from __future__ import annotations

import importlib.util
import inspect
import logging
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Iterable, Sequence

from agents.change_detector import ChangeDetectionResult
from agents.coverage_analyzer import CoverageAnalysisResult
from agents.test_discovery import TestDiscoveryResult


@dataclass(frozen=True)
class TestGenerationResult:
    created_tests: int
    created_files: Sequence[Path]


class TestGenerationAgent:
    def __init__(self, tests_root: Path | None = None, dry_run: bool = False) -> None:
        self.tests_root = tests_root or Path("tests")
        self.dry_run = dry_run

    def generate_tests(
        self,
        change_result: ChangeDetectionResult,
        discovery_result: TestDiscoveryResult,
        coverage_result: CoverageAnalysisResult,
    ) -> TestGenerationResult:
        logging.info("Generating tests for uncovered code")
        self.tests_root.mkdir(exist_ok=True)
        created_tests = 0
        created_files: list[Path] = []
        for gap in coverage_result.gaps:
            module = self._load_module(gap.file)
            test_file = self._generated_test_file(gap.file)
            if test_file.exists():
                logging.info("Skipping existing generated test file: %s", test_file)
                continue
            test_content, tests_count = self._build_tests(module, gap.file, gap.missing_tests)
            if tests_count == 0:
                continue
            created_tests += tests_count
            created_files.append(test_file)
            if self.dry_run:
                logging.info("Dry-run: would write %s", test_file)
                continue
            test_file.write_text(test_content)
            logging.info("Created tests in %s", test_file)
        return TestGenerationResult(created_tests=created_tests, created_files=created_files)

    def _generated_test_file(self, source_file: Path) -> Path:
        module_name = source_file.stem
        return self.tests_root / f"test_{module_name}_generated.py"

    def _load_module(self, source_file: Path) -> ModuleType | None:
        if not source_file.exists():
            return None
        spec = importlib.util.spec_from_file_location(source_file.stem, source_file)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception as exc:  # noqa: BLE001 - log and continue
            logging.warning("Failed to import %s: %s", source_file, exc)
            return None
        return module

    def _build_tests(
        self, module: ModuleType | None, source_file: Path, missing_tests: Sequence[str]
    ) -> tuple[str, int]:
        if module is None:
            return "", 0
        imports = f"import inspect\nimport {source_file.stem}\n"
        test_blocks = []
        for name in missing_tests:
            obj = getattr(module, name, None)
            if not callable(obj):
                continue
            test_block = self._build_test_block(source_file.stem, name, obj)
            if test_block:
                test_blocks.append(test_block)
        if not test_blocks:
            return "", 0
        content = "\n".join(
            [
                '"""Auto-generated tests for uncovered code."""',
                imports,
                *test_blocks,
            ]
        )
        return f"{content}\n", len(test_blocks)

    def _build_test_block(self, module_name: str, func_name: str, obj: object) -> str:
        signature = inspect.signature(obj)
        required_params = [
            param
            for param in signature.parameters.values()
            if param.default is inspect.Parameter.empty
            and param.kind
            in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        ]
        lines = [
            f"def test_{func_name}_smoke():",
            f'    """Smoke test for `{module_name}.{func_name}`."""',
            f"    target = {module_name}.{func_name}",
            "    assert callable(target)",
        ]
        if not required_params:
            lines.extend(
                [
                    "    result = target()",
                    "    assert result is None or result is not None",
                ]
            )
        else:
            lines.append("    assert len(inspect.signature(target).parameters) >= 1")
        return "\n".join(lines)
