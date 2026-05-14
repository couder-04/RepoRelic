"""Stage 6 — Execution Engine.

Asks the user for permission, then runs all generated test files with
pytest inside the target project's own virtual environment (if found).

Returns a list of TestResult objects.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

from engine.config import Config
from engine.models.report import TestResult
from engine import progress


def run(
    generated_test_paths: list[str],
    target_path: str,
    cfg: Config,
) -> list[TestResult]:
    stage, name = 6, "Execution Engine"

    if not generated_test_paths:
        progress.emit(stage, name, "done", "No tests to run.")
        return []

    # --- Permission gate ---
    n = len(generated_test_paths)
    approved = progress.request_permission(
        "run_tests",
        f"RepoRelic generated {n} test file(s) in {cfg.tests_dir}. "
        f"Allow execution? (They will run inside the target project's environment.)"
    )
    if not approved:
        progress.emit(stage, name, "done",
                      "User denied test execution — skipping.")
        return []

    # --- Locate the Python interpreter ---
    python = _find_venv_python(target_path)
    progress.emit(stage, name, "running",
                  f"Using Python: {python} | Running {n} test files ...")

    results: list[TestResult] = []
    for test_file in generated_test_paths:
        results.extend(_run_single(python, test_file, target_path))

    passed = sum(1 for r in results if r.status == "passed")
    failed = sum(1 for r in results if r.status != "passed")
    progress.emit(stage, name, "done",
                  f"{passed} passed | {failed} failed across {n} test files")
    return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_venv_python(target_path: str) -> str:
    """Look for .venv / venv in the target project; fall back to sys.executable."""
    # If target_path is a file, search in its parent directory
    base_dir = os.path.dirname(target_path) if os.path.isfile(target_path) else target_path
    
    for venv_name in (".venv", "venv", "env"):
        candidate_win = Path(base_dir) / venv_name / "Scripts" / "python.exe"
        candidate_unix = Path(base_dir) / venv_name / "bin" / "python"
        if candidate_win.exists():
            return str(candidate_win)
        if candidate_unix.exists():
            return str(candidate_unix)
    return sys.executable


def _run_single(python: str, test_file: str, cwd: str) -> list[TestResult]:
    """Run one test file with pytest and parse the output."""
    # Ensure cwd is a directory
    exec_cwd = os.path.dirname(cwd) if os.path.isfile(cwd) else cwd
    
    try:
        proc = subprocess.run(
            [python, "-m", "pytest", test_file, "--tb=short", "-q", "--no-header"],
            capture_output=True, text=True, timeout=120, cwd=exec_cwd,
        )
        return _parse_pytest_output(test_file, proc.stdout + proc.stderr)
    except subprocess.TimeoutExpired:
        return [TestResult(
            test_file=test_file, test_name="<timeout>",
            status="error", traceback="pytest timed out after 120s",
        )]
    except Exception as e:
        return [TestResult(
            test_file=test_file, test_name="<runner-error>",
            status="error", traceback=str(e),
        )]


# Pattern: "FAILED test_file.py::test_name - ErrorType: msg"
_FAILED_RE = re.compile(r"FAILED (.+?)::(.+?) - (.+)")
_PASSED_RE = re.compile(r"(.+?)::(\S+) PASSED")
_ERROR_BLOCK_RE = re.compile(r"_{5,}\s+(.+?)\s+_{5,}\n(.*?)(?=\n_{5,}|\Z)", re.S)


def _parse_pytest_output(test_file: str, output: str) -> list[TestResult]:
    results: list[TestResult] = []
    seen: set[str] = set()

    # Extract tracebacks from error blocks
    tracebacks: dict[str, str] = {}
    for m in _ERROR_BLOCK_RE.finditer(output):
        test_id = m.group(1).strip()
        tracebacks[test_id] = m.group(2).strip()

    for line in output.splitlines():
        m = _FAILED_RE.search(line)
        if m:
            tname = m.group(2).strip()
            if tname not in seen:
                seen.add(tname)
                tb_key = f"{m.group(1).strip()}::{tname}"
                results.append(TestResult(
                    test_file=test_file, test_name=tname,
                    status="failed",
                    traceback=tracebacks.get(tb_key, m.group(3).strip()),
                ))
        m2 = _PASSED_RE.search(line)
        if m2:
            tname = m2.group(2).strip()
            if tname not in seen:
                seen.add(tname)
                results.append(TestResult(
                    test_file=test_file, test_name=tname,
                    status="passed",
                ))

    if not results:
        # Couldn't parse individual results — mark whole file as error
        results.append(TestResult(
            test_file=test_file, test_name="<all>",
            status="error",
            traceback=output[:2000],
        ))
    return results
