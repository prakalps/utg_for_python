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
    coverage_text: str


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
        coverage_text = self._run_pytest_with_coverage()

        if not coverage_json.exists():
            logging.warning("Coverage report not found.")
            bootstrap_gaps = self._bootstrap_gaps_from_src()
            return CoverageAnalysisResult(gaps=bootstrap_gaps, coverage_report={}, coverage_text=coverage_text)

        try:
            report = json.loads(coverage_json.read_text())
        except (OSError, json.JSONDecodeError):
            logging.warning("Coverage report could not be parsed.")
            bootstrap_gaps = self._bootstrap_gaps_from_src()
            return CoverageAnalysisResult(gaps=bootstrap_gaps, coverage_report={}, coverage_text=coverage_text)

        files_report = report.get("files", {})
        if not isinstance(files_report, dict) or not files_report:
            logging.warning("Coverage report did not include file data; using bootstrap gaps.")
            bootstrap_gaps = self._bootstrap_gaps_from_src()
            return CoverageAnalysisResult(gaps=bootstrap_gaps, coverage_report={}, coverage_text=coverage_text)
        coverage_summary = {
            file_path: data.get("summary", {}).get("percent_covered", 0.0)
            for file_path, data in files_report.items()
        }

        # Generate gaps for all source files under src/ that report missing lines.
        # Relying only on ChangeDetectionResult can miss uncovered modules when the goal is
        # full-project coverage.
        gaps: list[CoverageGap] = []
        for file_key, file_data_obj in files_report.items():
            if not isinstance(file_data_obj, dict):
                continue
            normalized_key = str(file_key).replace("\\", "/")
            file_path = Path(normalized_key)
            if file_path.suffix != ".py":
                continue
            if file_path.parts and file_path.parts[0] != "src":
                continue
            missing_lines = set(file_data_obj.get("missing_lines", []))
            if not missing_lines:
                continue
            missing_defs = self._map_missing_lines_to_defs(file_path, missing_lines)
            if missing_defs:
                logging.info("Coverage gaps in %s: %s", file_path, missing_defs)
                gaps.append(CoverageGap(file=file_path, missing_tests=missing_defs))
        return CoverageAnalysisResult(gaps=gaps, coverage_report=coverage_summary, coverage_text=coverage_text)

    def _bootstrap_gaps_from_src(self) -> Sequence[CoverageGap]:
        src_root = Path("src")
        if not src_root.exists():
            return []

        gaps: list[CoverageGap] = []
        for path in sorted(src_root.rglob("*.py")):
            missing_defs = self._map_missing_lines_to_defs(path, set(range(1, 10**9)))
            if missing_defs:
                gaps.append(CoverageGap(file=path, missing_tests=missing_defs))
        return gaps

    def _run_pytest_with_coverage(self) -> str:
        command = [
            self._python_executable(),
            "-m",
            "pytest",
            "--cov=src",
            "--cov-report=json",
            "--cov-report=term-missing",
        ]
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=False)
            if result.returncode != 0:
                combined = f"{result.stdout}\n{result.stderr}".strip()
                logging.warning("pytest failed: %s", combined)
            return result.stdout.strip()
        except FileNotFoundError:
            logging.warning("Python executable not available: %s", command[0])
            return ""

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
        for node in getattr(tree, "body", []):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                start = node.lineno
                end = getattr(node, "end_lineno", start)
                if any(line in missing_lines for line in range(start, end + 1)):
                    missing_defs.append(node.name)
        return sorted(set(missing_defs))
