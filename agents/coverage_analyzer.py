from __future__ import annotations

import ast
import json
import logging
import subprocess
import sys
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

    def _python_executable(self) -> str:
        venv_python = Path(".venv") / "Scripts" / "python.exe"
        if venv_python.exists():
            return str(venv_python)
        return sys.executable

    def analyze_coverage(self, change_result: ChangeDetectionResult) -> CoverageAnalysisResult:
        logging.info("Running coverage analysis")
        coverage_json = Path("coverage.json")
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
            file_data = self._lookup_file_data(files_report, change.file_path)
            missing_lines = set(file_data.get("missing_lines", []))
            missing_defs = self._map_missing_lines_to_defs(change.file_path, missing_lines)
            if missing_defs:
                logging.info("Coverage gaps in %s: %s", change.file_path, missing_defs)
                gaps.append(CoverageGap(file=change.file_path, missing_tests=missing_defs))
        return CoverageAnalysisResult(gaps=gaps, coverage_report=coverage_summary)

    def _run_pytest_with_coverage(self) -> None:
        command = [
            self._python_executable(),
            "-m",
            "pytest",
            "--cov=src",
            "--cov-report=json",
        ]
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=False)
            if result.returncode != 0:
                combined = f"{result.stdout}\n{result.stderr}".strip()
                logging.warning("pytest failed: %s", combined)
        except FileNotFoundError:
            logging.warning("Python executable not available: %s", command[0])

    def _lookup_file_data(self, files_report: Dict[str, object], file_path: Path) -> Dict[str, object]:
        candidates = [
            str(file_path),
            file_path.as_posix(),
        ]
        normalized = []
        for candidate in candidates:
            if candidate:
                normalized.append(candidate)
                normalized.append(candidate.replace("/", "\\"))
                normalized.append(candidate.replace("\\", "/"))

        for key in normalized:
            file_data = files_report.get(key)
            if isinstance(file_data, dict):
                return file_data
        return {}

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
