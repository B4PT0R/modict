"""Micro-benchmark for hint-plan caches in TypeChecker and Coercer."""

from __future__ import annotations

import sys
import timeit
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modict.typechecker import Coercer, TypeChecker


REPEAT = 3


def bench(label: str, stmt: str, setup: str, *, number: int) -> None:
    samples = timeit.repeat(stmt, setup=setup, repeat=REPEAT, number=number)
    best = min(samples)
    per_op_us = (best / number) * 1_000_000
    print(f"{label:<42} {per_op_us:>10.2f} us/op  best-of-{REPEAT}")


def main() -> None:
    print("Typechecker cache benchmark", flush=True)
    print(flush=True)

    bench(
        "check_type no cache / nested generic",
        "checker.check_type(hint, value)",
        setup="""
from modict.typechecker import TypeChecker
checker = TypeChecker(use_cache=False)
hint = list[dict[str, int | None]]
value = [{"a": 1, "b": None}, {"c": 3}]
""",
        number=2_000,
    )
    bench(
        "check_type cache / nested generic",
        "checker.check_type(hint, value)",
        setup="""
from modict.typechecker import TypeChecker
checker = TypeChecker(use_cache=True)
hint = list[dict[str, int | None]]
value = [{"a": 1, "b": None}, {"c": 3}]
""",
        number=2_000,
    )
    bench(
        "check_type cache / simple int",
        "checker.check_type(int, 123)",
        setup="""
from modict.typechecker import TypeChecker
checker = TypeChecker(use_cache=True)
""",
        number=200_000,
    )
    print(flush=True)
    bench(
        "coerce no cache / nested generic",
        "coercer.coerce(value, hint)",
        setup="""
from modict.typechecker import TypeChecker, Coercer
checker = TypeChecker(use_cache=False)
coercer = Coercer(checker, use_cache=False)
hint = list[dict[str, int]]
value = [{"a": "1"}, {"b": "2"}]
""",
        number=2_000,
    )
    bench(
        "coerce cache / nested generic",
        "coercer.coerce(value, hint)",
        setup="""
from modict.typechecker import TypeChecker, Coercer
checker = TypeChecker(use_cache=True)
coercer = Coercer(checker, use_cache=True)
hint = list[dict[str, int]]
value = [{"a": "1"}, {"b": "2"}]
""",
        number=2_000,
    )
    print(flush=True)
    bench(
        "modict init no cache",
        "Payload(**payload)",
        setup="""
from modict import modict
from modict.typechecker import TypeChecker, Coercer
import modict.typechecker.src._public_api as public_api

checker = TypeChecker(use_cache=False)
coercer = Coercer(checker, use_cache=False)
public_api._global_typechecker = checker
public_api._global_coercer = coercer

class Item(modict):
    sku: str
    qty: int

class Payload(modict):
    order_id: str
    items: list[Item]
    retries: list[int]

payload = {
    "order_id": "ord_123",
    "items": [{"sku": "A", "qty": "1"}, {"sku": "B", "qty": "2"}],
    "retries": ["1", "5", "10"],
}
""",
        number=150,
    )
    bench(
        "modict init cache",
        "Payload(**payload)",
        setup="""
from modict import modict
from modict.typechecker import TypeChecker, Coercer
import modict.typechecker.src._public_api as public_api

checker = TypeChecker(use_cache=True)
coercer = Coercer(checker, use_cache=True)
public_api._global_typechecker = checker
public_api._global_coercer = coercer

class Item(modict):
    sku: str
    qty: int

class Payload(modict):
    order_id: str
    items: list[Item]
    retries: list[int]

payload = {
    "order_id": "ord_123",
    "items": [{"sku": "A", "qty": "1"}, {"sku": "B", "qty": "2"}],
    "retries": ["1", "5", "10"],
}
""",
        number=150,
    )


if __name__ == "__main__":
    main()
