from dataclasses import dataclass, field
from typing import Optional


@dataclass
class StaticIssue:
    file: str
    line: int
    code: str                    # e.g. "W0611", "C901", "bare-except"
    message: str
    severity: str                # "error", "warning", "convention", "refactor"
    tool: str                    # "pylint", "pyflakes", "ast", "radon"


@dataclass
class ComplexityScore:
    function_name: str
    file: str
    lineno: int
    score: int                   # cyclomatic complexity value
    rank: str                    # A/B/C/D/E/F


@dataclass
class AnalysisResult:
    issues: list[StaticIssue] = field(default_factory=list)
    complexity_scores: list[ComplexityScore] = field(default_factory=list)
