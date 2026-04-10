"""Micro-benchmarks for type checking and coercion across varied scenarios.

Covers simple builtins through complex nested generics, unions, literals,
optionals, TypedDict, and full modict init pipelines. Each case is designed
to reflect realistic usage frequency — most common types first.
"""

from __future__ import annotations

import sys
import timeit
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

REPEAT = 5


def bench(label: str, stmt: str, setup: str, *, number: int) -> None:
    samples = timeit.repeat(stmt, setup=setup, repeat=REPEAT, number=number)
    best = min(samples)
    per_op_us = (best / number) * 1_000_000
    print(f"{label:<52} {per_op_us:>10.2f} us/op  best-of-{REPEAT}")


def main() -> None:
    print("Typechecker validation benchmark", flush=True)
    print(flush=True)

    # ── 1. check_type: simple builtins (most common) ─────────────────
    print("── check_type: simple builtins ──", flush=True)

    bench(
        "check int",
        "tc.check_type(int, 42)",
        "from modict.typechecker import TypeChecker; tc = TypeChecker()",
        number=200_000,
    )
    bench(
        "check str",
        "tc.check_type(str, 'hello')",
        "from modict.typechecker import TypeChecker; tc = TypeChecker()",
        number=200_000,
    )
    bench(
        "check float",
        "tc.check_type(float, 3.14)",
        "from modict.typechecker import TypeChecker; tc = TypeChecker()",
        number=200_000,
    )
    bench(
        "check bool",
        "tc.check_type(bool, True)",
        "from modict.typechecker import TypeChecker; tc = TypeChecker()",
        number=200_000,
    )
    bench(
        "check None",
        "tc.check_type(None, None)",
        "from modict.typechecker import TypeChecker; tc = TypeChecker()",
        number=200_000,
    )
    bench(
        "check list (bare)",
        "tc.check_type(list, [1, 2, 3])",
        "from modict.typechecker import TypeChecker; tc = TypeChecker()",
        number=200_000,
    )
    bench(
        "check dict (bare)",
        "tc.check_type(dict, {'a': 1})",
        "from modict.typechecker import TypeChecker; tc = TypeChecker()",
        number=200_000,
    )

    print(flush=True)

    # ── 2. check_type: parameterized generics ────────────────────────
    print("── check_type: parameterized generics ──", flush=True)

    bench(
        "check list[int]",
        "tc.check_type(hint, value)",
        "from modict.typechecker import TypeChecker; tc = TypeChecker(); hint = list[int]; value = [1, 2, 3, 4, 5]",
        number=50_000,
    )
    bench(
        "check dict[str, int]",
        "tc.check_type(hint, value)",
        "from modict.typechecker import TypeChecker; tc = TypeChecker(); hint = dict[str, int]; value = {'a': 1, 'b': 2, 'c': 3}",
        number=50_000,
    )
    bench(
        "check tuple[int, str, bool]",
        "tc.check_type(hint, value)",
        "from modict.typechecker import TypeChecker; tc = TypeChecker(); hint = tuple[int, str, bool]; value = (1, 'a', True)",
        number=50_000,
    )
    bench(
        "check set[str]",
        "tc.check_type(hint, value)",
        "from modict.typechecker import TypeChecker; tc = TypeChecker(); hint = set[str]; value = {'a', 'b', 'c'}",
        number=50_000,
    )

    print(flush=True)

    # ── 3. check_type: unions / optionals ────────────────────────────
    print("── check_type: unions / optionals ──", flush=True)

    bench(
        "check int | str (match first)",
        "tc.check_type(hint, 42)",
        "from modict.typechecker import TypeChecker; tc = TypeChecker(); hint = int | str",
        number=100_000,
    )
    bench(
        "check int | str (match second)",
        "tc.check_type(hint, 'hello')",
        "from modict.typechecker import TypeChecker; tc = TypeChecker(); hint = int | str",
        number=100_000,
    )
    bench(
        "check Optional[int] (value)",
        "tc.check_type(hint, 42)",
        "from modict.typechecker import TypeChecker; from typing import Optional; tc = TypeChecker(); hint = Optional[int]",
        number=100_000,
    )
    bench(
        "check Optional[int] (None)",
        "tc.check_type(hint, None)",
        "from modict.typechecker import TypeChecker; from typing import Optional; tc = TypeChecker(); hint = Optional[int]",
        number=100_000,
    )

    print(flush=True)

    # ── 4. check_type: Literal ───────────────────────────────────────
    print("── check_type: Literal ──", flush=True)

    bench(
        "check Literal['a','b','c'] (hit)",
        "tc.check_type(hint, 'b')",
        "from modict.typechecker import TypeChecker; from typing import Literal; tc = TypeChecker(); hint = Literal['a', 'b', 'c']",
        number=100_000,
    )
    bench(
        "check Literal[1,2,3] (hit)",
        "tc.check_type(hint, 2)",
        "from modict.typechecker import TypeChecker; from typing import Literal; tc = TypeChecker(); hint = Literal[1, 2, 3]",
        number=100_000,
    )

    print(flush=True)

    # ── 5. check_type: nested generics ───────────────────────────────
    print("── check_type: nested generics ──", flush=True)

    bench(
        "check list[dict[str, int]]",
        "tc.check_type(hint, value)",
        """
from modict.typechecker import TypeChecker
tc = TypeChecker()
hint = list[dict[str, int]]
value = [{"a": 1, "b": 2}, {"c": 3}]
""",
        number=10_000,
    )
    bench(
        "check dict[str, list[int]]",
        "tc.check_type(hint, value)",
        """
from modict.typechecker import TypeChecker
tc = TypeChecker()
hint = dict[str, list[int]]
value = {"x": [1, 2], "y": [3, 4, 5]}
""",
        number=10_000,
    )
    bench(
        "check list[dict[str, int | None]]",
        "tc.check_type(hint, value)",
        """
from modict.typechecker import TypeChecker
tc = TypeChecker()
hint = list[dict[str, int | None]]
value = [{"a": 1, "b": None}, {"c": 3}]
""",
        number=5_000,
    )

    print(flush=True)

    # ── 6. coerce: basic type coercions ──────────────────────────────
    print("── coerce: basic coercions ──", flush=True)

    bench(
        "coerce str->int",
        "co.coerce('42', int)",
        "from modict.typechecker import TypeChecker, Coercer; tc = TypeChecker(); co = Coercer(tc)",
        number=50_000,
    )
    bench(
        "coerce str->float",
        "co.coerce('3.14', float)",
        "from modict.typechecker import TypeChecker, Coercer; tc = TypeChecker(); co = Coercer(tc)",
        number=50_000,
    )
    bench(
        "coerce int->float",
        "co.coerce(42, float)",
        "from modict.typechecker import TypeChecker, Coercer; tc = TypeChecker(); co = Coercer(tc)",
        number=50_000,
    )
    bench(
        "coerce int (already correct)",
        "co.coerce(42, int)",
        "from modict.typechecker import TypeChecker, Coercer; tc = TypeChecker(); co = Coercer(tc)",
        number=100_000,
    )

    print(flush=True)

    # ── 7. coerce: container coercions ───────────────────────────────
    print("── coerce: container coercions ──", flush=True)

    bench(
        "coerce list[str->int]",
        "co.coerce(value, hint)",
        """
from modict.typechecker import TypeChecker, Coercer
tc = TypeChecker(); co = Coercer(tc)
hint = list[int]; value = ['1', '2', '3']
""",
        number=10_000,
    )
    bench(
        "coerce dict[str, str->int]",
        "co.coerce(value, hint)",
        """
from modict.typechecker import TypeChecker, Coercer
tc = TypeChecker(); co = Coercer(tc)
hint = dict[str, int]; value = {'a': '1', 'b': '2'}
""",
        number=10_000,
    )
    bench(
        "coerce list[dict[str, str->int]]",
        "co.coerce(value, hint)",
        """
from modict.typechecker import TypeChecker, Coercer
tc = TypeChecker(); co = Coercer(tc)
hint = list[dict[str, int]]; value = [{"a": "1"}, {"b": "2"}]
""",
        number=5_000,
    )

    print(flush=True)

    # ── 8. coerce: union / optional coercions ────────────────────────
    print("── coerce: union / optional ──", flush=True)

    bench(
        "coerce str->int|float (to int)",
        "co.coerce('42', hint)",
        "from modict.typechecker import TypeChecker, Coercer; tc = TypeChecker(); co = Coercer(tc); hint = int | float",
        number=50_000,
    )
    bench(
        "coerce Optional[int] (None passthrough)",
        "co.coerce(None, hint)",
        """
from modict.typechecker import TypeChecker, Coercer
from typing import Optional
tc = TypeChecker(); co = Coercer(tc); hint = Optional[int]
""",
        number=50_000,
    )

    print(flush=True)

    # ── 9. modict init: varied complexity ────────────────────────────
    print("── modict init: varied complexity ──", flush=True)

    bench(
        "modict / flat 3-field (str,int,float)",
        "M(**data)",
        """
from modict import modict
class M(modict):
    name: str
    age: int
    score: float
data = {"name": "alice", "age": 30, "score": 9.5}
""",
        number=5_000,
    )
    bench(
        "modict / flat 3-field coercion",
        "M(**data)",
        """
from modict import modict
class M(modict):
    name: str
    age: int
    score: float
data = {"name": "alice", "age": "30", "score": "9.5"}
""",
        number=5_000,
    )
    bench(
        "modict / nested model",
        "Payload(**data)",
        """
from modict import modict
class Item(modict):
    sku: str
    qty: int
class Payload(modict):
    order_id: str
    items: list[Item]
data = {"order_id": "X", "items": [{"sku": "A", "qty": 1}, {"sku": "B", "qty": 2}]}
""",
        number=2_000,
    )
    bench(
        "modict / nested model with coercion",
        "Payload(**data)",
        """
from modict import modict
class Item(modict):
    sku: str
    qty: int
class Payload(modict):
    order_id: str
    items: list[Item]
    retries: list[int]
data = {"order_id": "X", "items": [{"sku": "A", "qty": "1"}, {"sku": "B", "qty": "2"}], "retries": ["1", "5", "10"]}
""",
        number=1_000,
    )
    bench(
        "modict / 6 fields mixed types",
        "M(**data)",
        """
from modict import modict
from typing import Optional
class M(modict):
    name: str
    age: int
    active: bool
    tags: list[str]
    score: Optional[float]
    meta: dict[str, int]
data = {"name": "bob", "age": 25, "active": True, "tags": ["a", "b"], "score": 8.5, "meta": {"x": 1}}
""",
        number=2_000,
    )

    print(flush=True)

    # ── 10. check_type: type mismatch (early rejection) ──────────────
    print("── check_type: mismatch (early exit) ──", flush=True)

    bench(
        "mismatch int (got str)",
        "try:\n    tc.check_type(int, 'hello')\nexcept Exception:\n    pass",
        "from modict.typechecker import TypeChecker; tc = TypeChecker()",
        number=200_000,
    )
    bench(
        "mismatch list[int] (got str in list)",
        "try:\n    tc.check_type(hint, value)\nexcept Exception:\n    pass",
        "from modict.typechecker import TypeChecker; tc = TypeChecker(); hint = list[int]; value = [1, 'bad', 3]",
        number=50_000,
    )


if __name__ == "__main__":
    main()
