"""Run benchmark scripts sequentially in isolated subprocesses."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SCRIPTS = [
    ROOT / "typechecker_cache.py",
    ROOT / "modict_core_ops.py",
    ROOT / "path_utils_ops.py",
    ROOT / "collections_utils_ops.py",
]


def run_script(script: Path) -> int:
    title = f"== {script.name} =="
    print(title, flush=True)
    print(flush=True)
    completed = subprocess.run([sys.executable, str(script)], cwd=ROOT.parent)
    print(flush=True)
    return completed.returncode


def main() -> int:
    exit_code = 0
    for index, script in enumerate(SCRIPTS):
        if index:
            print("-" * 72, flush=True)
        exit_code = max(exit_code, run_script(script))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
