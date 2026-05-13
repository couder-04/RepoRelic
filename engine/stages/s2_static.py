"""Stage 2 — Static Analysis.

Combines:
  - Custom AST checks  (bare-except, mutable defaults, unused imports)
  - Radon              (cyclomatic complexity per function)
  - Pylint             (programmatic run via TextReporter → StringIO)
  - Pyflakes           (subprocess call, output parsed)
"""
from __future__ import annotations

import ast
import io
import os
import re
import subprocess
import sys
from typing import Optional

from radon.complexity import cc_visit
from radon.visitors import ComplexityVisitor
from pylint.lint import Run as PylintRun
from pylint.reporters.text import TextReporter

from engine.config import Config
from engine.models.file_map import FileMap, FunctionInfo
from engine.models.analysis import AnalysisResult, StaticIssue, ComplexityScore
from engine import progress


# ---------------------------------------------------------------------------
# Public entry-point
# ---------------------------------------------------------------------------

def run(file_maps: list[FileMap], cfg: Config) -> AnalysisResult:
    stage, name = 2, "Static Analysis"
    result = AnalysisResult()

    # Only analyze files that parsed successfully
    valid = [f for f in file_maps if f.parse_error is None]
    total = len(valid)
    progress.emit(stage, name, "running", f"Analysing {total} files ...")

    for i, fm in enumerate(valid, 1):
        source = _read(fm.path)

        # 1. Custom AST checks
        result.issues.extend(_ast_checks(fm.path, source))

        # 2. Radon cyclomatic complexity
        result.complexity_scores.extend(_radon_complexity(fm.path, source))

        # 3. Pylint
        result.issues.extend(_pylint_check(fm.path))

        # 4. Pyflakes
        result.issues.extend(_pyflakes_check(fm.path))

        if i % 10 == 0 or i == total:
            progress.emit(stage, name, "running", f"Analysed {i}/{total} files ...")

    progress.emit(
        stage, name, "done",
        f"{len(result.issues)} issues found | "
        f"{len(result.complexity_scores)} complexity scores computed",
    )
    return result


# ---------------------------------------------------------------------------
# 1. Custom AST checks
# ---------------------------------------------------------------------------

def _read(path: str) -> str:
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def _ast_checks(path: str, source: str) -> list[StaticIssue]:
    issues: list[StaticIssue] = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return issues

    for node in ast.walk(tree):
        # Bare except
        if isinstance(node, ast.ExceptHandler) and node.type is None:
            issues.append(StaticIssue(
                file=path, line=node.lineno, code="bare-except",
                message="Bare 'except:' catches SystemExit and KeyboardInterrupt",
                severity="warning", tool="ast",
            ))

        # Mutable default argument
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for default in node.args.defaults + node.args.kw_defaults:
                if default and isinstance(default, (ast.List, ast.Dict, ast.Set)):
                    issues.append(StaticIssue(
                        file=path, line=node.lineno, code="mutable-default",
                        message=f"Function '{node.name}' uses a mutable default argument",
                        severity="warning", tool="ast",
                    ))

    # Unused imports (simple heuristic: imported name not used in source body)
    try:
        imported_names = _collect_imported_names(tree)
        used_names = {
            n.id for n in ast.walk(tree)
            if isinstance(n, ast.Name)
        }
        for name, lineno in imported_names.items():
            if name not in used_names:
                issues.append(StaticIssue(
                    file=path, line=lineno, code="unused-import",
                    message=f"'{name}' is imported but never used",
                    severity="convention", tool="ast",
                ))
    except Exception:
        pass

    return issues


def _collect_imported_names(tree: ast.Module) -> dict[str, int]:
    """Return {alias: lineno} for every imported name (simple heuristic)."""
    names: dict[str, int] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                key = alias.asname or alias.name.split(".")[0]
                names[key] = node.lineno
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == "*":
                    continue
                key = alias.asname or alias.name
                names[key] = node.lineno
    return names


# ---------------------------------------------------------------------------
# 2. Radon — cyclomatic complexity
# ---------------------------------------------------------------------------

def _radon_complexity(path: str, source: str) -> list[ComplexityScore]:
    scores: list[ComplexityScore] = []
    try:
        blocks = cc_visit(source)
        for block in blocks:
            scores.append(ComplexityScore(
                function_name=block.name,
                file=path,
                lineno=block.lineno,
                score=block.complexity,
                rank=block.letter,   # A-F
            ))
    except Exception:
        pass
    return scores


# ---------------------------------------------------------------------------
# 3. Pylint — programmatic run
# ---------------------------------------------------------------------------

_PYLINT_MSG_RE = re.compile(
    r"(?P<path>.+?):(?P<line>\d+):\d+: (?P<code>[A-Z]\d+): (?P<msg>.+)"
)
_SEVERITY_MAP = {
    "E": "error", "F": "error",
    "W": "warning",
    "C": "convention", "R": "refactor",
}

def _pylint_check(path: str) -> list[StaticIssue]:
    issues: list[StaticIssue] = []
    buf = io.StringIO()
    try:
        import contextlib
        with contextlib.redirect_stdout(io.StringIO()), \
             contextlib.redirect_stderr(io.StringIO()):
            PylintRun(
                [path, "--output-format=text", "--score=no",
                 "--disable=all",
                 "--enable=E,W,C0301,C0303,C0411,C0412,C0413,R0912,R0914,R0915"],
                reporter=TextReporter(buf),
                exit=False,
            )
    except Exception:
        pass

    for line in buf.getvalue().splitlines():
        m = _PYLINT_MSG_RE.match(line)
        if m:
            code = m.group("code")
            sev = _SEVERITY_MAP.get(code[0], "convention")
            issues.append(StaticIssue(
                file=path,
                line=int(m.group("line")),
                code=code,
                message=m.group("msg"),
                severity=sev,
                tool="pylint",
            ))
    return issues


# ---------------------------------------------------------------------------
# 4. Pyflakes — subprocess
# ---------------------------------------------------------------------------

_PYFLAKES_RE = re.compile(r"(.+):(\d+):\d+ (.+)")

def _pyflakes_check(path: str) -> list[StaticIssue]:
    issues: list[StaticIssue] = []
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pyflakes", path],
            capture_output=True, text=True, timeout=30,
        )
        for line in (result.stdout + result.stderr).splitlines():
            m = _PYFLAKES_RE.match(line)
            if m:
                issues.append(StaticIssue(
                    file=m.group(1),
                    line=int(m.group(2)),
                    code="pyflakes",
                    message=m.group(3).strip(),
                    severity="warning",
                    tool="pyflakes",
                ))
    except Exception:
        pass
    return issues
