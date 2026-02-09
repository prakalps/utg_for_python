from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class ValidationResult:
    success: bool
    output: str


class ValidationAgent:
    def validate_tests(self) -> ValidationResult:
        logging.info("Running pytest validation")
        if not self._has_tests():
            logging.warning("No tests collected; skipping pytest run.")
            return ValidationResult(success=True, output="No tests collected.")
        try:
            result = subprocess.run(
                ["pytest"],
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError:
            logging.warning("pytest is not available.")
            return ValidationResult(success=False, output="pytest not available")

        output = f"{result.stdout}\n{result.stderr}".strip()
        if result.returncode != 0:
            logging.warning("pytest failed.")
        return ValidationResult(success=result.returncode == 0, output=output)

    def _has_tests(self) -> bool:
        command = ["pytest", "--collect-only", "-q"]
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=False)
        except FileNotFoundError:
            logging.warning("pytest is not available.")
            return False
        output = result.stdout + result.stderr
        return "collected 0 items" not in output
