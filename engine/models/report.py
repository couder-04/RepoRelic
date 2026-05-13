from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TestResult:
    test_file: str
    test_name: str
    status: str                         # "passed", "failed", "error"
    traceback: Optional[str] = None


@dataclass
class DiagnosisResult:
    function_name: str
    test_name: str
    why_failed: str
    is_real_bug: bool
    suggested_fix: str


@dataclass
class ReportData:
    target_path: str
    generated_at: str
    file_count: int = 0
    function_count: int = 0
    class_count: int = 0
    risky_function_count: int = 0
    static_issue_count: int = 0
    tests_generated: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    test_results: list[TestResult] = field(default_factory=list)
    diagnoses: list[DiagnosisResult] = field(default_factory=list)
