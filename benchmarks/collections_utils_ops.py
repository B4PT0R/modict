"""Micro-benchmarks for collections_utils deep operations."""

from __future__ import annotations

import copy
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
    print("collections_utils benchmark", flush=True)
    print(flush=True)

    bench(
        "get_nested / existing path",
        'get_nested(payload, "$.users[1].profile.display_name")',
        setup="""
from modict.collections_utils import get_nested
payload = {
    "users": [
        {"id": "u1", "profile": {"display_name": "Alice", "age": 30}},
        {"id": "u2", "profile": {"display_name": "Bob", "age": 31}},
    ],
    "flags": {"debug": True, "region": "eu"},
}
""",
        number=500,
    )

    bench(
        "set_nested / existing path",
        'set_nested(payload, "$.users[1].profile.age", 32); payload["users"][1]["profile"]["age"] = 31',
        setup="""
from modict.collections_utils import set_nested
payload = {
    "users": [
        {"id": "u1", "profile": {"display_name": "Alice", "age": 30}},
        {"id": "u2", "profile": {"display_name": "Bob", "age": 31}},
    ],
}
""",
        number=250,
    )

    print(flush=True)

    bench(
        "walk / nested payload",
        "list(walk(payload))",
        setup="""
from modict.collections_utils import walk
payload = {
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

    bench(
        "unwalk / rebuild flattened payload",
        "unwalk(flattened)",
        setup="""
from modict.collections_utils import walked, unwalk
payload = {
    "users": [
        {"id": "u1", "profile": {"display_name": "Alice", "age": 30}},
        {"id": "u2", "profile": {"display_name": "Bob", "age": 31}},
    ],
    "flags": {"debug": True, "region": "eu"},
    "retries": [1, 5, 10],
}
flattened = walked(payload)
""",
        number=20,
    )

    print(flush=True)

    bench(
        "diff_nested / similar payloads",
        "diff_nested(left, right)",
        setup="""
from modict.collections_utils import diff_nested
left = {
    "users": [
        {"id": "u1", "profile": {"display_name": "Alice", "age": 30}},
        {"id": "u2", "profile": {"display_name": "Bob", "age": 31}},
    ],
    "flags": {"debug": True, "region": "eu"},
    "retries": [1, 5, 10],
}
right = {
    "users": [
        {"id": "u1", "profile": {"display_name": "Alice", "age": 30}},
        {"id": "u2", "profile": {"display_name": "Bobby", "age": 32}},
    ],
    "flags": {"debug": False, "region": "eu"},
    "retries": [1, 10],
}
""",
        number=50,
    )

    bench(
        "deep_merge / nested mappings",
        "target = copy.deepcopy(base); deep_merge(target, patch)",
        setup="""
import copy
from modict.collections_utils import deep_merge
base = {
    "users": {
        "u1": {"name": "Alice", "roles": ["admin"]},
        "u2": {"name": "Bob", "roles": ["reader"]},
    },
    "flags": {"debug": True, "region": "eu"},
    "limits": {"retries": 3, "timeout_s": 10},
}
patch = {
    "users": {
        "u2": {"roles": ["reader", "writer"]},
        "u3": {"name": "Cara", "roles": ["reader"]},
    },
    "flags": {"debug": False},
    "limits": {"timeout_s": 15},
}
""",
        number=50,
    )


if __name__ == "__main__":
    main()
