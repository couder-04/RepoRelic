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
) -> str:
    stage, name = 8, "Output Report"
    progress.emit(stage, name, "running", "Writing report.md ...")

    os.makedirs(cfg.output_dir, exist_ok=True)
    report_path = os.path.join(cfg.output_dir, cfg.report_filename)

    lines: list[str] = []
    _header(lines, target_path, file_maps, analysis, risky_funcs, test_results)
    _summary_table(lines, file_maps, analysis, risky_funcs, test_results)
    _static_issues(lines, analysis)
    _risky_functions(lines, risky_funcs)
    _dep_graph(lines, G)
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


def _summary_table(lines, file_maps, analysis, risky, test_results):
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
        "_Report generated by [RepoRelic](https://github.com/your-repo/reporelic)_",
    ]
