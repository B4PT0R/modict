"""Tests for basic collection utilities: keys, has_key, unroll."""

import pytest

from modict._collections_utils._basic import keys, has_key, unroll


def test_keys_mapping_and_sequence():
    assert list(keys({"a": 1, "b": 2})) == ["a", "b"]
    assert list(keys([10, 20])) == [0, 1]


def test_keys_invalid_container():
    with pytest.raises(TypeError):
        list(keys(123))  # type: ignore[arg-type]


def test_has_key_mapping_and_sequence():
    assert has_key({"a": 1}, "a") is True
    assert has_key({"a": 1}, "b") is False
    assert has_key([1, 2, 3], 2) is True
    assert has_key([1, 2, 3], 5) is False
    assert has_key([1, 2, 3], -1) is False  # negative index out of range
    assert has_key((1, 2), 1) is True


def test_has_key_invalid_container():
    with pytest.raises(TypeError):
        has_key(123, "a")  # type: ignore[arg-type]


def test_unroll_mapping_and_sequence():
    assert list(unroll({"a": 1})) == [("a", 1)]
    assert list(unroll([10, 20])) == [(0, 10), (1, 20)]
    assert list(unroll((5, 6))) == [(0, 5), (1, 6)]  # tuple treated as sequence


def test_unroll_invalid_container():
    with pytest.raises(TypeError):
        list(unroll("not a container"))  # type: ignore[arg-type]
