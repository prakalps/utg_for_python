from __future__ import annotations

import logging
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ValidationResult:
    success: bool
    output: str


class ValidationAgent:
    def _python_executable(self) -> str:
        venv_python = Path(".venv") / "Scripts" / "python.exe"
        if venv_python.exists():
            return str(venv_python)
        return sys.executable

    def validate_tests(self) -> ValidationResult:
        logging.info("Running pytest validation")
        try:
            result = subprocess.run(
                [self._python_executable(), "-m", "pytest"],
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError:
            logging.warning("pytest is not available.")
            return ValidationResult(success=False, output="pytest not available")

        output = f"{result.stdout}\n{result.stderr}".strip()
        if result.returncode != 0:
            logging.warning("pytest failed: %s", output)
        return ValidationResult(success=result.returncode == 0, output=output)
