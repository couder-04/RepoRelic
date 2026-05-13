"""Stage 8 — Output Report.

Assembles all stage outputs into a Markdown report written to
  <target>/.reporelic/report.md
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import networkx as nx

from engine.config import Config
from engine.models.file_map import FileMap
from engine.models.analysis import AnalysisResult
from engine.models.report import TestResult, DiagnosisResult
from engine import progress

_RANK_EMOJI = {"A": "🟢", "B": "🟡", "C": "🟠", "D": "🔴", "E": "🔴", "F": "🔴"}
_SEV_EMOJI = {"error": "🔴", "warning": "🟡", "convention": "🔵", "refactor": "🟣"}


def run(
    target_path: str,
    file_maps: list[FileMap],
    analysis: AnalysisResult,
    G: nx.DiGraph,
    risky_funcs: list[dict[str, Any]],
    test_results: list[TestResult],
    diagnoses: list[DiagnosisResult],
    cfg: Config,
    missing_deps: list[dict[str, Any]],
) -> str:
    stage, name = 8, "Output Report"
    progress.emit(stage, name, "running", "Writing report.md ...")

    os.makedirs(cfg.output_dir, exist_ok=True)
    report_path = os.path.join(cfg.output_dir, cfg.report_filename)

    lines: list[str] = []
    _header(lines, target_path, file_maps, analysis, risky_funcs, test_results)
    _summary_table(lines, file_maps, analysis, risky_funcs, test_results, missing_deps)
    _static_issues(lines, analysis)
    _risky_functions(lines, risky_funcs)
    _dependency_remarks(lines, missing_deps)
    _dep_graph(lines, G)
    _suggestions(lines, G, risky_funcs)
    _test_results(lines, test_results, diagnoses)
    _footer(lines)

    Path(report_path).write_text("\n".join(lines), encoding="utf-8")
    progress.emit(stage, name, "done", f"Report written to {report_path}")
    return report_path


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def _header(lines, target_path, file_maps, analysis, risky, test_results):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines += [
        "# 🔍 RepoRelic Analysis Report",
        f"> **Generated:** {ts}  ",
        f"> **Target:** `{target_path}`  ",
        f"> **Files:** {len(file_maps)}",
        "",
    ]


def _summary_table(lines, file_maps, analysis, risky, test_results, missing_deps):
    valid = [f for f in file_maps if not f.parse_error]
    func_count = sum(len(f.functions) for f in valid)
    class_count = sum(len(f.classes) for f in valid)
    passed = sum(1 for t in test_results if t.status == "passed")
    failed = sum(1 for t in test_results if t.status != "passed")
    lines += [
        "## 📊 Summary",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Files analysed | {len(file_maps)} ({len(file_maps) - len(valid)} parse errors) |",
        f"| Functions | {func_count} |",
        f"| Classes | {class_count} |",
        f"| Risky functions | {len(risky)} |",
        f"| Static issues | {len(analysis.issues)} |",
        f"| Tests generated | {len(test_results)} |",
        f"| Tests passed | {passed} |",
        f"| Tests failed | {failed} |",
        f"| Functions skipped due to missing dependencies | {len(missing_deps)} |",
        "",
    ]


def _static_issues(lines, analysis: AnalysisResult):
    lines += ["## ⚠️ Static Issues", ""]
    if not analysis.issues:
        lines += ["_No issues found._", ""]
        return

    by_sev: dict[str, list] = {}
    for i in analysis.issues:
        by_sev.setdefault(i.severity, []).append(i)

    for sev in ("error", "warning", "convention", "refactor"):
        items = by_sev.get(sev, [])
        if not items:
            continue
        emoji = _SEV_EMOJI.get(sev, "•")
        lines += [f"### {emoji} {sev.capitalize()} ({len(items)})", ""]
        for issue in items[:30]:   # cap at 30 per severity
            lines.append(f"- `{issue.file}:{issue.line}` [{issue.code}] — {issue.message}")
        if len(items) > 30:
            lines.append(f"- _...and {len(items) - 30} more_")
        lines.append("")


def _risky_functions(lines, risky_funcs):
    lines += ["## 🔴 Risky Functions", ""]
    if not risky_funcs:
        lines += ["_No risky functions identified._", ""]
        return

    lines += [
        "| Function | File | Complexity | Issues |",
        "|----------|------|-----------|--------|",
    ]
    for f in risky_funcs:
        rank = f.get("complexity_rank", "?")
        emoji = _RANK_EMOJI.get(rank, "❓")
        issue_count = len(f.get("issues", []))
        lines.append(
            f"| `{f['name']}` | `{f['file']}:{f.get('lineno', '?')}` "
            f"| {emoji} {f.get('complexity', '?')} ({rank}) | {issue_count} issues |"
        )
    lines.append("")


def _dep_graph(lines, G: nx.DiGraph):
    lines += ["## 📈 Dependency Graph", ""]
    file_nodes = [(n, d) for n, d in G.nodes(data=True) if d.get("kind") == "file"]
    if not file_nodes:
        lines += ["_No import graph data._", ""]
        return

    # Top 10 most-imported files
    in_degrees = sorted(
        [(n, G.in_degree(n)) for n, d in G.nodes(data=True) if d.get("kind") == "file"],
        key=lambda x: x[1], reverse=True
    )[:10]

    lines += [f"**Total nodes:** {G.number_of_nodes()} | **Total edges:** {G.number_of_edges()}", ""]
    lines += ["**Most imported files:**", ""]
    for rank, (node, deg) in enumerate(in_degrees, 1):
        lines.append(f"{rank}. `{node}` — imported by {deg} file(s)")
    lines.append("")


def _dependency_remarks(lines, missing_deps: list[dict[str, Any]]):
    lines += ["## 🚧 Missing Dependency Remarks", ""]
    if not missing_deps:
        lines += ["_No missing dependency issues were detected during test generation._", ""]
        return

    lines += [
        "The following risky functions could not have tests generated because required imports were not available in the current environment. ",
        "Review dependency installation or stub the missing modules before running generation again.",
        "",
    ]
    for item in missing_deps:
        missing_list = ", ".join(f"`{m}`" for m in item["missing"])
        lines.append(
            f"- `{item['function']}` in `{item['file']}` is missing: {missing_list}"
        )
    lines.append("")


def _suggestions(lines, G: nx.DiGraph, risky_funcs: list[dict[str, Any]]):
    lines += ["## 💡 Refactoring Suggestions", ""]
    suggestions = []

    disconnected = _find_disconnected_functions(G)
    if disconnected:
        suggestions += [
            f"- `{func_name}` in `{file}` appears isolated: no internal call edges and its file is not imported by other modules. Consider reviewing or removing it."
            for func_name, file in disconnected
        ]

    duplicate_groups = _find_duplicate_functions(G)
    for group in duplicate_groups:
        names = [f"`{item['name']}` in `{item['file']}`" for item in group]
        suggestions.append(
            f"- Duplicate function logic found in {', '.join(names[:3])}{' and more' if len(names) > 3 else ''}. Consider consolidating these into a shared helper."
        )

    # Add git history volatility suggestions
    volatile_funcs = _find_highly_volatile_functions(risky_funcs)
    for func in volatile_funcs:
        git = func.get("git_history", {})
        if git.get("volatility_score", 0) > 5:
            suggestions.append(
                f"- `{func['name']}` in `{func['file']}` has high volatility (score: {git['volatility_score']}/10, {git['commit_count']} commits). "
                f"Consider adding more comprehensive error handling or breaking into smaller functions."
            )

    if not suggestions:
        lines += ["_No refactoring suggestions identified._", ""]
        return

    lines += suggestions
    lines.append("")


def _find_disconnected_functions(G: nx.DiGraph) -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []
    for node, data in G.nodes(data=True):
        if data.get("kind") != "function":
            continue
        file = data.get("file")
        if not file:
            continue

        has_call_in = any(k == "call" for _, _, k in G.in_edges(node, data="kind"))
        has_call_out = any(k == "call" for _, _, k in G.out_edges(node, data="kind"))
        if has_call_in or has_call_out:
            continue

        if G.in_degree(file) == 0:
            candidates.append((node, file))
    return candidates


def _find_duplicate_functions(G: nx.DiGraph) -> list[list[dict[str, object]]]:
    normalized: dict[str, list[dict[str, object]]] = {}
    for _, data in G.nodes(data=True):
        if data.get("kind") != "function":
            continue
        source = data.get("source", "")
        if not source:
            continue
        key = "\n".join(
            line.strip() for line in source.splitlines()
            if line.strip() and not line.strip().startswith("#")
        )
        if not key:
            continue
        normalized.setdefault(key, []).append(data)
    return [group for group in normalized.values() if len(group) > 1]


def _find_highly_volatile_functions(risky_funcs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Find functions with high git history volatility."""
    volatile = []
    for func in risky_funcs:
        git = func.get("git_history", {})
        if git.get("volatility_score", 0) > 5:  # Threshold for "highly volatile"
            volatile.append(func)
    return volatile


def _test_results(lines, test_results: list[TestResult],
                  diagnoses: list[DiagnosisResult]):
    lines += ["## 🧪 Test Results", ""]
    if not test_results:
        lines += ["_No tests were run._", ""]
        return

    passed = [t for t in test_results if t.status == "passed"]
    failed = [t for t in test_results if t.status != "passed"]

    diag_map = {d.test_name: d for d in diagnoses}

    if passed:
        lines += [f"### ✅ Passed ({len(passed)})", ""]
        for t in passed:
            lines.append(f"- `{t.test_name}` ({Path(t.test_file).name})")
        lines.append("")

    if failed:
        lines += [f"### ❌ Failed ({len(failed)})", ""]
        for t in failed:
            lines += [f"#### `{t.test_name}`", ""]
            lines += [f"- **File:** `{Path(t.test_file).name}`"]
            if t.traceback:
                lines += ["- **Traceback:**", "  ```", *[f"  {l}" for l in t.traceback.splitlines()[:20]], "  ```"]
            d = diag_map.get(t.test_name)
            if d:
                lines += [
                    "",
                    f"- **Why it failed:** {d.why_failed}",
                    f"- **Real bug:** {'Yes 🐛' if d.is_real_bug else 'No (test issue)'}",
                    f"- **Suggested fix:** {d.suggested_fix[:300]}",
                ]
            lines.append("")


def _footer(lines):
    lines += [
        "---",
        "_Report generated by [RepoRelic](https://github.com/couder-04/RepoRelic/tree/main)_",
    ]
