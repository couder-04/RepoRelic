import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Tuple
from dotenv import load_dotenv

# Load .env from repository root (two levels up from this file)
BASE_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = BASE_DIR / ".env"
if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)

@dataclass
class Config:
    # --- Static analysis thresholds ---
    complexity_threshold: int = 10           # Cyclomatic complexity >= this is risky
    min_lines_no_docstring: int = 20         # No docstring + > this lines → risky

    # --- LLM provider selection ---
    llm_provider: str = field(default_factory=lambda: os.getenv("LLM_PROVIDER", "gemini").lower())
    gemini_api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    deepseek_api_key: str = field(default_factory=lambda: os.getenv("DEEPSEEK_API_KEY", ""))
    deepseek_base_url: str = field(default_factory=lambda: os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"))

    # Model names per provider (can be overridden via env if needed)
    gemini_test_model: str = field(default_factory=lambda: os.getenv("GEMINI_TEST_MODEL", "gemini-2.5-flash"))
    gemini_diag_model: str = field(default_factory=lambda: os.getenv("GEMINI_DIAG_MODEL", "gemini-2.5-pro"))
    deepseek_test_model: str = field(default_factory=lambda: os.getenv("DEEPSEEK_TEST_MODEL", "deepseek/deepseek-v4-flash"))
    deepseek_diag_model: str = field(default_factory=lambda: os.getenv("DEEPSEEK_DIAG_MODEL", "deepseek/deepseek-v4-flash"))

    # --- Rate limiting (caveman) ---
    max_rpm: int = 15
    max_tpm: int = 30_000
    min_delay_seconds: float = 2.0

    # --- Paths ---
    output_dir: str = ".reporelic"
    tests_dir: str = ".reporelic/generated_tests"
    report_filename: str = "report.md"
    knowledge_graph_filename: str = "knowledge_graph.json"

    # Directories to skip when walking codebase
    skip_dirs: Tuple[str, ...] = (
        "__pycache__", ".venv", "venv", ".git",
        ".reporelic", "node_modules", ".mypy_cache",
        ".pytest_cache", "dist", "build", "*.egg-info",
    )

    def validate(self):
        """Ensure required keys are present for the chosen provider."""
        if self.llm_provider == "gemini":
            if not self.gemini_api_key:
                raise RuntimeError("GEMINI_API_KEY missing in .env for Gemini provider.")
        elif self.llm_provider == "deepseek":
            if not self.deepseek_api_key:
                raise RuntimeError("DEEPSEEK_API_KEY missing in .env for DeepSeek provider.")
        else:
            raise ValueError(f"Unsupported LLM_PROVIDER: {self.llm_provider}")


def load_config(target_path: str) -> Config:
    """Create a Config instance and adjust path‑related values.
    The function injects the absolute output directory based on the target codebase.
    """
    cfg = Config()
    # Resolve output directories relative to the target workspace
    cfg.output_dir = os.path.join(target_path, cfg.output_dir)
    cfg.tests_dir = os.path.join(cfg.output_dir, "generated_tests")
    # Validate provider‑specific keys
    cfg.validate()
    return cfg
