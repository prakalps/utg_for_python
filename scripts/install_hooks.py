#!/usr/bin/env python3
from __future__ import annotations

import subprocess
from pathlib import Path


def main() -> None:
    hooks_path = Path(".githooks").resolve()
    subprocess.run(
        ["git", "config", "core.hooksPath", str(hooks_path)],
        check=False,
    )
    print(f"Configured git hooks path: {hooks_path}")


if __name__ == "__main__":
    main()
