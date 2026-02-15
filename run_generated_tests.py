from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def _venv_python() -> Path:
    venv_python = Path(__file__).resolve().parent / ".venv" / "Scripts" / "python.exe"
    if venv_python.exists():
        return venv_python
    return Path(sys.executable)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run only auto-generated pytest tests.")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run the full pytest suite (all tests), not just generated tests.",
    )
    parser.add_argument(
        "--regen",
        action="store_true",
        help="Run automatic_unit_test_generator.py to (re)generate tests before running pytest.",
    )
    parser.add_argument(
        "--cov",
        action="store_true",
        help="Enable coverage for src/ (writes coverage.json).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Run pytest without -q.",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parent
    tests_dir = root / "tests"
    if not tests_dir.exists():
        raise SystemExit("tests/ directory not found")

    if args.regen:
        regen_cmd = [str(_venv_python()), str(root / "automatic_unit_test_generator.py")]
        regen_proc = subprocess.run(regen_cmd, cwd=str(root), check=False)
        if regen_proc.returncode != 0:
            return int(regen_proc.returncode)

    generated_tests: list[Path] = []
    if not args.all:
        generated_tests = sorted(tests_dir.glob("test_*_generated.py"))
        if not generated_tests:
            print("No generated tests found (expected tests/test_*_generated.py)")
            return 2

    cmd: list[str] = [str(_venv_python()), "-m", "pytest"]
    if args.cov:
        cmd.extend(["--cov=src", "--cov-report=json", "--cov-report=term-missing"])
    if not args.verbose:
        cmd.append("-q")
    if args.all:
        cmd.append(str(tests_dir))
    else:
        cmd.extend([str(p) for p in generated_tests])

    proc = subprocess.run(cmd, cwd=str(root), check=False)
    return int(proc.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
