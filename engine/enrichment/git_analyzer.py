"""
Git history analysis for enriching knowledge graph with historical bug patterns.
"""

import os
import re
import subprocess
from collections import Counter
from typing import Any, Dict, List, Optional

from ..config import Config
import engine.progress as progress


def enrich_with_git_history(
    risky_funcs: list[dict[str, Any]],
    target_path: str,
    cfg: Config,
) -> list[dict[str, Any]]:
    """
    Enrich risky functions with historical git data.

    Parameters
    ----------
    risky_funcs : list of function dicts from Stage 4
    target_path : absolute path to target codebase
    cfg         : config object

    Returns
    -------
    enriched_funcs : same list with added 'git_history' key
    """
    if not cfg.include_git_history:
        progress.emit(4, "Knowledge Graph", "running",
                      "Git history enrichment disabled in config")
        return risky_funcs

    if not _is_git_repo(target_path):
        progress.emit(4, "Knowledge Graph", "running",
                      "Git history: not a git repository, skipping enrichment")
        return risky_funcs

    progress.emit(4, "Knowledge Graph", "running",
                  "Analyzing git history for historical bug patterns...")

    # Find the git root once to calculate relative paths later
    git_root = _get_git_root(target_path)

    enriched = []
    for func in risky_funcs:
        func_copy = func.copy()
        func_copy["git_history"] = _analyze_function_history(func, target_path, git_root, cfg)
        enriched.append(func_copy)

    total_issues = sum(len(f["git_history"]["issues"]) for f in enriched)
    progress.emit(4, "Knowledge Graph", "running",
                  f"Git history: found {total_issues} historical issues across {len(enriched)} functions")

    return enriched


def _is_git_repo(path: str) -> bool:
    """Check if path is a git repository."""
    cwd = os.path.dirname(path) if os.path.isfile(path) else path
        
    try:
        subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=cwd,
            capture_output=True,
            check=True,
            timeout=10,
        )
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _get_git_root(path: str) -> Optional[str]:
    """Get the root of the git repository."""
    cwd = os.path.dirname(path) if os.path.isfile(path) else path
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return None


def _analyze_function_history(func: dict[str, Any], repo_path: str, git_root: Optional[str], cfg: Config) -> dict[str, Any]:
    """
    Analyze git history for a specific function.
    """
    abs_file_path = func["abs_path"]
    func_name = func["name"]
    start_line = func["lineno"]
    end_line = func["end_lineno"]

    # Calculate relative path for git -L
    # Git on Windows handles forward slashes much better for -L arguments
    if git_root:
        try:
            rel_path = os.path.relpath(abs_file_path, git_root).replace(os.sep, "/")
            cwd = git_root
        except ValueError:
            # Fallback if paths are on different drives on Windows
            rel_path = abs_file_path.replace(os.sep, "/")
            cwd = os.path.dirname(repo_path) if os.path.isfile(repo_path) else repo_path
    else:
        rel_path = abs_file_path.replace(os.sep, "/")
        cwd = os.path.dirname(repo_path) if os.path.isfile(repo_path) else repo_path

    # Get git log for this file with line ranges
    try:
        # Get commits that touched lines in this function's range
        # -s suppresses the diff output, giving us clean commit headers
        cmd = [
            "git", "log",
            "--oneline",
            "-s",
            f"-L{start_line},{end_line}:{rel_path}",
            f"--max-count={cfg.git_history_depth}",
        ]
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            # Silent failure for individual functions is okay, but we could log it
            # print(f"Git log failed for {rel_path}: {result.stderr}")
            return _empty_history()

        commits = result.stdout.strip().split("\n") if result.stdout.strip() else []

    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        return _empty_history()

    commit_count = len([c for c in commits if c.strip()])

    # Extract issues from commit messages
    issues = []
    error_types = Counter()

    for commit in commits:
        if not commit.strip():
            continue
        # Skip the commit hash, get the message
        parts = commit.split(" ", 1)
        if len(parts) < 2:
            continue
        message = parts[1].lower()

        extracted = _extract_issues_from_commit(message)
        issues.extend(extracted)

        # Count error types
        for issue in extracted:
            if "error" in issue.lower():
                error_types["error"] += 1
            elif "bug" in issue.lower() or "fix" in issue.lower():
                error_types["bug/fix"] += 1
            elif "exception" in issue.lower():
                error_types["exception"] += 1
            elif "fail" in issue.lower():
                error_types["failure"] += 1

    # Calculate volatility score (0-10)
    # Based on commit count, error mentions, and recency
    base_score = min(commit_count / 5, 5)  # 0-5 for frequency
    error_bonus = min(len(issues) / 3, 3)  # 0-3 for error patterns
    recency_bonus = 2 if commit_count > 0 and len(issues) > 0 else 0  # +2 if recent issues

    volatility_score = int(base_score + error_bonus + recency_bonus)

    return {
        "commit_count": commit_count,
        "volatility_score": volatility_score,
        "issues": issues[:10],  # Limit to top 10 issues
        "error_types": dict(error_types.most_common(5)),  # Top 5 error types
    }


def _extract_issues_from_commit(message: str) -> list[str]:
    """Extract issue descriptions from commit message."""
    issues = []

    # Common patterns for bug-related commits
    patterns = [
        r"fix(?:ed|es|ing)?[:\s]+(.+?)(?:\s*[.!?]|$)",
        r"bug(?:\s*fix)?[:\s]+(.+?)(?:\s*[.!?]|$)",
        r"error[:\s]+(.+?)(?:\s*[.!?]|$)",
        r"issue[:\s]+(.+?)(?:\s*[.!?]|$)",
        r"problem[:\s]+(.+?)(?:\s*[.!?]|$)",
        r"resolve[:\s]+(.+?)(?:\s*[.!?]|$)",
        r"handle[:\s]+(.+?)(?:\s*[.!?]|$)",
    ]

    for pattern in patterns:
        matches = re.findall(pattern, message, re.IGNORECASE)
        for match in matches:
            clean_issue = match.strip()
            if len(clean_issue) > 5 and clean_issue not in issues:
                issues.append(clean_issue)

    # Also look for common error keywords
    error_keywords = ["null", "none", "empty", "invalid", "timeout", "crash", "hang", "memory", "leak"]
    for keyword in error_keywords:
        if keyword in message and not any(keyword in issue for issue in issues):
            issues.append(f"related to {keyword}")

    return issues


def _empty_history() -> dict[str, Any]:
    """Return empty git history dict."""
    return {
        "commit_count": 0,
        "volatility_score": 0,
        "issues": [],
        "error_types": {},
    }