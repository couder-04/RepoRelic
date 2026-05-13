"""Stage 5 — Test Generation.

For each risky function from Stage 4, render the test_gen.j2 prompt,
send it to the LLM, and write the returned code to
  .reporelic/generated_tests/test_<module>_<func>.py
"""
from __future__ import annotations

import os
import re
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
) -> list[str]:
    """
    Returns
    -------
    generated_test_paths : list of absolute paths to written test files
    """
    stage, name = 5, "Test Generation"
    total = len(risky_funcs)

    if total == 0:
        progress.emit(stage, name, "done", "No risky functions — skipping test generation.")
        return []

    progress.emit(stage, name, "running",
                  f"Generating tests for {total} risky functions ...")

    os.makedirs(cfg.tests_dir, exist_ok=True)
    env = Environment(loader=FileSystemLoader(str(_PROMPT_DIR)), trim_blocks=True)
    template = env.get_template("test_gen.j2")

    generated: list[str] = []

    for i, func in enumerate(risky_funcs, 1):
        progress.emit(stage, name, "running",
                      f"[{i}/{total}] Generating test for {func['name']} "
                      f"({func['file']}) ...")
        try:
            prompt = template.render(func=_FuncView(func))
            code = client.generate(prompt, model_role="test")
            code = _strip_fences(code)

            out_path = _test_file_path(cfg.tests_dir, func)
            Path(out_path).write_text(code, encoding="utf-8")
            generated.append(out_path)
        except Exception as e:
            progress.emit(stage, name, "running",
                          f"  ⚠ Skipped {func['name']}: {e}")

    progress.emit(stage, name, "done",
                  f"Generated {len(generated)}/{total} test files in {cfg.tests_dir}")
    return generated


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
