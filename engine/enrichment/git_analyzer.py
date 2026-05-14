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

    enriched = []
    for func in risky_funcs:
        func_copy = func.copy()
        func_copy["git_history"] = _analyze_function_history(func, target_path, cfg)
        enriched.append(func_copy)

    total_issues = sum(len(f["git_history"]["issues"]) for f in enriched)
    progress.emit(4, "Knowledge Graph", "running",
                  f"Git history: found {total_issues} historical issues across {len(enriched)} functions")

    return enriched


def _is_git_repo(path: str) -> bool:
    """Check if path is a git repository."""
    if os.path.isfile(path):
        cwd = os.path.dirname(path)
    else:
        cwd = path
        
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


def _analyze_function_history(func: dict[str, Any], repo_path: str, cfg: Config) -> dict[str, Any]:
    """
    Analyze git history for a specific function.

    Returns dict with:
    - commit_count: number of commits touching this function
    - volatility_score: 0-10 score based on commit frequency and error patterns
    - issues: list of extracted issue descriptions from commit messages
    - error_types: counter of error types mentioned in commits
    """
    file_path = func["abs_path"]
    func_name = func["name"]
    start_line = func["lineno"]
    end_line = func["end_lineno"]

    # Get git log for this file with line ranges
    try:
        if os.path.isfile(repo_path):
            cwd = os.path.dirname(repo_path)
        else:
            cwd = repo_path
            
        # Get commits that touched lines in this function's range
        cmd = [
            "git", "log",
            "--oneline",
            f"-L{start_line},{end_line}:{file_path}",
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
        r"fix(?:ed|es|ing)? (.+?)(?:\s*[.!?]|$)",
        r"bug(?:\s*fix)? (.+?)(?:\s*[.!?]|$)",
        r"error (.+?)(?:\s*[.!?]|$)",
        r"issue (.+?)(?:\s*[.!?]|$)",
        r"problem (.+?)(?:\s*[.!?]|$)",
        r"resolve (.+?)(?:\s*[.!?]|$)",
        r"handle (.+?)(?:\s*[.!?]|$)",
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