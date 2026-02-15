#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover
    yaml = None

from agents.change_detector import ChangeDetectionAgent
from agents.coverage_analyzer import CoverageAnalyzerAgent
from agents.test_discovery import TestDiscoveryAgent
from agents.test_generator import TestGenerationAgent
from agents.validator import ValidationAgent


@dataclass
class RunnerConfig:
    coverage_threshold: float = 0.8
    excluded_folders: Sequence[str] = ()
    dry_run: bool = False
    openai_enabled: bool = False
    openai_model: str = "gpt-4o-mini"
    max_regen_rounds: int = 1
    min_quality: str = "low"
    overwrite_generated_files: bool = False


def load_config(config_path: Path) -> RunnerConfig:
    if not config_path.exists():
        return RunnerConfig()

    if yaml is None:
        logging.warning(
            "PyYAML is not installed for interpreter %s; using default configuration.",
            sys.executable,
        )
        return RunnerConfig()

    data = yaml.safe_load(config_path.read_text()) or {}
    return RunnerConfig(
        coverage_threshold=float(data.get("coverage_threshold", 0.8)),
        excluded_folders=tuple(data.get("excluded_folders", [])),
        dry_run=bool(data.get("dry_run", False)),
        openai_enabled=bool(data.get("openai_enabled", False)),
        openai_model=str(data.get("openai_model", "gpt-4o-mini")),
        max_regen_rounds=int(data.get("max_regen_rounds", 1)),
        min_quality=str(data.get("min_quality", "low")),
        overwrite_generated_files=bool(data.get("overwrite_generated_files", False)),
    )


def _quality_rank(value: str) -> int:
    ranking = {"low": 0, "medium": 1, "high": 2}
    return ranking.get(value.strip().lower(), 0)


def summarize_generated_quality(tests_root: Path) -> dict[str, int]:
    summary: dict[str, int] = {"low": 0, "medium": 0, "high": 0}
    for path in sorted(tests_root.glob("test_*_generated.py")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        summary["low"] += text.count(" quality=low")
        summary["medium"] += text.count(" quality=medium")
        summary["high"] += text.count(" quality=high")
    return summary


def _missing_lines_for_file(file_path: Path) -> list[int]:
    coverage_json = Path("coverage.json")
    if not coverage_json.exists():
        return []
    try:
        report = json.loads(coverage_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    files_report = report.get("files", {})
    candidates = [str(file_path), file_path.as_posix()]
    normalized: list[str] = []
    for candidate in candidates:
        if not candidate:
            continue
        normalized.append(candidate)
        normalized.append(candidate.replace("/", "\\"))
        normalized.append(candidate.replace("\\", "/"))

    for key in normalized:
        data = files_report.get(key)
        if isinstance(data, dict):
            lines = data.get("missing_lines", [])
            if isinstance(lines, list):
                return [int(x) for x in lines if isinstance(x, (int, float, str)) and str(x).isdigit()]
    return []


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI Test Runner")
    parser.add_argument(
        "--git-hook",
        action="store_true",
        help="Run in git hook mode (detect changes since last commit).",
    )
    return parser.parse_args()


def main() -> None:
    setup_logging()
    args = parse_args()
    config = load_config(Path("ai_test_config.yaml"))

    change_detector = ChangeDetectionAgent(excluded_folders=config.excluded_folders)
    test_discovery = TestDiscoveryAgent()
    coverage_analyzer = CoverageAnalyzerAgent(coverage_threshold=config.coverage_threshold)
    test_generator = TestGenerationAgent(
        dry_run=config.dry_run,
        openai_enabled=config.openai_enabled,
        openai_model=config.openai_model,
    )
    validator = ValidationAgent()

    change_result = change_detector.detect_changes(git_hook=args.git_hook)
    discovery_result = test_discovery.discover_tests()

    max_rounds = max(1, int(config.max_regen_rounds))
    min_q_rank = _quality_rank(config.min_quality)
    quality_extension_budget = 5
    extension_used = 0

    last_generation = None
    last_validation = None
    last_coverage = None
    iteration_feedback = ""

    @dataclass(frozen=True)
    class _RoundScore:
        tests_pass: bool
        gaps: int
        worst_quality_rank: int

    def _score_round(*, tests_pass: bool, gaps: int, worst_quality_rank: int) -> _RoundScore:
        return _RoundScore(tests_pass=tests_pass, gaps=gaps, worst_quality_rank=worst_quality_rank)

    def _is_better(a: _RoundScore, b: _RoundScore) -> bool:
        if a.tests_pass != b.tests_pass:
            return a.tests_pass and not b.tests_pass
        if a.gaps != b.gaps:
            return a.gaps < b.gaps
        return a.worst_quality_rank > b.worst_quality_rank

    def _snapshot_tests(*, tests_dir: Path) -> Path:
        tmp_root = Path(tempfile.mkdtemp(prefix="utg_tests_snapshot_"))
        snap_dir = tmp_root / "tests"
        shutil.copytree(tests_dir, snap_dir)
        return snap_dir

    def _restore_tests(*, snapshot_dir: Path, tests_dir: Path) -> None:
        if tests_dir.exists():
            shutil.rmtree(tests_dir)
        shutil.copytree(snapshot_dir, tests_dir)

    tests_dir = Path("tests")
    best_snapshot: Path | None = _snapshot_tests(tests_dir=tests_dir) if tests_dir.exists() else None
    best_score = _score_round(tests_pass=False, gaps=10**9, worst_quality_rank=-1)

    round_idx = 1
    while round_idx <= max_rounds:
        logging.info("Regeneration round %s/%s", round_idx, max_rounds)

        round_snapshot = _snapshot_tests(tests_dir=tests_dir) if tests_dir.exists() else None

        coverage_before = coverage_analyzer.analyze_coverage(change_result)
        if coverage_before.coverage_text.strip():
            print(coverage_before.coverage_text)

        gaps_summary_lines: list[str] = []
        for gap in coverage_before.gaps:
            missing_lines = _missing_lines_for_file(gap.file)
            tail_lines = missing_lines[:50]
            gaps_summary_lines.append(
                f"- file={gap.file} missing_defs={list(gap.missing_tests)} missing_lines={tail_lines}"
            )

        generation_result = test_generator.generate_tests(
            change_result=change_result,
            discovery_result=discovery_result,
            coverage_result=coverage_before,
            overwrite_generated_files=config.overwrite_generated_files,
            iteration_feedback=iteration_feedback,
            min_quality=config.min_quality,
        )

        validation_result = validator.validate_tests()

        coverage_after = coverage_analyzer.analyze_coverage(change_result)
        if coverage_after.coverage_text.strip():
            print(coverage_after.coverage_text)

        overall_quality = summarize_generated_quality(Path("tests"))
        worst_quality_rank = 2
        if overall_quality.get("low", 0) > 0:
            worst_quality_rank = 0
        elif overall_quality.get("medium", 0) > 0:
            worst_quality_rank = 1

        worst_quality_label = "low" if worst_quality_rank == 0 else "medium" if worst_quality_rank == 1 else "high"
        pytest_excerpt = ""
        if not validation_result.success and validation_result.output:
            lines = [line for line in validation_result.output.splitlines() if line.strip()]
            pytest_excerpt = "\n".join(lines[-60:])

        iteration_feedback = "\n".join(
            [
                f"Round {round_idx}/{max_rounds}",
                f"tests_pass={validation_result.success}",
                f"coverage_gaps={len(coverage_after.gaps)}",
                f"generated_this_round={generation_result.created_tests}",
                f"quality_counts={overall_quality}",
                f"worst_quality={worst_quality_label}",
                "coverage_gaps_detail:",
                *gaps_summary_lines,
                "pytest_failure_excerpt:",
                pytest_excerpt or "(none)",
            ]
        )

        done = validation_result.success and len(coverage_after.gaps) == 0 and worst_quality_rank >= min_q_rank

        round_score = _score_round(
            tests_pass=validation_result.success,
            gaps=len(coverage_after.gaps),
            worst_quality_rank=worst_quality_rank,
        )
        if _is_better(round_score, best_score):
            best_score = round_score
            if best_snapshot is not None:
                shutil.rmtree(best_snapshot.parent, ignore_errors=True)
            best_snapshot = _snapshot_tests(tests_dir=tests_dir)
        elif round_snapshot is not None and best_snapshot is not None and not _is_better(round_score, best_score):
            _restore_tests(snapshot_dir=best_snapshot, tests_dir=tests_dir)

        last_generation = generation_result
        last_validation = validation_result
        last_coverage = coverage_after

        if done:
            logging.info(
                "Stop condition met: tests_pass=%s gaps=%s worst_quality=%s min_quality=%s",
                validation_result.success,
                len(coverage_after.gaps),
                worst_quality_label,
                config.min_quality,
            )
            break

        if (
            round_idx == max_rounds
            and validation_result.success
            and len(coverage_after.gaps) == 0
            and worst_quality_rank < min_q_rank
            and extension_used < quality_extension_budget
        ):
            extension_used += 1
            max_rounds += 1
            logging.info(
                "Extending regeneration rounds to improve quality (extension %s/%s): worst_quality=%s min_quality=%s",
                extension_used,
                quality_extension_budget,
                worst_quality_label,
                config.min_quality,
            )
        elif round_idx == max_rounds:
            logging.info(
                "Max rounds reached: tests_pass=%s gaps=%s worst_quality=%s min_quality=%s",
                validation_result.success,
                len(coverage_after.gaps),
                worst_quality_label,
                config.min_quality,
            )

        round_idx += 1

    if best_snapshot is not None:
        _restore_tests(snapshot_dir=best_snapshot, tests_dir=tests_dir)

    generation_result = last_generation
    validation_result = last_validation
    coverage_result = last_coverage
    if generation_result is None or validation_result is None or coverage_result is None:
        return

    quality = summarize_generated_quality(Path("tests"))
    summary_lines = [
        "✔ Changed files analyzed",
        f"✔ Coverage gaps found: {len(coverage_result.gaps)}",
        f"✔ New tests generated: {generation_result.created_tests}",
        f"  - Rule-based: {generation_result.created_rule_tests}",
        f"  - LLM (OpenAI): {generation_result.created_llm_tests}",
        f"  - Quality: high={quality.get('high', 0)} medium={quality.get('medium', 0)} low={quality.get('low', 0)}",
        "✔ All tests passing" if validation_result.success else "✖ Tests failed",
    ]
    print("\n".join(summary_lines))


if __name__ == "__main__":
    main()
