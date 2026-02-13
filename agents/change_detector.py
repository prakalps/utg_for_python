from __future__ import annotations

import ast
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


@dataclass(frozen=True)
class ChangeDetail:
    file_path: Path
    changed_functions: Sequence[str]
    changed_classes: Sequence[str]
    new_blocks: Sequence[str]


@dataclass(frozen=True)
class ChangeDetectionResult:
    changes: Sequence[ChangeDetail]


class ChangeDetectionAgent:
    def __init__(self, excluded_folders: Sequence[str] = ()) -> None:
        self.excluded_folders = set(excluded_folders)

    def detect_changes(self, git_hook: bool) -> ChangeDetectionResult:
        logging.info("Detected changes via git_hook=%s", git_hook)
        diff_command = ["git", "diff", "--name-only", "HEAD~1", "HEAD"] if git_hook else [
            "git",
            "diff",
            "--name-only",
        ]
        changed_files = list(self._run_git_command(diff_command))
        untracked_files = list(
            self._run_git_command([
                "git",
                "ls-files",
                "--others",
                "--exclude-standard",
                "src",
            ])
        )
        changed_files.extend(untracked_files)
        src_files = [
            Path(path)
            for path in changed_files
            if path.startswith("src/") and path.endswith(".py")
        ]
        if not src_files:
            logging.info("No changed src/*.py files detected; scanning src/ for python files.")
            src_files = list(Path("src").rglob("*.py"))
        filtered_files = [
            path for path in src_files if not self._is_excluded(path)
        ]
        change_details = [self._analyze_file(path) for path in filtered_files]
        return ChangeDetectionResult(changes=change_details)

    def _run_git_command(self, command: Sequence[str]) -> Sequence[str]:
        try:
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            logging.warning("Git is not available; no changed files detected.")
            return []
        if result.returncode != 0:
            logging.warning("Git command failed: %s", result.stderr.strip())
            return []
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]

    def _is_excluded(self, path: Path) -> bool:
        return any(part in self.excluded_folders for part in path.parts)

    def _analyze_file(self, path: Path) -> ChangeDetail:
        logging.info("Analyzing changes in %s", path)
        diff_output = self._run_git_command(
            ["git", "diff", "-U0", "HEAD~1", "HEAD", "--", str(path)]
        )
        added_lines = [
            line[1:]
            for line in diff_output
            if line.startswith("+") and not line.startswith("+++")
        ]
        changed_functions = sorted(self._extract_defs(added_lines, "def "))
        changed_classes = sorted(self._extract_defs(added_lines, "class "))
        new_blocks = [line.strip() for line in added_lines if line.strip()]

        if not path.exists():
            return ChangeDetail(path, changed_functions, changed_classes, new_blocks)

        try:
            source = path.read_text()
            tree = ast.parse(source)
        except (OSError, SyntaxError):
            return ChangeDetail(path, changed_functions, changed_classes, new_blocks)

        all_functions = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        all_classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
        if not changed_functions:
            changed_functions = sorted(all_functions)
        if not changed_classes:
            changed_classes = sorted(all_classes)
        return ChangeDetail(path, changed_functions, changed_classes, new_blocks)

    def _extract_defs(self, lines: Iterable[str], prefix: str) -> Iterable[str]:
        for line in lines:
            stripped = line.strip()
            if stripped.startswith(prefix):
                name = stripped[len(prefix):].split("(")[0].split(":")[0].strip()
                if name:
                    yield name
