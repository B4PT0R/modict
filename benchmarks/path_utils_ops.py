"""Micro-benchmarks for path_utils operations."""

from __future__ import annotations

import sys
import timeit
from pathlib import Path as _FsPath

sys.path.insert(0, str(_FsPath(__file__).resolve().parents[1]))


REPEAT = 2


def bench(label: str, stmt: str, setup: str, *, number: int) -> None:
    samples = timeit.repeat(stmt, setup=setup, repeat=REPEAT, number=number)
    best = min(samples)
    per_op_us = (best / number) * 1_000_000
    print(f"{label:<42} {per_op_us:>10.2f} us/op  best-of-{REPEAT}")


def main() -> None:
    print("path_utils benchmark", flush=True)
    print(flush=True)

    bench(
        "Path / parse JSONPath string",
        'Path("$.users[12].profile.display_name")',
        setup="""
from modict.path_utils import Path
""",
        number=100,
    )

    bench(
        "Path / chained child construction",
        'base["users"][12]["profile"]["display_name"]',
        setup="""
from modict.path_utils import Path
base = Path()
""",
        number=500,
    )

    print(flush=True)

    bench(
        "Path / resolve existing path",
        "path.resolve()",
        setup="""
from modict.path_utils import Path
root = {
    "users": [
        {"profile": {"display_name": "Alice"}},
        {"profile": {"display_name": "Bob"}},
    ]
}
path = Path("$.users[1].profile.display_name", root=root)
""",
        number=1_000,
    )

    bench(
        "Path / walk nested payload",
        "list(Path.walk(root))",
        setup="""
from modict.path_utils import Path
root = {
    "users": [
        {"id": "u1", "profile": {"display_name": "Alice", "age": 30}},
        {"id": "u2", "profile": {"display_name": "Bob", "age": 31}},
    ],
    "flags": {"debug": True, "region": "eu"},
    "retries": [1, 5, 10],
}
""",
        number=20,
    )

    print(flush=True)

    bench(
        "Path / slice with retained root",
        "path[:3]",
        setup="""
from modict.path_utils import Path
root = {"users": [{"profile": {"display_name": "Alice"}}]}
path = Path("$.users[0].profile.display_name", root=root)
""",
        number=500,
    )

    bench(
        "Path / relative_to prefix",
        'path.relative_to("$.users[0]")',
        setup="""
from modict.path_utils import Path
path = Path("$.users[0].profile.display_name")
""",
        number=500,
    )


if __name__ == "__main__":
    main()
