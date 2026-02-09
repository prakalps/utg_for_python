from __future__ import annotations

import ast
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Sequence


@dataclass(frozen=True)
class TestDiscoveryResult:
    tests_by_source: Dict[Path, Sequence[str]]
    test_files: Sequence[Path]


class TestDiscoveryAgent:
    def __init__(self, tests_root: Path | None = None) -> None:
        self.tests_root = tests_root or Path("tests")

    def discover_tests(self) -> TestDiscoveryResult:
        logging.info("Discovering tests in %s", self.tests_root)
        test_files = sorted(self.tests_root.glob("test_*.py"))
        tests_by_source: Dict[Path, Sequence[str]] = {}
        for test_file in test_files:
            mapped_source = self._map_source_file(test_file)
            tests_by_source[mapped_source] = self._parse_tests(test_file)
        return TestDiscoveryResult(tests_by_source=tests_by_source, test_files=test_files)

    def _map_source_file(self, test_file: Path) -> Path:
        module_name = test_file.stem.replace("test_", "")
        return Path("src") / f"{module_name}.py"

    def _parse_tests(self, test_file: Path) -> Sequence[str]:
        try:
            tree = ast.parse(test_file.read_text())
        except (OSError, SyntaxError):
            logging.warning("Failed to parse %s", test_file)
            return []
        test_names = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                test_names.append(node.name)
        return sorted(test_names)
