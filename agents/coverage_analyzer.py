from __future__ import annotations

import ast
import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Sequence

from agents.change_detector import ChangeDetectionResult


@dataclass(frozen=True)
class CoverageGap:
    file: Path
    missing_tests: Sequence[str]


@dataclass(frozen=True)
class CoverageAnalysisResult:
    gaps: Sequence[CoverageGap]
    coverage_report: Dict[str, float]


class CoverageAnalyzerAgent:
    def __init__(self, coverage_threshold: float = 0.8) -> None:
        self.coverage_threshold = coverage_threshold

    def analyze_coverage(self, change_result: ChangeDetectionResult) -> CoverageAnalysisResult:
        logging.info("Running coverage analysis")
        coverage_json = Path("coverage.json")
        if not self._has_tests():
            logging.warning("No tests collected; skipping coverage run.")
            return CoverageAnalysisResult(gaps=[], coverage_report={})

        self._run_pytest_with_coverage()

        if not coverage_json.exists():
            logging.warning("Coverage report not found.")
            return CoverageAnalysisResult(gaps=[], coverage_report={})

        report = json.loads(coverage_json.read_text())
        files_report = report.get("files", {})
        coverage_summary = {
            file_path: data.get("summary", {}).get("percent_covered", 0.0)
            for file_path, data in files_report.items()
        }
        gaps = []
        for change in change_result.changes:
            file_key = str(change.file_path)
            file_data = files_report.get(file_key, {})
            missing_lines = set(file_data.get("missing_lines", []))
            missing_defs = self._map_missing_lines_to_defs(change.file_path, missing_lines)
            if missing_defs:
                logging.info("Coverage gaps in %s: %s", change.file_path, missing_defs)
                gaps.append(CoverageGap(file=change.file_path, missing_tests=missing_defs))
        return CoverageAnalysisResult(gaps=gaps, coverage_report=coverage_summary)

    def _has_tests(self) -> bool:
        command = ["pytest", "--collect-only", "-q"]
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=False)
        except FileNotFoundError:
            logging.warning("pytest is not available.")
            return False
        output = result.stdout + result.stderr
        return "collected 0 items" not in output

    def _run_pytest_with_coverage(self) -> None:
        command = ["pytest", "--cov=src", "--cov-report=json"]
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=False)
            if result.returncode != 0:
                logging.warning("pytest failed: %s", result.stderr.strip())
        except FileNotFoundError:
            logging.warning("pytest is not available.")

    def _map_missing_lines_to_defs(self, file_path: Path, missing_lines: set[int]) -> Sequence[str]:
        if not file_path.exists():
            return []
        try:
            tree = ast.parse(file_path.read_text())
        except (OSError, SyntaxError):
            return []

        missing_defs = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                start = node.lineno
                end = getattr(node, "end_lineno", start)
                if any(line in missing_lines for line in range(start, end + 1)):
                    missing_defs.append(node.name)
        return sorted(set(missing_defs))
