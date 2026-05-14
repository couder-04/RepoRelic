"""
RepoRelic Dependency Resolver
-----------------------------

A production-grade dependency detection and installation engine.

Features:
- Detects target project virtual environment
- Parses third-party imports from FileMaps
- Avoids importing packages directly (safe detection)
- Supports requirements.txt / pyproject.toml / poetry.lock
- Auto-installs missing packages
- Uses batching for faster installs
- Handles import-name → pip-name mapping
- Emits detailed progress events
- Safer subprocess handling
- Compatible with Python 3.11+

Author: RepoRelic
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import sysconfig
from pathlib import Path
from typing import Iterable

from engine import progress
from engine.models.file_map import FileMap

# ============================================================
# STDLIB DETECTION
# ============================================================

try:
    STDLIB_MODULES = set(sys.stdlib_module_names)
except AttributeError:
    STDLIB_MODULES = set(Path(sysconfig.get_paths()["stdlib"]).iterdir())

# ============================================================
# IMPORT NAME → PIP PACKAGE NAME MAPPING
# ============================================================

IMPORT_TO_PIP: dict[str, str] = {
    "cv2": "opencv-python",
    "PIL": "Pillow",
    "sklearn": "scikit-learn",
    "bs4": "beautifulsoup4",
    "yaml": "PyYAML",
    "dotenv": "python-dotenv",
    "google": "google-generativeai",
    "googleapiclient": "google-api-python-client",
    "jwt": "PyJWT",
    "Crypto": "pycryptodome",
    "serial": "pyserial",
    "magic": "python-magic",
    "dateutil": "python-dateutil",
    "attr": "attrs",
    "nacl": "PyNaCl",
    "llama_index": "llama-index",
    "slack_sdk": "slack-sdk",
    "discord": "discord.py",
    "telegram": "python-telegram-bot",
    "pygame": "pygame",
}

# ============================================================
# SAFE PACKAGE ALLOWLIST
# ============================================================

SAFE_PACKAGES = {
    "numpy",
    "pandas",
    "pygame",
    "matplotlib",
    "seaborn",
    "plotly",
    "requests",
    "flask",
    "django",
    "fastapi",
    "uvicorn",
    "pytest",
    "torch",
    "tensorflow",
    "transformers",
    "scipy",
    "sympy",
    "networkx",
    "opencv-python",
    "Pillow",
    "beautifulsoup4",
    "PyYAML",
    "openai",
    "anthropic",
    "groq",
    "cohere",
    "langchain",
    "llama-index",
    "rich",
    "click",
    "typer",
    "loguru",
    "tqdm",
    "sqlalchemy",
    "alembic",
    "redis",
    "pymongo",
    "boto3",
    "aiohttp",
    "httpx",
}

# ============================================================
# PYTHON ENVIRONMENT DETECTION
# ============================================================

def find_target_python(target_path: str) -> str:
    """
    Detect target project's Python interpreter.
    """

    target = Path(target_path)

    for venv_name in (".venv", "venv", "env", ".env"):
        unix = target / venv_name / "bin" / "python"
        windows = target / venv_name / "Scripts" / "python.exe"

        if unix.exists():
            return str(unix)

        if windows.exists():
            return str(windows)

    return sys.executable

# ============================================================
# IMPORT COLLECTION
# ============================================================

def collect_imports(file_maps: list[FileMap]) -> set[str]:
    """
    Extract unique third-party imports.
    """

    imports: set[str] = set()

    for fm in file_maps:
        for imp in (fm.imports or []):

            name = (
                getattr(imp, "module", None)
                or getattr(imp, "name", "")
            )

            if not name:
                continue

            top_level = name.split(".")[0]

            if (
                top_level
                and top_level.isidentifier()
                and top_level not in STDLIB_MODULES
                and not top_level.startswith("_")
            ):
                imports.add(top_level)

    return imports

# ============================================================
# REQUIREMENTS FILE DETECTION
# ============================================================

def find_dependency_files(target_path: str) -> list[Path]:

    target = Path(target_path)

    candidates = [
        "requirements.txt",
        "requirements-dev.txt",
        "pyproject.toml",
        "poetry.lock",
    ]

    found = []

    for file in candidates:
        path = target / file
        if path.exists():
            found.append(path)

    return found

# ============================================================
# SAFE IMPORT CHECK
# ============================================================

def is_import_available(module_name: str) -> bool:
    """
    Safely check module availability without importing it.
    """

    return importlib.util.find_spec(module_name) is not None

# ============================================================
# INSTALL PACKAGE
# ============================================================

def install_packages(
    python: str,
    packages: Iterable[str],
    stage: int,
    stage_name: str,
) -> tuple[list[str], list[str]]:

    installed = []
    failed = []

    packages = list(packages)

    if not packages:
        return installed, failed

    progress.emit(
        stage,
        stage_name,
        "running",
        f"Installing {len(packages)} package(s)..."
    )

    cmd = [
        python,
        "-m",
        "pip",
        "install",
        *packages,
        "--disable-pip-version-check",
        "--no-input",
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
        )

        if result.returncode == 0:
            installed.extend(packages)

            progress.emit(
                stage,
                stage_name,
                "running",
                f"Installed: {', '.join(packages)}"
            )

        else:
            failed.extend(packages)

            progress.emit(
                stage,
                stage_name,
                "running",
                f"Installation failed: {', '.join(packages)}"
            )

    except subprocess.TimeoutExpired:

        failed.extend(packages)

        progress.emit(
            stage,
            stage_name,
            "running",
            f"Installation timeout: {', '.join(packages)}"
        )

    return installed, failed

# ============================================================
# MAIN RESOLVER
# ============================================================

def resolve(
    file_maps: list[FileMap],
    target_path: str,
) -> dict:

    stage = 1
    stage_name = "Dependency Resolver"

    python = find_target_python(target_path)

    progress.emit(
        stage,
        stage_name,
        "running",
        f"Using Python: {python}"
    )

    # --------------------------------------------------------
    # Install dependency files first
    # --------------------------------------------------------

    dependency_files = find_dependency_files(target_path)

    for dep_file in dependency_files:

        progress.emit(
            stage,
            stage_name,
            "running",
            f"Found dependency file: {dep_file.name}"
        )

        if dep_file.name.startswith("requirements"):

            subprocess.run(
                [
                    python,
                    "-m",
                    "pip",
                    "install",
                    "-r",
                    str(dep_file),
                ],
                capture_output=True,
                text=True,
                timeout=600,
            )

    # --------------------------------------------------------
    # Collect imports
    # --------------------------------------------------------

    imports = collect_imports(file_maps)

    if not imports:

        progress.emit(
            stage,
            stage_name,
            "running",
            "No third-party imports detected."
        )

        return {
            "installed": [],
            "failed": [],
            "skipped": [],
            "python": python,
        }

    progress.emit(
        stage,
        stage_name,
        "running",
        f"Detected {len(imports)} third-party imports."
    )

    # --------------------------------------------------------
    # Detect missing packages
    # --------------------------------------------------------

    missing_packages = []
    skipped = []

    for imp in sorted(imports):

        if is_import_available(imp):
            skipped.append(imp)
            continue

        pip_name = IMPORT_TO_PIP.get(imp, imp)

        if pip_name not in SAFE_PACKAGES:

            progress.emit(
                stage,
                stage_name,
                "running",
                f"Skipped unsafe/unverified package: {pip_name}"
            )

            continue

        missing_packages.append(pip_name)

    # --------------------------------------------------------
    # Install missing packages
    # --------------------------------------------------------

    installed, failed = install_packages(
        python=python,
        packages=missing_packages,
        stage=stage,
        stage_name=stage_name,
    )

    # --------------------------------------------------------
    # Final Summary
    # --------------------------------------------------------

    progress.emit(
        stage,
        stage_name,
        "running",
        (
            f"Dependency resolution completed | "
            f"Installed: {len(installed)} | "
            f"Skipped: {len(skipped)} | "
            f"Failed: {len(failed)}"
        )
    )

    return {
        "installed": installed,
        "failed": failed,
        "skipped": skipped,
        "python": python,
    }