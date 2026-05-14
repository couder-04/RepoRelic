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

    progress.emit(
        1,
        "System",
        "running",
        f"Initializing RepoRelic pipeline... "
        f"(Python {sys.version.split()[0]} at {sys.executable})"
    )

    # ─────────────────────────────────────────────────────────────
    # Load config
    # ─────────────────────────────────────────────────────────────

    try:
        cfg = load_config(target_path)

    except (RuntimeError, ValueError) as e:
        progress.emit_error(str(e))
        sys.exit(1)

    # ─────────────────────────────────────────────────────────────
    # Shared LLM client
    # ─────────────────────────────────────────────────────────────

    progress.emit(
        1,
        "LLM",
        "running",
        "Initializing LLM client..."
    )

    client = LLMClient(cfg)

    # ─────────────────────────────────────────────────────────────
    # Stage 1 — Understand Codebase
    # ─────────────────────────────────────────────────────────────

    file_maps = _run_stage(
        1,
        "Understand Codebase",
        lambda: s1_understand.run(target_path, cfg)
    )

    # ─────────────────────────────────────────────────────────────
    # Dependency Resolution
    # ─────────────────────────────────────────────────────────────

    try:
        from engine.dep_resolver import resolve as resolve_deps

        dep_summary = resolve_deps(file_maps, target_path)

    except Exception as e:

        dep_summary = {
            "installed": [],
            "failed": [],
            "skipped": [],
            "python": sys.executable,
        }

        progress.emit(
            1,
            "Dependency Resolver",
            "running",
            f"Dependency resolver skipped: {e}"
        )

    # ─────────────────────────────────────────────────────────────
    # Stage 2 — Static Analysis
    # ─────────────────────────────────────────────────────────────

    analysis = _run_stage(
        2,
        "Static Analysis",
        lambda: s2_static.run(file_maps, cfg)
    )

    # ─────────────────────────────────────────────────────────────
    # Stage 3 — Dependency Graph
    # ─────────────────────────────────────────────────────────────

    dep_graph = _run_stage(
        3,
        "Dependency Graph",
        lambda: s3_depgraph.run(file_maps, target_path, cfg)
    )

    # ─────────────────────────────────────────────────────────────
    # Stage 4 — Knowledge Graph
    # ─────────────────────────────────────────────────────────────

    dep_graph, risky_funcs = _run_stage(
        4,
        "Knowledge Graph",
        lambda: s4_knowledge.run(
            dep_graph,
            file_maps,
            analysis,
            cfg
        )
    )

    # ─────────────────────────────────────────────────────────────
    # Stage 5 — Test Generation
    # ─────────────────────────────────────────────────────────────

    generated_tests, skipped_deps = _run_stage(
        5,
        "Test Generation",
        lambda: s5_testgen.run(
            risky_funcs,
            cfg,
            client
        )
    )

    # ─────────────────────────────────────────────────────────────
    # Stage 6 — Execution
    # ─────────────────────────────────────────────────────────────

    test_results = _run_stage(
        6,
        "Execution Engine",
        lambda: s6_executor.run(
            generated_tests,
            target_path,
            cfg
        )
    )

    # ─────────────────────────────────────────────────────────────
    # Stage 7 — Failure Diagnosis
    # ─────────────────────────────────────────────────────────────

    diagnoses = _run_stage(
        7,
        "Failure Diagnosis",
        lambda: s7_diagnosis.run(
            test_results,
            dep_graph,
            risky_funcs,
            cfg,
            client
        )
    )

    # ─────────────────────────────────────────────────────────────
    # Stage 8 — Output Report
    # ─────────────────────────────────────────────────────────────

    report_path = _run_stage(
        8,
        "Output Report",
        lambda: s8_report.run(
            target_path=target_path,
            file_maps=file_maps,
            analysis=analysis,
            G=dep_graph,
            risky_funcs=risky_funcs,
            test_results=test_results,
            diagnoses=diagnoses,
            cfg=cfg,
            missing_deps=skipped_deps,
            dep_summary=dep_summary,
        )
    )

    # ─────────────────────────────────────────────────────────────
    # Completion
    # ─────────────────────────────────────────────────────────────

    if report_path:

        progress.emit(
            8,
            "Complete",
            "done",
            "Pipeline finished successfully."
        )

        progress.emit_complete(report_path)

    else:

        progress.emit(
            8,
            "Complete",
            "error",
            "Pipeline completed with errors."
        )


def _run_stage(stage_num: int, stage_name: str, fn):
    """Run stage with live UI updates."""

    progress.emit(
        stage_num,
        stage_name,
        "running",
        f"{stage_name} started... "
        f"(Python {sys.version.split()[0]})"
    )

    try:

        result = fn()

        progress.emit(
            stage_num,
            stage_name,
            "done",
            f"{stage_name} completed successfully."
        )

        return result

    except Exception as e:

        progress.emit_error(
            f"Stage {stage_num} ({stage_name}) crashed: {e}"
        )

        import traceback as tb

        progress.emit(
            stage_num,
            stage_name,
            "error",
            tb.format_exc()[:2000]
        )

        return _safe_defaults(stage_num)


def _safe_defaults(stage_num: int):

    defaults = {
        1: [],
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