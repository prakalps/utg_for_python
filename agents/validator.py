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
