from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

import pytest

from collections_utils import json_dumps, to_jsonable


class Color(Enum):
    RED = "red"


@dataclass
class Point:
    x: int
    y: int


def test_to_jsonable_handles_nested_and_exclude_none():
    obj = {"a": 1, "b": None, "c": {"d": None, "e": 2}, "f": [None, 3]}
    assert to_jsonable(obj, exclude_none=True) == {"a": 1, "c": {"e": 2}, "f": [None, 3]}


def test_to_jsonable_encodes_enums_when_enabled():
    obj = {"color": Color.RED}
    assert to_jsonable(obj, use_enum_values=True) == {"color": "red"}


def test_to_jsonable_applies_encoders_to_leaf_values():
    ts = datetime(2020, 1, 1, tzinfo=timezone.utc)
    obj = {"ts": ts, "pt": Point(1, 2)}

    encoded = to_jsonable(
        obj,
        encoders={
            datetime: lambda v: v.isoformat(),
            Point: lambda v: {"x": v.x, "y": v.y},
        },
    )
    assert encoded == {"ts": "2020-01-01T00:00:00+00:00", "pt": {"x": 1, "y": 2}}


def test_json_dumps_roundtrip_for_jsonable_payload():
    payload = {"a": [1, 2, 3], "b": {"c": "d"}}
    s = json_dumps(payload, sort_keys=True)
    assert s == '{"a": [1, 2, 3], "b": {"c": "d"}}'


def test_json_dumps_raises_for_unknown_types_without_encoder():
    with pytest.raises(TypeError):
        json_dumps({"pt": Point(1, 2)})

