"""Stage 5 — Test Generation.

For each risky function from Stage 4, render the test_gen.j2 prompt,
send it to the LLM, and write the returned code to
  .reporelic/generated_tests/test_<module>_<func>.py
"""
from __future__ import annotations

import ast
import importlib.util
import os
import re
import sys
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from engine.config import Config
from engine.llm.gemini_client import LLMClient
from engine import progress

_PROMPT_DIR = Path(__file__).resolve().parents[1] / "llm" / "prompts"


def run(
    risky_funcs: list[dict[str, Any]],
    cfg: Config,
    client: LLMClient,
) -> tuple[list[str], list[dict[str, Any]]]:
    """
    Returns
    -------
    generated_test_paths : list of absolute paths to written test files
    skipped_due_to_missing_deps : list of dicts with missing dependency details
    """
    stage, name = 5, "Test Generation"
    total = len(risky_funcs)

    if total == 0:
        progress.emit(stage, name, "done", "No risky functions — skipping test generation.")
        return [], []

    progress.emit(stage, name, "running",
                  f"Generating tests for {total} risky functions ...")

    os.makedirs(cfg.tests_dir, exist_ok=True)
    env = Environment(loader=FileSystemLoader(str(_PROMPT_DIR)), trim_blocks=True)
    template = env.get_template("test_gen.j2")

    generated: list[str] = []
    skipped_deps: list[dict[str, Any]] = []

    project_root = os.path.dirname(cfg.output_dir)

    for i, func in enumerate(risky_funcs, 1):
        progress.emit(stage, name, "running",
                      f"[{i}/{total}] Generating test for {func['name']} "
                      f"({func['file']}) ...")
        try:
            missing = _missing_dependencies(func['abs_path'], project_root)
            if missing:
                progress.emit(stage, name, "running",
                              f"  ⚠ Skipped {func['name']}: missing dependencies {missing}")
                skipped_deps.append({
                    "function": func['name'],
                    "file": func['file'],
                    "missing": missing,
                })
                continue

            prompt = template.render(func=_FuncView(func))
            code = client.generate(prompt, model_role="test")
            code = _strip_fences(code)

            if not _is_valid_test_code(code):
                progress.emit(stage, name, "running",
                              f"  ⚠ Skipped {func['name']}: generated code is not valid pytest or contains no assertions")
                continue

            out_path = _test_file_path(cfg.tests_dir, func)
            Path(out_path).write_text(code, encoding="utf-8")
            generated.append(out_path)
        except Exception as e:
            progress.emit(stage, name, "running",
                          f"  ⚠ Skipped {func['name']}: {e}")

    progress.emit(stage, name, "done",
                  f"Generated {len(generated)}/{total} test files in {cfg.tests_dir}")
    return generated, skipped_deps


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FuncView:
    """Thin wrapper to expose func dict as object attributes to Jinja2."""
    def __init__(self, d: dict):
        self.__dict__.update(d)


def _test_file_path(tests_dir: str, func: dict) -> str:
    module = func["file"].replace("/", "_").replace("\\", "_").removesuffix(".py")
    func_name = re.sub(r"[^a-zA-Z0-9_]", "_", func["name"])
    return os.path.join(tests_dir, f"test_{module}__{func_name}.py")


def _strip_fences(code: str) -> str:
    """Remove markdown code fences if the LLM wrapped its output."""
    code = re.sub(r"^```(?:python)?\n?", "", code.strip())
    code = re.sub(r"\n?```$", "", code.strip())
    return code.strip()


def _missing_dependencies(path: str, project_root: str) -> list[str]:
    try:
        source = Path(path).read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source)
    except Exception:
        return []

    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level > 0:
                continue
            if node.module:
                modules.add(node.module.split(".")[0])

    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    missing = []
    for module in sorted(modules):
        if module in {"__future__", "typing", "dataclasses", "pathlib", "os", "sys", "re", "json", "ast", "math", "collections", "typing_extensions"}:
            continue
        try:
            if importlib.util.find_spec(module) is None:
                missing.append(module)
        except Exception:
            missing.append(module)
    return missing


def _is_valid_test_code(code: str) -> bool:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return False

    has_assert = any(isinstance(node, ast.Assert) for node in ast.walk(tree))
    has_pytest_raises = any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and getattr(node.func.value, "id", "") == "pytest"
        and node.func.attr == "raises"
        for node in ast.walk(tree)
    )
    return has_assert or has_pytest_raises
