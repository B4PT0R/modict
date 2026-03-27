"""Micro-benchmarks for common modict core operations."""

from __future__ import annotations

import sys
import timeit
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


REPEAT = 3


def bench(label: str, stmt: str, setup: str, *, number: int) -> None:
    samples = timeit.repeat(stmt, setup=setup, repeat=REPEAT, number=number)
    best = min(samples)
    per_op_us = (best / number) * 1_000_000
    print(f"{label:<42} {per_op_us:>10.2f} us/op  best-of-{REPEAT}")


def main() -> None:
    print("modict core benchmark", flush=True)
    print(flush=True)

    bench(
        "typed assignment / coercion path",
        'payload["count"] = "3"',
        setup="""
from modict import modict

class Payload(modict):
    _config = modict.config(validate_assignment=True)
    count: int

payload = Payload(count=1)
""",
        number=5_000,
    )

    bench(
        "typed assignment / no-op fast path",
        'payload["count"] = 1',
        setup="""
from modict import modict

class Payload(modict):
    _config = modict.config(validate_assignment=True)
    count: int

payload = Payload(count=1)
""",
        number=5_000,
    )

    print(flush=True)

    bench(
        "bulk update / changed values",
        'payload.update({"a": "10", "b": "20", "c": "30"})',
        setup="""
from modict import modict

class Payload(modict):
    _config = modict.config(validate_assignment=True)
    a: int
    b: int
    c: int

payload = Payload(a=1, b=2, c=3)
""",
        number=2_000,
    )

    bench(
        "bulk update / no-op values",
        'payload.update({"a": 1, "b": 2, "c": 3})',
        setup="""
from modict import modict

class Payload(modict):
    _config = modict.config(validate_assignment=True)
    a: int
    b: int
    c: int

payload = Payload(a=1, b=2, c=3)
""",
        number=2_000,
    )

    print(flush=True)

    bench(
        "computed read / cached",
        "payload.total",
        setup="""
from modict import modict

class Payload(modict):
    a: int
    b: int

    @modict.computed(cache=True, deps=["a", "b"])
    def total(self):
        return self.a + self.b

payload = Payload(a=1, b=2)
_ = payload.total
""",
        number=20_000,
    )

    bench(
        "computed write+read / invalidated",
        'payload["a"] = 2; payload.total; payload["a"] = 1',
        setup="""
from modict import modict

class Payload(modict):
    _config = modict.config(validate_assignment=True)
    a: int
    b: int

    @modict.computed(cache=True, deps=["a", "b"])
    def total(self):
        return self.a + self.b

payload = Payload(a=1, b=2)
_ = payload.total
""",
        number=5_000,
    )


if __name__ == "__main__":
    main()
