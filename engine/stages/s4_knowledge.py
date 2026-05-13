"""Stage 4 — Knowledge Graph.

Enrich the dependency graph (from Stage 3) with per-function metadata:
  - signature, docstring, complexity score, rank
  - static issues list
  - is_risky flag (based on configurable thresholds)

Serializes the enriched graph to .reporelic/knowledge_graph.json.
Returns a list of "risky" function node IDs ready for Stage 5.
"""
from __future__ import annotations

import inspect
import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

import networkx as nx
from networkx.readwrite import json_graph

from engine.enrichment.git_analyzer import enrich_with_git_history
from engine import progress


# ---------------------------------------------------------------------------
# Public entry-point
# ---------------------------------------------------------------------------

def run(
    G: nx.DiGraph,
    file_maps: list[FileMap],
    analysis: AnalysisResult,
    cfg: Config,
    target_path: str = "",
) -> tuple[nx.DiGraph, list[dict[str, Any]]]:
    """
    Returns
    -------
    G            : enriched graph (mutated in-place)
    risky_funcs  : list of function dicts flagged for test generation
    """
    stage, name = 4, "Knowledge Graph"
    progress.emit(stage, name, "running", "Enriching graph with function metadata ...")

    # Build fast lookup maps
    complexity_map = _build_complexity_map(analysis.complexity_scores)
    issues_map = _build_issues_map(analysis.issues)

    risky_funcs: list[dict[str, Any]] = []

    for fm in file_maps:
        if fm.parse_error:
            continue

        all_functions = fm.functions + [m for cls in fm.classes for m in cls.methods]

        for func in all_functions:
            node_id = _func_node_id(fm.rel_path, func)
            cc = complexity_map.get(_func_key(fm.path, func.name))
            issues = issues_map.get(fm.path, [])
            func_issues = [i for i in issues if i.line >= func.lineno
                           and i.line <= func.end_lineno]

            is_risky = _determine_risk(func, cc, func_issues, cfg)

            # Attach attributes to graph node
            G.add_node(node_id, **{
                "kind": "function",
                "file": fm.rel_path,
                "abs_path": fm.path,
                "name": func.name,
                "class_name": func.class_name,
                "lineno": func.lineno,
                "end_lineno": func.end_lineno,
                "args": func.args,
                "docstring": func.docstring or "",
                "source": func.source,
                "complexity": cc.score if cc else 0,
                "complexity_rank": cc.rank if cc else "A",
                "issues": [_issue_dict(i) for i in func_issues],
                "is_risky": is_risky,
            })

            if is_risky:
                risky_funcs.append(dict(G.nodes[node_id]))
                risky_funcs[-1]["node_id"] = node_id

    # Enrich risky functions with git history data
    risky_funcs = enrich_with_git_history(risky_funcs, target_path, cfg)

    # Serialize graph to JSON
    os.makedirs(cfg.output_dir, exist_ok=True)
    kg_path = os.path.join(cfg.output_dir, cfg.knowledge_graph_filename)
    _save_graph(G, kg_path)

    progress.emit(
        stage, name, "done",
        f"Knowledge graph saved to {kg_path} | "
        f"{len(risky_funcs)} risky functions flagged",
    )
    return G, risky_funcs


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _func_node_id(rel_path: str, func: FunctionInfo) -> str:
    base = rel_path.removesuffix(".py").replace(os.sep, ".")
    if func.class_name:
        return f"{base}.{func.class_name}.{func.name}"
    return f"{base}.{func.name}"


def _func_key(abs_path: str, func_name: str) -> str:
    return f"{abs_path}::{func_name}"


def _build_complexity_map(scores: list[ComplexityScore]) -> dict[str, ComplexityScore]:
    return {f"{s.file}::{s.function_name}": s for s in scores}


def _build_issues_map(issues: list[StaticIssue]) -> dict[str, list[StaticIssue]]:
    result: dict[str, list[StaticIssue]] = {}
    for issue in issues:
        result.setdefault(issue.file, []).append(issue)
    return result


def _issue_dict(issue: StaticIssue) -> dict:
    return {
        "line": issue.line, "code": issue.code,
        "message": issue.message, "severity": issue.severity,
        "tool": issue.tool,
    }


def _determine_risk(
    func: FunctionInfo,
    cc: ComplexityScore | None,
    issues: list[StaticIssue],
    cfg: Config,
) -> bool:
    # High cyclomatic complexity
    if cc and cc.score >= cfg.complexity_threshold:
        return True
    # Long function without a docstring
    body_lines = func.end_lineno - func.lineno
    if not func.docstring and body_lines > cfg.min_lines_no_docstring:
        return True
    # Has static errors (severity == "error")
    if any(i.severity == "error" for i in issues):
        return True
    # Contains a bare-except
    if any(i.code == "bare-except" for i in issues):
        return True
    return False


def _save_graph(G: nx.DiGraph, path: str):
    data = json_graph.node_link_data(G)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, default=str)
