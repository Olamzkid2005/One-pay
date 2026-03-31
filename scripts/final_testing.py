#!/usr/bin/env python3
"""
Final Comprehensive Testing Script for KoraPay Integration

This script runs all tests and generates a comprehensive report.

Requirements: 42.1, 42.2, 42.3, 42.4, 42.5
"""

import json
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))


@dataclass
class TestSuiteResult:
    """Result of a test suite."""
    suite_name: str
    total_tests: int
    passed: int
    failed: int
    skipped: int
    duration_seconds: float
    errors: list[str] = field(default_factory=list)
    failures: list[dict] = field(default_factory=list)


@dataclass
class ComprehensiveTestReport:
    """Comprehensive test report."""
    timestamp: str
    duration_seconds: float
    total_tests: int
    total_passed: int
    total_failed: int
    total_skipped: int
    suites: list[TestSuiteResult] = field(default_factory=list)
    coverage_percent: Optional[float] = None


def run_pytest_suite(
    test_path: str,
    suite_name: str,
    verbose: bool = True
) -> TestSuiteResult:
    """Run a pytest test suite and return results."""
    print(f"\n{'='*60}")
    print(f"Running {suite_name}...")
    print(f"{'='*60}")

    start = time.time()

    cmd = [
        sys.executable, "-m", "pytest",
        test_path,
        "-v", "--tb=short",
        "--no-header",
        "-q"
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        duration = time.time() - start

        output = result.stdout + result.stderr

        total = passed = failed = skipped = 0
        failures = []

        for line in output.split("\n"):
            if " passed" in line or " failed" in line or " skipped" in line:
                parts = line.split()
                for i, part in enumerate(parts):
                    if part == "passed":
                        try:
                            passed = int(parts[i-1])
                            total += passed
                        except (IndexError, ValueError):
                            pass
                    if part == "failed":
                        try:
                            failed = int(parts[i-1])
                            total += failed
                        except (IndexError, ValueError):
                            pass
                    if part == "skipped":
                        try:
                            skipped = int(parts[i-1])
                            total += skipped
                        except (IndexError, ValueError):
                            pass

        if total == 0:
            total = passed + failed + skipped

        print(f"Results: {passed} passed, {failed} failed, {skipped} skipped ({duration:.1f}s)")

        return TestSuiteResult(
            suite_name=suite_name,
            total_tests=total,
            passed=passed,
            failed=failed,
            skipped=skipped,
            duration_seconds=duration,
            failures=failures
        )

    except Exception as e:
        duration = time.time() - start
        print(f"Error running suite: {e}")
        return TestSuiteResult(
            suite_name=suite_name,
            total_tests=0,
            passed=0,
            failed=0,
            skipped=0,
            duration_seconds=duration,
            errors=[str(e)]
        )


def run_unit_tests() -> TestSuiteResult:
    """Run unit tests."""
    return run_pytest_suite("tests/unit/", "Unit Tests")


def run_integration_tests() -> TestSuiteResult:
    """Run integration tests."""
    return run_pytest_suite("tests/integration/", "Integration Tests")


def run_property_tests() -> TestSuiteResult:
    """Run property-based tests."""
    return run_pytest_suite("tests/property/", "Property-Based Tests")


def run_security_tests() -> TestSuiteResult:
    """Run security tests."""
    return run_pytest_suite("tests/security/", "Security Tests")


def generate_report(suites: list[TestSuiteResult]) -> ComprehensiveTestReport:
    """Generate comprehensive test report."""
    total_tests = sum(s.total_tests for s in suites)
    total_passed = sum(s.passed for s in suites)
    total_failed = sum(s.failed for s in suites)
    total_skipped = sum(s.skipped for s in suites)
    total_duration = sum(s.duration_seconds for s in suites)

    report = ComprehensiveTestReport(
        timestamp=datetime.now(timezone.utc).isoformat(),
        duration_seconds=total_duration,
        total_tests=total_tests,
        total_passed=total_passed,
        total_failed=total_failed,
        total_skipped=total_skipped,
        suites=suites
    )

    return report


def print_report(report: ComprehensiveTestReport) -> None:
    """Print formatted test report."""
    print("\n")
    print("="*70)
    print("COMPREHENSIVE TEST REPORT")
    print("="*70)
    print(f"Timestamp: {report.timestamp}")
    print(f"Total Duration: {report.duration_seconds:.1f}s")
    print()
    print(f"{'Suite':<30} {'Passed':<10} {'Failed':<10} {'Skipped':<10} {'Duration':<10}")
    print("-"*70)

    for suite in report.suites:
        print(f"{suite.suite_name:<30} {suite.passed:<10} {suite.failed:<10} "
              f"{suite.skipped:<10} {suite.duration_seconds:<10.1f}s")

    print("-"*70)
    print(f"{'TOTAL':<30} {report.total_passed:<10} {report.total_failed:<10} "
          f"{report.total_skipped:<10} {report.duration_seconds:<10.1f}s")
    print()

    if report.total_failed > 0:
        print("❌ SOME TESTS FAILED")
    elif report.total_skipped > 0:
        print("⚠️  TESTS PASSED (with skipped)")
    else:
        print("✅ ALL TESTS PASSED")

    print()


def save_report(report: ComprehensiveTestReport, filepath: str) -> None:
    """Save report to JSON file."""
    report_dict = {
        "timestamp": report.timestamp,
        "duration_seconds": report.duration_seconds,
        "total_tests": report.total_tests,
        "total_passed": report.total_passed,
        "total_failed": report.total_failed,
        "total_skipped": report.total_skipped,
        "suites": [
            {
                "suite_name": s.suite_name,
                "total_tests": s.total_tests,
                "passed": s.passed,
                "failed": s.failed,
                "skipped": s.skipped,
                "duration_seconds": s.duration_seconds,
                "errors": s.errors,
                "failures": s.failures
            }
            for s in report.suites
        ]
    }

    with open(filepath, "w") as f:
        json.dump(report_dict, f, indent=2)

    print(f"Report saved to: {filepath}")


def main():
    """Run all test suites and generate report."""
    print("="*70)
    print("KORAPAY INTEGRATION - COMPREHENSIVE TESTING")
    print("="*70)
    print(f"Started at: {datetime.now(timezone.utc).isoformat()}")

    suites = []

    suite_configs = [
        ("tests/unit/", "Unit Tests"),
        ("tests/integration/", "Integration Tests"),
        ("tests/property/", "Property-Based Tests"),
        ("tests/security/", "Security Tests"),
    ]

    for test_path, suite_name in suite_configs:
        test_dir = Path(test_path)
        if test_dir.exists():
            result = run_pytest_suite(test_path, suite_name)
            suites.append(result)
        else:
            print(f"Skipping {suite_name} - directory not found")

    report = generate_report(suites)
    print_report(report)

    report_path = Path(__file__).parent.parent / "test_report.json"
    save_report(report, str(report_path))

    if report.total_failed > 0:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())