#!/usr/bin/env python3
from __future__ import annotations

import argparse
import logging
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


def load_config(config_path: Path) -> RunnerConfig:
    if not config_path.exists():
        return RunnerConfig()

    if yaml is None:
        logging.warning("PyYAML is not installed; using default configuration.")
        return RunnerConfig()

    data = yaml.safe_load(config_path.read_text()) or {}
    return RunnerConfig(
        coverage_threshold=float(data.get("coverage_threshold", 0.8)),
        excluded_folders=tuple(data.get("excluded_folders", [])),
        dry_run=bool(data.get("dry_run", False)),
    )


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
    test_generator = TestGenerationAgent(dry_run=config.dry_run)
    validator = ValidationAgent()

    change_result = change_detector.detect_changes(git_hook=args.git_hook)
    discovery_result = test_discovery.discover_tests()
    coverage_result = coverage_analyzer.analyze_coverage(change_result)
    generation_result = test_generator.generate_tests(
        change_result=change_result,
        discovery_result=discovery_result,
        coverage_result=coverage_result,
    )
    validation_result = validator.validate_tests()

    summary_lines = [
        "✔ Changed files analyzed",
        f"✔ Coverage gaps found: {len(coverage_result.gaps)}",
        f"✔ New tests generated: {generation_result.created_tests}",
        "✔ All tests passing" if validation_result.success else "✖ Tests failed",
    ]
    print("\n".join(summary_lines))


if __name__ == "__main__":
    main()
