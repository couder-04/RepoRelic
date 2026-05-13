"""Orchestrator — runs all 8 analysis stages in sequence."""
from __future__ import annotations

import sys
from engine import progress
from engine.config import load_config
from engine.llm.gemini_client import LLMClient
from engine.stages import (
    s1_understand,
    s2_static,
    s3_depgraph,
    s4_knowledge,
    s5_testgen,
    s6_executor,
    s7_diagnosis,
    s8_report,
)


def run(target_path: str):
    # ── Load config (validates API key) ──────────────────────────────────
    try:
        cfg = load_config(target_path)
    except (RuntimeError, ValueError) as e:
        progress.emit_error(str(e))
        sys.exit(1)

    # ── Shared LLM client (rate-limited) ─────────────────────────────────
    client = LLMClient(cfg)

    # ── Stage 1: Understand codebase ─────────────────────────────────────
    file_maps = _run_stage(
        1, "Understand Codebase",
        lambda: s1_understand.run(target_path, cfg)
    )

    # ── Stage 2: Static analysis ──────────────────────────────────────────
    analysis = _run_stage(
        2, "Static Analysis",
        lambda: s2_static.run(file_maps, cfg)
    )

    # ── Stage 3: Dependency graph ─────────────────────────────────────────
    dep_graph = _run_stage(
        3, "Dependency Graph",
        lambda: s3_depgraph.run(file_maps, target_path, cfg)
    )

    # ── Stage 4: Knowledge graph ──────────────────────────────────────────
    dep_graph, risky_funcs = _run_stage(
        4, "Knowledge Graph",
        lambda: s4_knowledge.run(dep_graph, file_maps, analysis, cfg)
    )

    # ── Stage 5: Test generation (LLM) ────────────────────────────────────
    generated_tests, skipped_deps = _run_stage(
        5, "Test Generation",
        lambda: s5_testgen.run(risky_funcs, cfg, client)
    )

    # ── Stage 6: Execution ────────────────────────────────────────────────
    test_results = _run_stage(
        6, "Execution Engine",
        lambda: s6_executor.run(generated_tests, target_path, cfg)
    )

    # ── Stage 7: Failure diagnosis (LLM) ──────────────────────────────────
    diagnoses = _run_stage(
        7, "Failure Diagnosis",
        lambda: s7_diagnosis.run(test_results, dep_graph, risky_funcs, cfg, client)
    )

    # ── Stage 8: Report ────────────────────────────────────────────────────
    report_path = _run_stage(
        8, "Output Report",
        lambda: s8_report.run(
            target_path, file_maps, analysis, dep_graph,
            risky_funcs, test_results, diagnoses, cfg, skipped_deps
        )
    )

    progress.emit_complete(report_path)


def _run_stage(stage_num: int, stage_name: str, fn):
    """Run a stage function, catching any unexpected exception."""
    try:
        return fn()
    except Exception as e:
        progress.emit_error(f"Stage {stage_num} ({stage_name}) crashed: {e}")
        # Return safe defaults so remaining stages can still attempt to run
        import traceback as tb
        progress.emit(stage_num, stage_name, "error", tb.format_exc()[:500])
        return _safe_defaults(stage_num)


def _safe_defaults(stage_num: int):
    """Return an empty default value appropriate for each stage's output type."""
    defaults = {
        1: [],          # file_maps
        2: _EmptyAnalysis(),
        3: _empty_graph(),
        4: (_empty_graph(), []),
        5: ([], []),
        6: [],
        7: [],
        8: "",
    }
    return defaults.get(stage_num, None)


class _EmptyAnalysis:
    issues = []
    complexity_scores = []


def _empty_graph():
    import networkx as nx
    return nx.DiGraph()
