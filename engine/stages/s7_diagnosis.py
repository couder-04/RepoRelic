"""Stage 7 — Failure Diagnosis.

For each failed test, look up the matching function in the knowledge graph,
render the diagnosis.j2 prompt, send it to the LLM, and parse the structured
response into DiagnosisResult objects.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import networkx as nx
from jinja2 import Environment, FileSystemLoader

from engine.config import Config
from engine.llm.gemini_client import LLMClient
from engine.models.report import TestResult, DiagnosisResult
from engine import progress

_PROMPT_DIR = Path(__file__).resolve().parents[1] / "llm" / "prompts"


def run(
    test_results: list[TestResult],
    G: nx.DiGraph,
    risky_funcs: list[dict[str, Any]],
    cfg: Config,
    client: LLMClient,
) -> list[DiagnosisResult]:
    stage, name = 7, "Failure Diagnosis"

    failed = [r for r in test_results if r.status == "failed"]
    if not failed:
        progress.emit(stage, name, "done", "No failures to diagnose.")
        return []

    progress.emit(stage, name, "running",
                  f"Diagnosing {len(failed)} failure(s) via LLM ...")

    env = Environment(loader=FileSystemLoader(str(_PROMPT_DIR)), trim_blocks=True)
    template = env.get_template("diagnosis.j2")

    # Build lookup: test_name → func dict (by matching test file suffix to func name)
    func_lookup = _build_func_lookup(risky_funcs)

    diagnoses: list[DiagnosisResult] = []

    for i, result in enumerate(failed, 1):
        func = _find_func(result, func_lookup)
        if not func:
            progress.emit(stage, name, "running",
                          f"[{i}/{len(failed)}] Could not match {result.test_name} to a function — skipping.")
            continue

        progress.emit(stage, name, "running",
                      f"[{i}/{len(failed)}] Diagnosing {result.test_name} ...")
        try:
            test_code = _read_test_code(result.test_file, result.test_name)
            prompt = template.render(
                test_code=test_code,
                traceback=result.traceback or "",
                func=_FuncView(func),
            )
            response = client.generate(prompt, model_role="diag")
            diagnosis = _parse_response(func["name"], result.test_name, response)
            diagnoses.append(diagnosis)
        except Exception as e:
            progress.emit(stage, name, "running",
                          f"  ⚠ Failed to diagnose {result.test_name}: {e}")

    progress.emit(stage, name, "done",
                  f"Diagnosed {len(diagnoses)}/{len(failed)} failures.")
    return diagnoses


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FuncView:
    def __init__(self, d: dict):
        self.__dict__.update(d)


def _build_func_lookup(risky_funcs: list[dict]) -> dict[str, dict]:
    return {f["name"]: f for f in risky_funcs}


def _find_func(result: TestResult, lookup: dict[str, dict]) -> dict | None:
    """Heuristic: test name usually contains the function name after 'test_'."""
    clean = re.sub(r"^test_", "", result.test_name)
    # Try direct match first
    for key in lookup:
        if key in clean or clean.startswith(key):
            return lookup[key]
    return None


def _read_test_code(test_file: str, test_name: str) -> str:
    """Extract the specific test function's source from the file."""
    try:
        src = Path(test_file).read_text(encoding="utf-8", errors="replace")
        # Find the def test_name block
        pattern = re.compile(
            rf"(def {re.escape(test_name)}\(.*?\):.*?)(?=\ndef |\Z)", re.S
        )
        m = pattern.search(src)
        return m.group(1).strip() if m else src[:1500]
    except Exception:
        return ""


def _parse_response(func_name: str, test_name: str, text: str) -> DiagnosisResult:
    """Parse WHY / IS_BUG / SUGGESTED_FIX from LLM response."""
    why = _extract(r"WHY IT FAILED:\s*(.+)", text, "Unknown")
    bug_raw = _extract(r"IS IT A REAL BUG:\s*(.+)", text, "unclear")
    fix = _extract(r"SUGGESTED FIX:\s*([\s\S]+)", text, text)
    is_bug = "yes" in bug_raw.lower()
    return DiagnosisResult(
        function_name=func_name,
        test_name=test_name,
        why_failed=why,
        is_real_bug=is_bug,
        suggested_fix=fix.strip(),
    )


def _extract(pattern: str, text: str, default: str) -> str:
    m = re.search(pattern, text, re.IGNORECASE)
    return m.group(1).strip() if m else default
