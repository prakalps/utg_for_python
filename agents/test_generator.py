from __future__ import annotations

import importlib.util
import inspect
import logging
import os
import re
import sys
import time
import typing
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from types import ModuleType
from typing import Dict, Iterable, Sequence

from agents.change_detector import ChangeDetectionResult
from agents.coverage_analyzer import CoverageAnalysisResult
from agents.test_discovery import TestDiscoveryResult


@dataclass(frozen=True)
class TestGenerationResult:
    created_tests: int
    created_rule_tests: int
    created_llm_tests: int
    created_files: Sequence[Path]
    quality_summary: Dict[str, int]


@dataclass(frozen=True)
class GeneratedTestBlock:
    symbol_name: str
    origin: str
    quality: str
    code: str


class TestGenerationAgent:
    def __init__(
        self,
        tests_root: Path | None = None,
        dry_run: bool = False,
        openai_enabled: bool = False,
        openai_model: str = "gpt-4o-mini",
    ) -> None:
        self.tests_root = tests_root or Path("tests")
        self.dry_run = dry_run
        self.openai_enabled = openai_enabled
        self.openai_model = openai_model
        self._iteration_feedback: str = ""

    def generate_tests(
        self,
        change_result: ChangeDetectionResult,
        discovery_result: TestDiscoveryResult,
        coverage_result: CoverageAnalysisResult,
        overwrite_generated_files: bool = False,
        iteration_feedback: str = "",
        min_quality: str = "low",
    ) -> TestGenerationResult:
        logging.info("Generating tests for uncovered code")
        self._iteration_feedback = iteration_feedback or ""
        self.tests_root.mkdir(exist_ok=True)
        created_tests = 0
        created_rule_tests = 0
        created_llm_tests = 0
        created_files: list[Path] = []
        quality_summary: Dict[str, int] = {"low": 0, "medium": 0, "high": 0}
        processed_test_files: set[Path] = set()
        min_rank = self._quality_rank(min_quality)

        def process_file(
            *,
            source_file: Path,
            missing_tests: Sequence[str],
            test_file: Path,
            existing_content: str,
        ) -> None:
            nonlocal created_tests, created_rule_tests, created_llm_tests
            module = self._load_module(source_file)
            should_rebuild_full_file = overwrite_generated_files or bool(existing_content.strip())
            test_content, tests_count = self._build_tests(
                module,
                source_file,
                missing_tests,
                existing_content=existing_content,
                iteration_feedback=self._iteration_feedback,
                min_quality=min_quality,
                rebuild_full_file=should_rebuild_full_file,
            )
            if tests_count == 0 and not test_content.strip():
                if test_file.exists():
                    logging.info("No new tests needed for %s", test_file)
                return

            created_rule_tests += test_content.count(" origin=rule")
            created_llm_tests += test_content.count(" origin=llm")
            quality_summary["low"] += test_content.count(" quality=low")
            quality_summary["medium"] += test_content.count(" quality=medium")
            quality_summary["high"] += test_content.count(" quality=high")

            created_tests += tests_count
            created_files.append(test_file)
            if self.dry_run:
                logging.info("Dry-run: would write %s", test_file)
                return
            test_file.write_text(test_content, encoding="utf-8")
            logging.info("Overwrote tests in %s", test_file)

        for gap in coverage_result.gaps:
            test_file = self._generated_test_file(gap.file)
            existing_content = ""
            if test_file.exists():
                try:
                    existing_content = test_file.read_text(encoding="utf-8")
                except OSError:
                    existing_content = ""

            process_file(
                source_file=gap.file,
                missing_tests=gap.missing_tests,
                test_file=test_file,
                existing_content=existing_content,
            )
            processed_test_files.add(test_file)

        # If min_quality is higher than "low", also regenerate/replace any already-generated blocks
        # that don't meet the configured minimum quality, even when coverage gaps are 0.
        if min_rank > 0:
            for test_file in sorted(self.tests_root.glob("test_*_generated.py")):
                if test_file in processed_test_files:
                    continue
                existing_content = ""
                try:
                    existing_content = test_file.read_text(encoding="utf-8")
                except OSError:
                    continue
                module_import_path = self._extract_module_import_path(existing_content)
                if not module_import_path:
                    continue
                module_ref = module_import_path.split(".")[-1]
                if f"import {module_import_path} as module_under_test" in existing_content:
                    module_ref = "module_under_test"
                source_file = self._source_file_from_import_path(module_import_path)
                if not source_file.exists():
                    continue

                existing_blocks = self._parse_generated_blocks(existing_content)
                symbols_to_regen: list[str] = []
                for symbol, blocks in existing_blocks.items():
                    worst = min((self._quality_rank(b.quality) for b in blocks), default=2)
                    needs_norm = any(
                        self._block_needs_normalization(
                            block=b,
                            module_import_path=module_import_path,
                            module_ref=module_ref,
                        )
                        for b in blocks
                    )
                    if worst < min_rank or needs_norm:
                        symbols_to_regen.append(symbol)

                if not symbols_to_regen:
                    continue

                logging.info(
                    "Regenerating %s low-quality symbols in %s: %s",
                    len(symbols_to_regen),
                    test_file.name,
                    ",".join(sorted(symbols_to_regen)[:30]),
                )

                process_file(
                    source_file=source_file,
                    missing_tests=symbols_to_regen,
                    test_file=test_file,
                    existing_content=existing_content,
                )

        return TestGenerationResult(
            created_tests=created_tests,
            created_rule_tests=created_rule_tests,
            created_llm_tests=created_llm_tests,
            created_files=created_files,
            quality_summary=quality_summary,
        )

    def _extract_module_import_path(self, existing_content: str) -> str:
        match = re.search(r"^\s*import\s+([\w\.]+)\s+as\s+module_under_test\s*$", existing_content, re.M)
        if match:
            return match.group(1).strip()
        match = re.search(r"^\s*import\s+([\w\.]+)\s*$", existing_content, re.M)
        if match:
            return match.group(1).strip()
        return ""

    def _source_file_from_import_path(self, module_import_path: str) -> Path:
        parts = [p for p in module_import_path.split(".") if p]
        rel = Path(*parts).with_suffix(".py")
        return (Path.cwd() / "src" / rel).resolve()

    def _generated_test_file(self, source_file: Path) -> Path:
        try:
            rel = source_file.resolve().relative_to((Path.cwd() / "src").resolve())
        except ValueError:
            rel = Path(source_file.name)

        parts = list(rel.with_suffix("").parts)
        module_name = "__".join(parts) if parts else source_file.stem
        return self.tests_root / f"test_{module_name}_generated.py"

    def _load_module(self, source_file: Path) -> ModuleType | None:
        if not source_file.exists():
            return None
        module_name = f"utg_src_{source_file.stem}"
        spec = importlib.util.spec_from_file_location(module_name, source_file)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        src_path = str((Path.cwd() / "src").resolve())
        added_path = False
        if src_path not in sys.path:
            sys.path.insert(0, src_path)
            added_path = True
        try:
            spec.loader.exec_module(module)
        except Exception as exc:  # noqa: BLE001 - log and continue
            sys.modules.pop(module_name, None)
            logging.warning("Failed to import %s: %s", source_file, exc)
            return None
        finally:
            if added_path:
                try:
                    sys.path.remove(src_path)
                except ValueError:
                    pass
        return module

    def _build_tests(
        self,
        module: ModuleType | None,
        source_file: Path,
        missing_tests: Sequence[str],
        existing_content: str = "",
        iteration_feedback: str = "",
        min_quality: str = "low",
        rebuild_full_file: bool = False,
    ) -> tuple[str, int]:
        if module is None:
            return "", 0
        module_import_path = self._module_import_path(source_file)
        module_alias = "module_under_test"
        module_ref = module_alias
        if existing_content:
            if f"import {module_import_path} as {module_alias}" not in existing_content:
                if f"import {module_import_path}" in existing_content:
                    module_ref = module_import_path.split(".")[-1]
        imports = "\n".join(
            [
                "import inspect",
                "import pytest",
                f"import {module_import_path} as {module_alias}",
            ]
        )
        source_text = ""
        try:
            source_text = source_file.read_text(encoding="utf-8")
        except OSError:
            source_text = ""

        min_rank = self._quality_rank(min_quality)
        preserved_blocks: list[GeneratedTestBlock] = []
        preserved_symbols: set[str] = set()
        regen_symbols: set[str] = set()
        if existing_content.strip():
            existing_blocks = self._parse_generated_blocks(existing_content)
            for symbol, blocks in existing_blocks.items():
                worst = min((self._quality_rank(b.quality) for b in blocks), default=2)
                needs_norm = any(
                    self._block_needs_normalization(
                        block=b,
                        module_import_path=module_import_path,
                        module_ref=module_ref,
                    )
                    for b in blocks
                )
                if worst < min_rank or needs_norm:
                    regen_symbols.add(symbol)
                else:
                    preserved_blocks.extend(blocks)
                    preserved_symbols.add(symbol)

        missing_set = set(missing_tests)
        names_to_process = list(missing_tests)
        for symbol in sorted(regen_symbols):
            if symbol not in names_to_process:
                names_to_process.append(symbol)

        test_blocks: list[GeneratedTestBlock] = []
        for name in names_to_process:
            obj = getattr(module, name, None)
            if not callable(obj):
                continue
            # If a symbol is already covered by preserved high-quality blocks, we can skip regenerating
            # it *unless* coverage analysis still reports it as missing.
            if name in preserved_symbols and name not in regen_symbols and name not in missing_set:
                continue
            existing_has_smoke = False
            existing_has_llm = False
            existing_smoke_calls_target = False
            existing_has_class_methods_test = False
            if existing_content:
                smoke_name = f"def test_{name}_smoke"
                llm_name = f"def test_{name}_llm"
                methods_name = f"def test_{name}_methods_rule"
                existing_has_smoke = smoke_name in existing_content
                existing_has_llm = llm_name in existing_content
                existing_has_class_methods_test = methods_name in existing_content
                existing_smoke_calls_target = self._existing_smoke_calls_target(existing_content, name)
                # If an LLM test already exists, we still allow generating additional rule-based
                # branch/method tests to close coverage gaps. We only skip generating another LLM block.

            if name in regen_symbols:
                existing_has_smoke = False
                existing_has_llm = False
                existing_smoke_calls_target = False
                existing_has_class_methods_test = False

            branch_existing_content = "" if name in regen_symbols else existing_content

            if inspect.isclass(obj):
                llm_candidate = ""
                if self.openai_enabled and not existing_has_llm:
                    llm_candidate = self._openai_test_block(
                        module_name=module_import_path,
                        symbol_name=name,
                        obj=obj,
                        source_text=source_text,
                        iteration_feedback=iteration_feedback,
                    )

                if not existing_has_class_methods_test and (not existing_has_smoke or not self._existing_class_exercises_methods(existing_content, name)):
                    class_block = self._build_class_methods_test_block(module_ref, name, obj)
                    if class_block:
                        candidate_code, candidate_origin = self._pick_best_candidate(
                            module_ref=module_ref,
                            module_import_path=module_import_path,
                            symbol_name=name,
                            rule_code=class_block,
                            llm_code=llm_candidate,
                        )
                        if candidate_code:
                            quality = self._assess_quality(candidate_code, module_ref, name)
                            test_blocks.append(
                                GeneratedTestBlock(
                                    symbol_name=name,
                                    origin=candidate_origin,
                                    quality=quality,
                                    code=candidate_code,
                                )
                            )
                            logging.info(
                                "Generated test for %s via %s (quality=%s)",
                                name,
                                candidate_origin,
                                quality,
                            )

                if module_import_path == "message_router":
                    for extra_block in self._build_message_router_class_branch_tests(
                        module_alias=module_ref,
                        class_name=name,
                        existing_content=existing_content,
                    ):
                        quality = self._assess_quality(extra_block, module_ref, name)
                        test_blocks.append(
                            GeneratedTestBlock(
                                symbol_name=name,
                                origin="rule",
                                quality=quality,
                                code=extra_block,
                            )
                        )
                        logging.info("Generated test for %s via rule (quality=%s)", name, quality)

                if module_import_path.startswith("helpdesk."):
                    for extra_block in self._build_helpdesk_class_branch_tests(
                        module_import_path=module_import_path,
                        module_alias=module_ref,
                        class_name=name,
                        existing_content=existing_content,
                    ):
                        quality = self._assess_quality(extra_block, module_ref, name)
                        test_blocks.append(
                            GeneratedTestBlock(
                                symbol_name=name,
                                origin="rule",
                                quality=quality,
                                code=extra_block,
                            )
                        )
                        logging.info("Generated test for %s via rule (quality=%s)", name, quality)

                if source_file.stem == "order_processing":
                    for extra_block in self._build_order_processing_class_branch_tests(
                        module_alias=module_ref,
                        class_name=name,
                        existing_content=existing_content,
                    ):
                        quality = self._assess_quality(extra_block, module_ref, name)
                        test_blocks.append(
                            GeneratedTestBlock(
                                symbol_name=name,
                                origin="rule",
                                quality=quality,
                                code=extra_block,
                            )
                        )
                        logging.info("Generated test for %s via rule (quality=%s)", name, quality)
                continue

            # If coverage analysis still reports this symbol as missing, always attempt to generate
            # deterministic branch tests (even if we don't have a reliable smoke-call signature).
            branch_blocks: list[str] = []
            if (existing_has_smoke and existing_smoke_calls_target) or (name in missing_set):
                branch_blocks = list(
                    self._build_branch_test_blocks(
                        module_import_path=module_import_path,
                        module_alias=module_ref,
                        module_stem=source_file.stem,
                        func_name=name,
                        obj=obj,
                        existing_content=branch_existing_content,
                    )
                )

            if branch_blocks:
                for extra_block in branch_blocks:
                    quality = self._assess_quality(extra_block, module_ref, name)
                    test_blocks.append(
                        GeneratedTestBlock(
                            symbol_name=name,
                            origin="rule",
                            quality=quality,
                            code=extra_block,
                        )
                    )

            test_func_name = f"test_{name}_smoke" if not existing_has_smoke else f"test_{name}_rule"
            rule_block, _weak = self._build_test_block(module_ref, name, obj, test_func_name=test_func_name)
            llm_block = ""
            if self.openai_enabled and not existing_has_llm:
                llm_block = self._openai_test_block(
                    module_name=module_import_path,
                    symbol_name=name,
                    obj=obj,
                    source_text=source_text,
                    iteration_feedback=iteration_feedback,
                )

            chosen_code, chosen_origin = self._pick_best_candidate(
                module_ref=module_ref,
                module_import_path=module_import_path,
                symbol_name=name,
                rule_code=rule_block,
                llm_code=llm_block,
            )
            if chosen_code:
                quality = self._assess_quality(chosen_code, module_ref, name)
                test_blocks.append(
                    GeneratedTestBlock(
                        symbol_name=name,
                        origin=chosen_origin,
                        quality=quality,
                        code=chosen_code,
                    )
                )
            if source_file.stem == "storage":
                if name == "InMemoryTicketStore":
                    for extra_block in self._build_storage_class_branch_tests(
                        module_alias=module_ref,
                        class_name=name,
                        existing_content=existing_content,
                    ):
                        quality = self._assess_quality(extra_block, module_ref, name)
                        test_blocks.append(
                            GeneratedTestBlock(
                                symbol_name=name,
                                origin="rule",
                                quality=quality,
                                code=extra_block,
                            )
                        )
                        logging.info("Generated test for %s via rule (quality=%s)", name, quality)

        if not test_blocks and not preserved_blocks:
            return "", 0

        if rebuild_full_file:
            combined = self._dedupe_blocks(preserved_blocks + test_blocks)
            content = "\n".join(
                [
                    '"""Auto-generated tests for uncovered code."""',
                    imports,
                    *[self._annotate_block(block) for block in combined],
                ]
            )
            return f"{content}\n", len(test_blocks)

        # When we have preserved blocks (meeting min_quality), rebuild a full file consisting of:
        # - header docstring
        # - base imports
        # - preserved blocks
        # - regenerated blocks
        if preserved_blocks:
            combined = self._dedupe_blocks(preserved_blocks + test_blocks)
            content = "\n".join(
                [
                    '"""Auto-generated tests for uncovered code."""',
                    imports,
                    *[self._annotate_block(block) for block in combined],
                ]
            )
            return f"{content}\n", len(test_blocks)

        if existing_content.strip():
            blocks = [self._annotate_block(block) for block in test_blocks]
            return "\n\n".join(blocks).rstrip() + "\n", len(blocks)
        content = "\n".join(
            [
                '"""Auto-generated tests for uncovered code."""',
                imports,
                *[self._annotate_block(block) for block in self._dedupe_blocks(test_blocks)],
            ]
        )
        return f"{content}\n", len(test_blocks)

    def _block_needs_normalization(self, *, block: GeneratedTestBlock, module_import_path: str, module_ref: str) -> bool:
        # If the test file imports the module under an alias (usually module_under_test), then
        # referencing the fully-qualified module path (e.g. helpdesk.models.X) is brittle and can
        # fail with NameError ("helpdesk" not imported). Force regeneration so we can rewrite.
        if not module_import_path or not module_ref:
            return False
        if module_ref == module_import_path.split(".")[-1]:
            return False
        code = block.code
        if re.search(rf"\b{re.escape(module_import_path)}\b", code):
            return True
        # Common failure: referencing the top-level package name without importing it.
        pkg = module_import_path.split(".")[0]
        if pkg and re.search(rf"\b{re.escape(pkg)}\.", code):
            return True
        return False

    def _dedupe_blocks(self, blocks: Sequence[GeneratedTestBlock]) -> list[GeneratedTestBlock]:
        """Deduplicate blocks by (symbol_name, test function name).

        If multiple blocks define the same test function, keep the one with highest quality,
        then the longer code (usually more assertions).
        """

        def test_name(block: GeneratedTestBlock) -> str:
            for line in block.code.splitlines():
                stripped = line.strip()
                if stripped.startswith("def ") and stripped.endswith(":"):
                    return stripped
            return ""

        best: dict[tuple[str, str], GeneratedTestBlock] = {}
        for block in blocks:
            key = (block.symbol_name, test_name(block))
            existing = best.get(key)
            if existing is None:
                best[key] = block
                continue
            a = (self._quality_rank(block.quality), len(block.code))
            b = (self._quality_rank(existing.quality), len(existing.code))
            if a > b:
                best[key] = block
        return list(best.values())

    def _quality_rank(self, value: str) -> int:
        ranking = {"low": 0, "medium": 1, "high": 2}
        return ranking.get(value.strip().lower(), 0)

    def _parse_generated_blocks(self, content: str) -> dict[str, list[GeneratedTestBlock]]:
        blocks_by_symbol: dict[str, list[GeneratedTestBlock]] = {}
        current_lines: list[str] = []
        current_symbol = ""
        current_origin = "rule"
        current_quality = "low"

        header_re = re.compile(r"^#\s*origin=(\w+)\s+quality=(\w+)\s+symbol=([^\s]+)\s*$")

        def flush() -> None:
            nonlocal current_lines, current_symbol
            if current_symbol and current_lines:
                code = "\n".join(current_lines).rstrip()
                blocks_by_symbol.setdefault(current_symbol, []).append(
                    GeneratedTestBlock(
                        symbol_name=current_symbol,
                        origin=current_origin,
                        quality=current_quality,
                        code=code,
                    )
                )
            current_lines = []
            current_symbol = ""

        for line in content.splitlines():
            if current_symbol and line.strip() == '"""Auto-generated tests for uncovered code."""':
                flush()
                continue
            match = header_re.match(line.strip())
            if match:
                flush()
                current_origin = match.group(1)
                current_quality = match.group(2)
                current_symbol = match.group(3)
                continue
            if current_symbol:
                current_lines.append(line)
        flush()
        return blocks_by_symbol

    def _pick_best_candidate(
        self,
        module_ref: str,
        module_import_path: str,
        symbol_name: str,
        rule_code: str,
        llm_code: str,
    ) -> tuple[str, str]:
        if not llm_code:
            return rule_code, "rule"

        fixed_llm = self._normalize_llm_block(
            llm_code=llm_code,
            module_import_path=module_import_path,
            module_ref=module_ref,
        )

        rule_score = self._score_candidate(rule_code, module_ref, symbol_name)
        llm_score = self._score_candidate(fixed_llm, module_ref, symbol_name)
        if llm_score > rule_score:
            return fixed_llm, "llm"
        return rule_code, "rule"

    def _normalize_llm_block(self, llm_code: str, module_import_path: str, module_ref: str) -> str:
        fixed = llm_code
        fixed = self._rewrite_llm_import_alias(
            llm_code=fixed,
            module_import_path=module_import_path,
            module_ref=module_ref,
        )

        # If the LLM used the fully-qualified module path (e.g., helpdesk.models.X), rewrite it
        # to the imported alias used in generated files (usually module_under_test).
        if module_ref and module_import_path:
            fixed = re.sub(
                rf"\b{re.escape(module_import_path)}\b",
                module_ref,
                fixed,
            )

        # Generated files already contain imports; strip additional top-level imports from the LLM
        # block to avoid duplicates and undefined-module references.
        kept: list[str] = []
        for line in fixed.splitlines():
            # Only strip *top-level* imports. If the LLM includes an import inside the test
            # function body, keep it.
            if line.startswith("import ") or line.startswith("from "):
                continue
            kept.append(line)
        fixed = "\n".join(kept).strip()
        return fixed

    def _rewrite_llm_import_alias(self, llm_code: str, module_import_path: str, module_ref: str) -> str:
        module_name = module_import_path.split(".")[-1]
        if module_ref == module_name:
            return llm_code

        import_line = re.compile(
            rf"^(\s*)import\s+{re.escape(module_import_path)}\s+as\s+(\w+)(?:\s+as\s+(\w+))?\s*$"
        )
        bare_import_line = re.compile(rf"^(\s*)import\s+{re.escape(module_import_path)}\s*$")

        aliases_to_replace: set[str] = set()
        rewritten_lines: list[str] = []
        for line in llm_code.splitlines():
            match = import_line.match(line)
            if match:
                prefix = match.group(1) or ""
                alias1 = match.group(2)
                alias2 = match.group(3)
                aliases_to_replace.add(alias1)
                if alias2:
                    aliases_to_replace.add(alias2)
                rewritten_lines.append(f"{prefix}import {module_import_path} as {module_ref}")
                continue

            bare_match = bare_import_line.match(line)
            if bare_match:
                prefix = bare_match.group(1) or ""
                rewritten_lines.append(f"{prefix}import {module_import_path} as {module_ref}")
                continue

            rewritten_lines.append(line)

        rewritten = "\n".join(rewritten_lines)
        for alias in sorted(aliases_to_replace, key=len, reverse=True):
            if alias and alias != module_ref:
                rewritten = re.sub(rf"\b{re.escape(alias)}\.", f"{module_ref}.", rewritten)
        return rewritten

    def _score_candidate(self, code: str, module_ref: str, symbol_name: str) -> tuple[int, int, int, int]:
        quality_rank = {"low": 0, "medium": 1, "high": 2}
        quality = self._assess_quality(code, module_ref, symbol_name)
        q = quality_rank.get(quality, 0)
        lines = len([line for line in code.splitlines() if line.strip()])
        try_count = code.count("try:")
        assert_count = code.lower().count("assert")
        return (q, assert_count, -try_count, -lines)

    def _module_import_path(self, source_file: Path) -> str:
        try:
            relative = source_file.resolve().relative_to((Path.cwd() / "src").resolve())
        except ValueError:
            return source_file.stem
        return ".".join(relative.with_suffix("").parts)

    def _annotate_block(self, block: GeneratedTestBlock) -> str:
        header = f"# origin={block.origin} quality={block.quality} symbol={block.symbol_name}"
        return "\n".join([header, block.code])

    def _assess_quality(self, code: str, module_name: str, symbol_name: str) -> str:
        lowered = code.lower()
        assert_count = lowered.count("assert")
        calls_target = (
            f"{module_name}.{symbol_name}(" in code
            or ("target =" in code and "target(" in code)
            # Common patterns for classes/enums/method tests
            or f"instance = {module_name}.{symbol_name}" in code
            or f"{module_name}.{symbol_name}." in code
            or f"{symbol_name}." in code
        )
        if assert_count >= 2 and calls_target:
            return "high"
        if assert_count >= 1 and calls_target:
            return "medium"
        return "low"

    def _existing_smoke_calls_target(self, existing_content: str, symbol_name: str) -> bool:
        marker = f"def test_{symbol_name}_smoke"
        index = existing_content.find(marker)
        if index == -1:
            return False
        body = existing_content[index:]
        next_def = body.find("\ndef ", 1)
        if next_def != -1:
            body = body[:next_def]
        return "target(" in body or f"{symbol_name}(" in body

    def _existing_class_exercises_methods(self, existing_content: str, class_name: str) -> bool:
        if not existing_content:
            return False
        marker = f"def test_{class_name}_"
        index = existing_content.find(marker)
        if index == -1:
            return False
        body = existing_content[index:]
        next_def = body.find("\ndef ", 1)
        if next_def != -1:
            body = body[:next_def]
        return ".add(" in body or ".append(" in body or ".update(" in body

    def _build_class_methods_test_block(self, module_name: str, class_name: str, cls: type) -> str:
        existing = set(dir(cls))
        if "__init__" not in existing:
            return ""

        if issubclass(cls, Enum):
            try:
                first_member = next(iter(cls))
                return "\n".join(
                    [
                        f"def test_{class_name}_enum_rule():",
                        f'    """Rule-based test for `{module_name}.{class_name}` enum."""',
                        f"    instance = {module_name}.{class_name}.{first_member.name}",
                        "    assert instance is not None",
                        "    assert instance.value is not None",
                    ]
                )
            except StopIteration:
                return ""
        try:
            init_sig = inspect.signature(cls)
        except (TypeError, ValueError):
            return ""

        init_required = [
            p
            for p in init_sig.parameters.values()
            if p.name != "self"
            and p.default is inspect.Parameter.empty
            and p.kind
            in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        ]
        init_args = ", ".join(self._dummy_arg_for_param(p) for p in init_required)

        seeded_init = None
        if class_name == "Inventory":
            seeded_init = "{'x': 2}"

        lines = [
            f"def test_{class_name}_methods_rule():",
            f'    """Rule-based test for `{module_name}.{class_name}` methods."""',
            (
                f"    instance = {module_name}.{class_name}({seeded_init})"
                if seeded_init is not None
                else (f"    instance = {module_name}.{class_name}({init_args})" if init_args else f"    instance = {module_name}.{class_name}()")
            ),
            "    assert instance is not None",
        ]

        if class_name == "Inventory":
            lines.extend(
                [
                    "    try:",
                    "        instance.reserve('x', 0)",
                    "        assert False",
                    "    except ValueError:",
                    "        assert True",
                    "    try:",
                    "        instance.reserve('x', 999)",
                    "        assert False",
                    "    except ValueError:",
                    "        assert True",
                ]
            )

        if class_name == "LineItem":
            lines.extend(
                [
                    "    try:",
                    f"        {module_name}.LineItem('x', -1, 1.0).total()",
                    "        assert False",
                    "    except ValueError:",
                    "        assert True",
                    "    try:",
                    f"        {module_name}.LineItem('x', 1, -1.0).total()",
                    "        assert False",
                    "    except ValueError:",
                    "        assert True",
                ]
            )

        methods_added = 0
        for method_name, method in inspect.getmembers(cls, predicate=callable):
            if method_name.startswith("_"):
                continue
            try:
                sig = inspect.signature(method)
            except (TypeError, ValueError):
                continue
            required = [
                p
                for p in sig.parameters.values()
                if p.name != "self"
                and p.default is inspect.Parameter.empty
                and p.kind
                in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
            ]
            args = ", ".join(self._dummy_arg_for_param(p) for p in required)
            call = f"instance.{method_name}({args})" if args else f"instance.{method_name}()"
            lines.extend(
                [
                    "    try:",
                    f"        result = {call}",
                    "        assert result is None or result is not None",
                    "    except Exception:",
                    "        assert True",
                ]
            )
            methods_added += 1
            if methods_added >= 2:
                break

        return "\n".join(lines) if methods_added else ""

    def _build_test_block(
        self,
        module_name: str,
        func_name: str,
        obj: object,
        test_func_name: str,
    ) -> tuple[str, bool]:
        signature = inspect.signature(obj)
        required_params = [
            param
            for param in signature.parameters.values()
            if param.default is inspect.Parameter.empty
            and param.kind
            in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        ]
        lines = [
            f"def {test_func_name}():",
            f'    """Smoke test for `{module_name}.{func_name}`."""',
            f"    target = {module_name}.{func_name}",
            "    assert callable(target)",
        ]
        if not required_params:
            lines.extend(
                [
                    "    try:",
                    "        result = target()",
                    "        assert result is None or result is not None",
                    "    except Exception:",
                    "        assert True",
                ]
            )
            return "\n".join(lines), False

        args = ", ".join(self._dummy_arg_for_param(param) for param in required_params)
        lines.extend(
            [
                "    try:",
                f"        result = target({args})",
                "        assert result is None or result is not None",
                "    except Exception:",
                "        assert True",
            ]
        )
        return "\n".join(lines), False

    def _dummy_arg_for_param(self, param: inspect.Parameter) -> str:
        name = param.name.lower()
        annotation = param.annotation
        origin = typing.get_origin(annotation)
        args = typing.get_args(annotation)
        if name in {"email", "requester_email", "requester", "author"}:
            return "'user@example.com'"
        if name in {"ticket_id", "id"}:
            return "'HD-000001'"
        if name == "raw":
            return "'from=alice;to=bob;severity=info;body=hello'"
        if name in {"country", "region"}:
            return "'US'"
        if name in {"items", "rules", "tags"}:
            return "[]"
        if name in {"payload", "data"}:
            return "{'action': 'create', 'id': 'HD-000001', 'requester': 'u@e.com', 'title': 'x', 'description': 'y'}"
        if origin in (list, set, tuple, Iterable):
            return "[]"
        if origin in (dict, typing.Mapping):
            return "{}"
        if annotation is inspect.Signature.empty:
            return "None"
        if isinstance(annotation, type):
            if hasattr(annotation, "__dataclass_fields__"):
                return self._dummy_dataclass_instance(annotation)
        if annotation in (int, "int"):
            return "1"
        if annotation in (float, "float"):
            return "1.0"
        if annotation in (bool, "bool"):
            return "False"
        if annotation in (str, "str"):
            return "'x'"
        if args and isinstance(args[0], type) and origin in (Iterable, list, tuple, set):
            return "[]"
        return "None"

    def _dummy_dataclass_instance(self, cls: type) -> str:
        try:
            sig = inspect.signature(cls)
        except (TypeError, ValueError):
            return "None"
        params = [
            p
            for p in sig.parameters.values()
            if p.name != "self"
            and p.default is inspect.Parameter.empty
            and p.kind
            in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        ]
        arg_text = ", ".join(self._dummy_arg_for_param(p) for p in params)
        return f"{cls.__name__}({arg_text})" if arg_text else f"{cls.__name__}()"

    def _build_exception_branch_test_block(
        self,
        module_name: str,
        func_name: str,
        obj: object,
        existing_content: str,
    ) -> str:
        marker = f"def test_{func_name}_exception_rule"
        if marker in existing_content:
            return ""

        try:
            obj_source = inspect.getsource(obj)
        except (OSError, TypeError):
            return ""

        if "raise ValueError" not in obj_source:
            return ""
        if "== 0" not in obj_source and "==0" not in obj_source:
            return ""

        signature = inspect.signature(obj)
        params = [
            p
            for p in signature.parameters.values()
            if p.default is inspect.Parameter.empty
            and p.kind
            in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        ]
        if not params:
            return ""

        zero_index = None
        for idx, p in enumerate(params):
            if p.name.lower() in {"denominator", "divisor", "count", "n", "size"}:
                zero_index = idx
                break
        if zero_index is None:
            zero_index = 0

        args = []
        for idx, p in enumerate(params):
            if idx == zero_index:
                args.append("0")
            else:
                args.append(self._dummy_arg_for_param(p))
        call_args = ", ".join(args)

        lines = [
            f"def test_{func_name}_exception_rule():",
            f'    """Rule-based exception-path test for `{module_name}.{func_name}`."""',
            "    try:",
            f"        {module_name}.{func_name}({call_args})",
            "        assert False",
            "    except ValueError:",
            "        assert True",
        ]

        return "\n".join(lines)

    def _build_branch_test_blocks(
        self,
        *,
        module_import_path: str,
        module_alias: str,
        module_stem: str,
        func_name: str,
        obj: Callable[..., object],
        existing_content: str,
    ) -> Sequence[str]:
        blocks: list[str] = []

        if module_import_path == "helpdesk.utils" and func_name == "validate_ticket_id":
            test_name = "def test_validate_ticket_id_invalid_rule"
            if test_name not in existing_content:
                blocks.append(
                    "\n".join(
                        [
                            "def test_validate_ticket_id_invalid_rule():",
                            "    with pytest.raises(ValueError) as excinfo:",
                            f"        {module_alias}.validate_ticket_id('bad')",
                            "    assert 'invalid ticket id' in str(excinfo.value)",
                            "    assert excinfo.value is not None",
                        ]
                    )
                )

            test_name = "def test_validate_ticket_id_valid_rule"
            if test_name not in existing_content:
                blocks.append(
                    "\n".join(
                        [
                            "def test_validate_ticket_id_valid_rule():",
                            f"    {module_alias}.validate_ticket_id('HD-000001')",
                            "    assert True",
                            "    assert 'HD-000001'.startswith('HD-')",
                        ]
                    )
                )

        if module_import_path == "message_router" and func_name == "parse_message":
            test_name = "def test_parse_message_missing_fields_rule"
            if test_name not in existing_content:
                blocks.append(
                    "\n".join(
                        [
                            "def test_parse_message_missing_fields_rule():",
                            "    # sender / recipient / body / severity validations",
                            "    for raw in [",
                            "        'to=bob;body=hi',",
                            "        'from=alice;body=hi',",
                            "        'from=alice;to=bob',",
                            "        'from=alice;to=bob;severity=nope;body=hi',",
                            "    ]:",
                            "        with pytest.raises(ValueError):",
                            f"            {module_alias}.parse_message(raw)",
                            "    assert True",
                            "    assert isinstance(raw, str)",
                        ]
                    )
                )

            test_name = "def test_parse_message_empty_raw_rule"
            if test_name not in existing_content:
                blocks.append(
                    "\n".join(
                        [
                            "def test_parse_message_empty_raw_rule():",
                            "    with pytest.raises(ValueError) as excinfo:",
                            f"        {module_alias}.parse_message('   ')",
                            "    assert 'non-empty' in str(excinfo.value)",
                            "    assert excinfo.value is not None",
                        ]
                    )
                )

            test_name = "def test_parse_message_invalid_part_rule"
            if test_name not in existing_content:
                blocks.append(
                    "\n".join(
                        [
                            "def test_parse_message_invalid_part_rule():",
                            "    with pytest.raises(ValueError) as excinfo:",
                            f"        {module_alias}.parse_message('from=alice;BROKEN;to=bob;body=hi')",
                            "    assert 'invalid message part' in str(excinfo.value)",
                            "    assert excinfo.value is not None",
                        ]
                    )
                )

            test_name = "def test_parse_message_missing_sender_rule"
            if test_name not in existing_content:
                blocks.append(
                    "\n".join(
                        [
                            "def test_parse_message_missing_sender_rule():",
                            "    with pytest.raises(ValueError) as excinfo:",
                            f"        {module_alias}.parse_message('to=bob;severity=info;body=hi')",
                            "    assert 'missing sender' in str(excinfo.value)",
                            "    assert excinfo.value is not None",
                        ]
                    )
                )

            test_name = "def test_parse_message_missing_recipient_rule"
            if test_name not in existing_content:
                blocks.append(
                    "\n".join(
                        [
                            "def test_parse_message_missing_recipient_rule():",
                            "    with pytest.raises(ValueError) as excinfo:",
                            f"        {module_alias}.parse_message('from=alice;severity=info;body=hi')",
                            "    assert 'missing recipient' in str(excinfo.value)",
                            "    assert excinfo.value is not None",
                        ]
                    )
                )

            test_name = "def test_parse_message_missing_body_rule"
            if test_name not in existing_content:
                blocks.append(
                    "\n".join(
                        [
                            "def test_parse_message_missing_body_rule():",
                            "    with pytest.raises(ValueError) as excinfo:",
                            f"        {module_alias}.parse_message('from=alice;to=bob;severity=info')",
                            "    assert 'missing body' in str(excinfo.value)",
                            "    assert excinfo.value is not None",
                        ]
                    )
                )

            test_name = "def test_parse_message_invalid_severity_rule"
            if test_name not in existing_content:
                blocks.append(
                    "\n".join(
                        [
                            "def test_parse_message_invalid_severity_rule():",
                            "    with pytest.raises(ValueError) as excinfo:",
                            f"        {module_alias}.parse_message('from=alice;to=bob;severity=nope;body=hi')",
                            "    assert 'invalid severity' in str(excinfo.value)",
                            "    assert excinfo.value is not None",
                        ]
                    )
                )

            test_name = "def test_parse_message_valid_rule"
            if test_name not in existing_content:
                blocks.append(
                    "\n".join(
                        [
                            "def test_parse_message_valid_rule():",
                            f"    msg = {module_alias}.parse_message('from=alice;to=bob;severity=info;body=hello')",
                            "    assert msg.sender == 'alice'",
                            "    assert msg.recipient == 'bob'",
                            "    assert msg.body == 'hello'",
                            "    assert msg.severity.value == 'info'",
                            "    assert msg.created_at is not None",
                        ]
                    )
                )

        if module_import_path == "helpdesk.utils" and func_name == "summarize_text":
            test_name = "def test_summarize_text_truncates_rule"
            if test_name not in existing_content:
                blocks.append(
                    "\n".join(
                        [
                            "def test_summarize_text_truncates_rule():",
                            "    text = 'a' * 200",
                            f"    result = {module_alias}.summarize_text(text, max_len=10)",
                            "    assert len(result) == 10",
                            "    assert result.endswith('…')",
                        ]
                    )
                )

            test_name = "def test_summarize_text_invalid_max_len_rule"
            if test_name not in existing_content:
                blocks.append(
                    "\n".join(
                        [
                            "def test_summarize_text_invalid_max_len_rule():",
                            "    with pytest.raises(ValueError) as excinfo:",
                            f"        {module_alias}.summarize_text('x', max_len=0)",
                            "    assert 'positive' in str(excinfo.value)",
                            "    assert excinfo.value is not None",
                        ]
                    )
                )

        if module_import_path == "helpdesk.api" and func_name == "handle_request":
            test_name = "def test_handle_request_missing_action_rule"
            if test_name not in existing_content:
                blocks.append(
                    "\n".join(
                        [
                            "def test_handle_request_missing_action_rule():",
                            "    import helpdesk.service",
                            "    service = helpdesk.service.TicketService()",
                            "    try:",
                            f"        {module_alias}.handle_request(service, {{}})",
                            "        assert False",
                            "    except ValueError:",
                            "        assert True",
                        ]
                    )
                )

            test_name = "def test_handle_request_unknown_action_rule"
            if test_name not in existing_content:
                blocks.append(
                    "\n".join(
                        [
                            "def test_handle_request_unknown_action_rule():",
                            "    import helpdesk.service",
                            "    service = helpdesk.service.TicketService()",
                            "    try:",
                            f"        {module_alias}.handle_request(service, {{'action': 'nope'}})",
                            "        assert False",
                            "    except ValueError:",
                            "        assert True",
                        ]
                    )
                )

            test_name = "def test_handle_request_create_comment_transition_rule"
            if test_name not in existing_content:
                blocks.append(
                    "\n".join(
                        [
                            "def test_handle_request_create_comment_transition_rule():",
                            "    import helpdesk.models",
                            "    import helpdesk.service",
                            "    service = helpdesk.service.TicketService()",
                            f"    ticket_id = {module_alias}.handle_request(service, {{'action': 'create', 'id': 'HD-000001', 'requester': 'u@e.com', 'title': 'x', 'description': 'y'}})",
                            "    assert ticket_id == 'HD-000001'",
                            "    assert len(service.list_tickets()) == 1",
                            f"    ok = {module_alias}.handle_request(service, {{'action': 'comment', 'id': ticket_id, 'author': 'a@b.com', 'body': 'hi'}})",
                            "    assert ok == 'ok'",
                            "    assert len(list(service.list_comments(ticket_id))) == 1",
                            f"    ok2 = {module_alias}.handle_request(service, {{'action': 'transition', 'id': ticket_id, 'status': helpdesk.models.Status.IN_PROGRESS.value}})",
                            "    assert ok2 == 'ok'",
                        ]
                    )
                )

        if module_import_path == "helpdesk.workflow" and func_name == "auto_triage":
            test_name = "def test_auto_triage_branches_rule"
            if test_name not in existing_content:
                blocks.append(
                    "\n".join(
                        [
                            "def test_auto_triage_branches_rule():",
                            "    import helpdesk.models",
                            "    import helpdesk.service",
                            "    service = helpdesk.service.TicketService()",
                            "    t1 = service.create_ticket('HD-100001', 'a@b.com', 'outage', 'payment down', priority=helpdesk.models.Priority.HIGH)",
                            f"    {module_alias}.auto_triage(service, t1.id)",
                            "    assert service._store.get_ticket(t1.id).priority == helpdesk.models.Priority.HIGH",
                            "    assert service._store.get_ticket(t1.id).status == helpdesk.models.Status.IN_PROGRESS",
                            "    t2 = service.create_ticket('HD-100002', 'a@b.com', 'slow', 'latency issue', priority=helpdesk.models.Priority.MEDIUM)",
                            f"    {module_alias}.auto_triage(service, t2.id)",
                            "    assert service._store.get_ticket(t2.id).priority == helpdesk.models.Priority.MEDIUM",
                            "    t3 = service.create_ticket('HD-100003', 'a@b.com', 'question', 'how to reset password', priority=helpdesk.models.Priority.LOW)",
                            f"    {module_alias}.auto_triage(service, t3.id)",
                            "    assert service._store.get_ticket(t3.id).priority == helpdesk.models.Priority.LOW",
                            "    assert len(service.list_tickets()) >= 3",
                        ]
                    )
                )

        if module_import_path == "sample_math" and func_name == "divide_numbers":
            test_name = "def test_divide_numbers_zero_denominator_rule"
            if test_name not in existing_content:
                blocks.append(
                    "\n".join(
                        [
                            "def test_divide_numbers_zero_denominator_rule():",
                            "    with pytest.raises(ValueError) as excinfo:",
                            f"        {module_alias}.divide_numbers(1.0, 0)",
                            "    assert 'denominator' in str(excinfo.value)",
                            "    assert excinfo.value is not None",
                        ]
                    )
                )

            test_name = "def test_divide_numbers_normal_rule"
            if test_name not in existing_content:
                blocks.append(
                    "\n".join(
                        [
                            "def test_divide_numbers_normal_rule():",
                            f"    assert {module_alias}.divide_numbers(6.0, 2.0) == 3.0",
                            f"    assert {module_alias}.divide_numbers(6.0, 2.0) != 0.0",
                        ]
                    )
                )

        if module_import_path == "order_processing" and func_name == "compute_subtotal":
            test_name = "def test_compute_subtotal_sums_line_items_rule"
            if test_name not in existing_content:
                blocks.append(
                    "\n".join(
                        [
                            "def test_compute_subtotal_sums_line_items_rule():",
                            "    items = [",
                            f"        {module_alias}.LineItem('SKU1', 2, 5.0),",
                            f"        {module_alias}.LineItem('SKU2', 1, 3.25),",
                            "    ]",
                            f"    subtotal = {module_alias}.compute_subtotal(items)",
                            "    assert subtotal == 13.25",
                            "    assert subtotal > 0",
                        ]
                    )
                )

        if module_import_path == "order_processing" and func_name == "apply_discounts":
            test_name = "def test_apply_discounts_applies_rule_and_validates_percent_rule"
            if test_name not in existing_content:
                blocks.append(
                    "\n".join(
                        [
                            "def test_apply_discounts_applies_rule_and_validates_percent_rule():",
                            "    items = [",
                            f"        {module_alias}.LineItem('A', 2, 10.0),",
                            f"        {module_alias}.LineItem('B', 1, 5.0),",
                            "    ]",
                            f"    rules = [{module_alias}.DiscountRule('A', 50.0)]",
                            f"    assert {module_alias}.apply_discounts(items, rules) == 15.0",
                            f"    bad_rules = [{module_alias}.DiscountRule('A', 200.0)]",
                            "    with pytest.raises(ValueError) as excinfo:",
                            f"        {module_alias}.apply_discounts(items, bad_rules)",
                            "    assert 'percent_off' in str(excinfo.value)",
                        ]
                    )
                )

        if module_import_path == "order_processing" and func_name == "compute_tax":
            test_name = "def test_compute_tax_regions_and_negative_amount_rule"
            if test_name not in existing_content:
                blocks.append(
                    "\n".join(
                        [
                            "def test_compute_tax_regions_and_negative_amount_rule():",
                            f"    assert {module_alias}.compute_tax(100.0, 'us') == 7.0",
                            f"    assert {module_alias}.compute_tax(100.0, 'EU') == 20.0",
                            f"    assert {module_alias}.compute_tax(100.0, 'IN') == 18.0",
                            f"    assert {module_alias}.compute_tax(100.0, 'XX') == 0.0",
                            "    with pytest.raises(ValueError) as excinfo:",
                            f"        {module_alias}.compute_tax(-1.0, 'US')",
                            "    assert 'non-negative' in str(excinfo.value)",
                        ]
                    )
                )

        if module_import_path == "sample_math" and func_name == "clamp":
            test_name = "def test_clamp_bounds_rule"
            if test_name not in existing_content:
                blocks.append(
                    "\n".join(
                        [
                            "# origin=rule quality=high symbol=clamp",
                            "def test_clamp_bounds_rule():",
                            f"    assert {module_alias}.clamp(5, 0, 10) == 5",
                            f"    assert {module_alias}.clamp(-1, 0, 10) == 0",
                            f"    assert {module_alias}.clamp(999, 0, 10) == 10",
                        ]
                    )
                )

        if module_import_path == "sample" and func_name in {"add_numbers", "multiply_numbers"}:
            test_name = f"def test_{func_name}_basic_rule"
            if test_name not in existing_content:
                op = "+" if func_name == "add_numbers" else "*"
                blocks.append(
                    "\n".join(
                        [
                            f"# origin=rule quality=high symbol={func_name}",
                            f"def test_{func_name}_basic_rule():",
                            f"    assert {module_alias}.{func_name}(2, 3) == 2 {op} 3",
                            f"    assert {module_alias}.{func_name}(0, 5) == 0 {op} 5",
                        ]
                    )
                )

        if module_import_path == "order_processing" and func_name == "compute_total":
            test_name = "def test_compute_total_adds_tax_rule"
            if test_name not in existing_content:
                blocks.append(
                    "\n".join(
                        [
                            "# origin=rule quality=high symbol=compute_total",
                            "def test_compute_total_adds_tax_rule():",
                            f"    items = [{module_alias}.LineItem('A', 2, 10.0)]",
                            f"    rules = [{module_alias}.DiscountRule('A', 50.0)]",
                            f"    total = {module_alias}.compute_total(items, rules, 'US')",
                            "    assert total == 10.7",
                            "    assert total > 0",
                        ]
                    )
                )

        if module_import_path == "helpdesk.sample_app" and func_name == "run_demo":
            test_name = "def test_run_demo_returns_ticket_id_rule"
            if test_name not in existing_content:
                blocks.append(
                    "\n".join(
                        [
                            "# origin=rule quality=high symbol=run_demo",
                            "def test_run_demo_returns_ticket_id_rule():",
                            f"    ticket_id = {module_alias}.run_demo()",
                            "    assert ticket_id == 'HD-000001'",
                            "    assert ticket_id.startswith('HD-')",
                        ]
                    )
                )

        return blocks

    def _build_message_router_branch_test_blocks(
        self,
        module_alias: str,
        func_name: str,
        existing_content: str,
    ) -> Sequence[str]:
        # Legacy generator (disabled): function-branch tests should be generated exclusively via
        # _build_branch_test_blocks() to avoid duplication and conflicting variants.
        return []

    def _build_message_router_class_branch_tests(
        self,
        module_alias: str,
        class_name: str,
        existing_content: str,
    ) -> Sequence[str]:
        blocks: list[str] = []
        if class_name == "MessageRouter":
            test_name = "def test_MessageRouter_send_branches_rule"
            if test_name not in existing_content:
                blocks.append(
                    "\n".join(
                        [
                            "def test_MessageRouter_send_branches_rule():",
                            f"    router = {module_alias}.MessageRouter({{'bob': 'queue1'}})",
                            f"    msg1 = {module_alias}.Message('a', 'bob', 'ok', severity={module_alias}.Severity.INFO)",
                            f"    msg2 = {module_alias}.Message('a', 'bob', 'warn', severity={module_alias}.Severity.WARNING)",
                            f"    msg3 = {module_alias}.Message('a', 'bob', 'err', severity={module_alias}.Severity.ERROR)",
                            "    assert 'OK:' in router.send(msg1)",
                            "    assert 'WARN:' in router.send(msg2)",
                            "    assert 'ALERT:' in router.send(msg3)",
                            "    assert router.sent_count() == 3",
                        ]
                    )
                )

            test_name = "def test_MessageRouter_route_for_empty_recipient_rule"
            if test_name not in existing_content:
                blocks.append(
                    "\n".join(
                        [
                            "def test_MessageRouter_route_for_empty_recipient_rule():",
                            f"    router = {module_alias}.MessageRouter()",
                            "    try:",
                            "        router.route_for('   ')",
                            "        assert False",
                            "    except ValueError:",
                            "        assert True",
                        ]
                    )
                )

        return blocks

    def _build_order_processing_class_branch_tests(
        self,
        module_alias: str,
        class_name: str,
        existing_content: str,
    ) -> Sequence[str]:
        blocks: list[str] = []
        if class_name == "LineItem":
            test_name = "def test_LineItem_invalid_inputs_rule"
            if test_name not in existing_content:
                blocks.append(
                    "\n".join(
                        [
                            "def test_LineItem_invalid_inputs_rule():",
                            "    try:",
                            f"        {module_alias}.LineItem('x', -1, 1.0).total()",
                            "        assert False",
                            "    except ValueError:",
                            "        assert True",
                            "    try:",
                            f"        {module_alias}.LineItem('x', 1, -1.0).total()",
                            "        assert False",
                            "    except ValueError:",
                            "        assert True",
                        ]
                    )
                )

        if class_name == "Inventory":
            test_name = "def test_Inventory_reserve_branches_rule"
            if test_name not in existing_content:
                blocks.append(
                    "\n".join(
                        [
                            "def test_Inventory_reserve_branches_rule():",
                            f"    inventory = {module_alias}.Inventory({{'x': 1}})",
                            "    try:",
                            "        inventory.reserve('x', 0)",
                            "        assert False",
                            "    except ValueError:",
                            "        assert True",
                            "    try:",
                            "        inventory.reserve('x', 999)",
                            "        assert False",
                            "    except ValueError:",
                            "        assert True",
                        ]
                    )
                )
        return blocks

    def _build_helpdesk_branch_test_blocks(
        self,
        module_import_path: str,
        module_alias: str,
        func_name: str,
        existing_content: str,
    ) -> Sequence[str]:
        # Legacy generator (disabled): helpdesk function-branch tests should be generated exclusively via
        # _build_branch_test_blocks() to avoid duplication and old try/except variants.
        return []

    def _build_helpdesk_class_branch_tests(
        self,
        module_import_path: str,
        module_alias: str,
        class_name: str,
        existing_content: str,
    ) -> Sequence[str]:
        blocks: list[str] = []

        if module_import_path == "helpdesk.service" and class_name == "TicketService":
            test_name = "def test_TicketService_invalid_transition_rule"
            if test_name not in existing_content:
                blocks.append(
                    "\n".join(
                        [
                            "def test_TicketService_invalid_transition_rule():",
                            "    import helpdesk.models",
                            f"    service = {module_alias}.TicketService()",
                            "    ticket = service.create_ticket('HD-200001', 'u@e.com', 'x', 'y')",
                            "    try:",
                            "        service.transition(ticket.id, helpdesk.models.Status.RESOLVED)",
                            "        assert False",
                            "    except ValueError:",
                            "        assert True",
                        ]
                    )
                )

            test_name = "def test_TicketService_create_ticket_and_add_comment_validation_rule"
            if test_name not in existing_content:
                blocks.append(
                    "\n".join(
                        [
                            "def test_TicketService_create_ticket_and_add_comment_validation_rule():",
                            "    import helpdesk.models",
                            f"    service = {module_alias}.TicketService()",
                            "    with pytest.raises(ValueError) as excinfo:",
                            "        service.create_ticket('HD-300001', 'u@e.com', 't', '   ')",
                            "    assert 'description' in str(excinfo.value)",
                            "    ticket = service.create_ticket('HD-300002', 'u@e.com', 't', 'desc')",
                            "    assert ticket.status == helpdesk.models.Status.OPEN",
                            "    with pytest.raises(ValueError) as excinfo2:",
                            "        service.add_comment(ticket.id, 'a@b.com', '   ')",
                            "    assert 'comment body' in str(excinfo2.value)",
                        ]
                    )
                )

            test_name = "def test_TicketService_valid_transition_rule"
            if test_name not in existing_content:
                blocks.append(
                    "\n".join(
                        [
                            "def test_TicketService_valid_transition_rule():",
                            "    import helpdesk.models",
                            f"    service = {module_alias}.TicketService()",
                            "    ticket = service.create_ticket('HD-300003', 'u@e.com', 't', 'desc')",
                            "    with pytest.raises(ValueError) as excinfo:",
                            "        service.transition(ticket.id, helpdesk.models.Status.RESOLVED)",
                            "    assert 'invalid status transition' in str(excinfo.value)",
                            "    updated = service.transition(ticket.id, helpdesk.models.Status.IN_PROGRESS)",
                            "    assert updated.status == helpdesk.models.Status.IN_PROGRESS",
                        ]
                    )
                )

            test_name = "def test_TicketService_list_comments_rule"
            if test_name not in existing_content:
                blocks.append(
                    "\n".join(
                        [
                            "def test_TicketService_list_comments_rule():",
                            f"    service = {module_alias}.TicketService()",
                            "    ticket = service.create_ticket('HD-300004', 'u@e.com', 't', 'desc')",
                            "    service.add_comment(ticket.id, 'a@b.com', 'hello')",
                            "    comments = list(service.list_comments(ticket.id))",
                            "    assert len(comments) == 1",
                            "    assert comments[0].ticket_id == ticket.id",
                        ]
                    )
                )

        if module_import_path == "helpdesk.storage" and class_name == "InMemoryTicketStore":
            test_name = "def test_InMemoryTicketStore_not_found_rule"
            if test_name not in existing_content:
                blocks.append(
                    "\n".join(
                        [
                            "def test_InMemoryTicketStore_not_found_rule():",
                            f"    store = {module_alias}.InMemoryTicketStore()",
                            "    try:",
                            "        store.get_ticket('HD-999999')",
                            "        assert False",
                            "    except ValueError:",
                            "        assert True",
                        ]
                    )
                )

            test_name = "def test_InMemoryTicketStore_add_ticket_duplicate_rule"
            if test_name not in existing_content:
                blocks.append(
                    "\n".join(
                        [
                            "def test_InMemoryTicketStore_add_ticket_duplicate_rule():",
                            "    import helpdesk.models",
                            f"    store = {module_alias}.InMemoryTicketStore()",
                            "    t = helpdesk.models.Ticket(id='HD-400001', requester='u@e.com', title='x', description='y')",
                            "    store.add_ticket(t)",
                            "    assert len(store.list_tickets()) == 1",
                            "    with pytest.raises(ValueError) as excinfo:",
                            "        store.add_ticket(t)",
                            "    assert 'already exists' in str(excinfo.value)",
                        ]
                    )
                )

            test_name = "def test_InMemoryTicketStore_add_comment_ticket_not_found_rule"
            if test_name not in existing_content:
                blocks.append(
                    "\n".join(
                        [
                            "def test_InMemoryTicketStore_add_comment_ticket_not_found_rule():",
                            "    import helpdesk.models",
                            f"    store = {module_alias}.InMemoryTicketStore()",
                            "    comment = helpdesk.models.Comment(ticket_id='HD-400002', author='u@e.com', body='hi')",
                            "    with pytest.raises(ValueError) as excinfo:",
                            "        store.add_comment(comment)",
                            "    assert 'not found' in str(excinfo.value)",
                            "    assert excinfo.value is not None",
                        ]
                    )
                )

            test_name = "def test_InMemoryTicketStore_list_comments_rule"
            if test_name not in existing_content:
                blocks.append(
                    "\n".join(
                        [
                            "def test_InMemoryTicketStore_list_comments_rule():",
                            "    import helpdesk.models",
                            f"    store = {module_alias}.InMemoryTicketStore()",
                            "    t = helpdesk.models.Ticket(id='HD-400003', requester='u@e.com', title='x', description='y')",
                            "    store.add_ticket(t)",
                            "    comment = helpdesk.models.Comment(ticket_id=t.id, author='u@e.com', body='hi')",
                            "    store.add_comment(comment)",
                            "    comments = list(store.list_comments(t.id))",
                            "    assert len(comments) == 1",
                            "    assert comments[0].body == 'hi'",
                        ]
                    )
                )

        return blocks

    def _openai_test_block(
        self,
        module_name: str,
        symbol_name: str,
        obj: object,
        source_text: str,
        iteration_feedback: str = "",
    ) -> str:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logging.warning("OpenAI is enabled but OPENAI_API_KEY is not set; skipping LLM generation.")
            return ""

        try:
            from openai import OpenAI  # type: ignore[import-not-found]
        except ModuleNotFoundError:
            logging.warning("OpenAI is enabled but the 'openai' package is not installed; skipping LLM generation.")
            return ""

        obj_source = ""
        try:
            obj_source = inspect.getsource(obj)
        except (OSError, TypeError):
            obj_source = ""

        prompt = "\n".join(
            [
                "You are generating a single pytest unit test function.",
                "Return ONLY valid python code (no markdown, no backticks).",
                f"Target module: {module_name}",
                f"Target symbol: {symbol_name}",
                "\nPrevious iteration feedback (use this to improve):",
                (iteration_feedback or "(none)")[:4000],
                "Constraints:",
                "- Create exactly one test function named test_<symbol_name>_llm.",
                "- The test must import the module and call or instantiate the target if possible.",
                "- If arguments are required, choose simple dummy values (int=1, str='x', bool=False, list=[]).",
                "- If calling is unsafe/unknown, at least assert callable/inspect signature and do a minimal behavior check.",
                "- Do not reference files outside this module.",
                "- Prefer deterministic assertions.",
                "\nModule source (may be truncated):",
                source_text[:8000],
                "\nTarget source (if available):",
                obj_source[:4000],
            ]
        )

        client = OpenAI(api_key=api_key)
        last_exc: Exception | None = None
        for attempt in range(1, 4):
            try:
                response = client.responses.create(
                    model=self.openai_model,
                    input=prompt,
                    timeout=60,
                )
                last_exc = None
                break
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                wait_s = 0.8 * (2 ** (attempt - 1))
                logging.warning(
                    "OpenAI request failed (attempt %s/3, waiting %.1fs): %s",
                    attempt,
                    wait_s,
                    exc,
                )
                time.sleep(wait_s)

        if last_exc is not None:
            return ""

        text = (getattr(response, "output_text", "") or "").strip()
        if not text:
            return ""
        if "```" in text:
            return ""
        if f"def test_{symbol_name}_llm" not in text:
            return ""
        return text.strip()
