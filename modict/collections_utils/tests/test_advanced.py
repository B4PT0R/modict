"""Test suite for the migrated _advanced.py module with JSONPath support."""

import pytest

from modict.collections_utils import (
    get_nested,
    set_nested,
    has_nested,
    pop_nested,
    del_nested,
    walk,
    walked,
    diff_nested,
    unwalk,
    first_keys,
    is_seq_based,
    Path,
    MISSING,
    extract,
    exclude,
    deep_merge,
    deep_equals,
)


class TestGetNested:
    """Tests for get_nested() with different path formats."""

    @pytest.fixture
    def sample_data(self):
        return {"users": [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]}

    def test_get_nested_jsonpath_string(self, sample_data):
        result = get_nested(sample_data, "$.users[0].name")
        assert result == "Alice"

    def test_get_nested_tuple(self, sample_data):
        result = get_nested(sample_data, ("users", 0, "name"))
        assert result == "Alice"

    def test_get_nested_path_object(self, sample_data):
        path = Path("$.users[1].age")
        result = get_nested(sample_data, path)
        assert result == 25

    def test_get_nested_with_default(self, sample_data):
        result = get_nested(sample_data, "$.users[2].name", default="Not found")
        assert result == "Not found"

    def test_get_nested_missing_path_no_default(self, sample_data):
        with pytest.raises((KeyError, IndexError)):
            get_nested(sample_data, "$.users[5].missing")

    def test_get_nested_non_container_raises(self):
        with pytest.raises(TypeError):
            get_nested(123, "$.a")


class TestSetNested:
    def test_set_nested_creates_structure(self):
        data = {}
        set_nested(data, "$.a.b[0].c", 42)
        assert data == {"a": {"b": [{"c": 42}]}}

    def test_set_nested_tuple_path(self):
        data = {"a": {"b": [{"c": 42}]}}
        set_nested(data, ("a", "b", 1, "d"), "hello")
        assert data == {"a": {"b": [{"c": 42}, {"d": "hello"}]}}

    def test_set_nested_existing_path(self):
        data = {"a": 1}
        set_nested(data, "$.a", 99)
        assert data == {"a": 99}

    def test_set_nested_on_non_container(self):
        with pytest.raises(TypeError):
            set_nested(123, "$.a", 1)


class TestHasNested:
    def test_has_nested_existing_path(self):
        data = {"users": [{"name": "Alice"}]}
        assert has_nested(data, "$.users[0].name") is True

    def test_has_nested_missing_path(self):
        data = {"users": [{"name": "Alice"}]}
        assert has_nested(data, "$.users[5].name") is False


class TestExtractExclude:
    def test_extract_preserves_order(self):
        data = {"a": 1, "b": 2, "c": 3}
        result = list(extract(data, "c", "a"))
        assert result == [("a", 1), ("c", 3)]

    def test_exclude_filters_out_keys(self):
        data = {"a": 1, "b": 2, "c": 3}
        result = dict(exclude(data, "b"))
        assert result == {"a": 1, "c": 3}

    def test_extract_invalid_container(self):
        with pytest.raises(TypeError):
            list(extract(123, "a"))  # type: ignore[arg-type]

    def test_exclude_invalid_container(self):
        with pytest.raises(TypeError):
            list(exclude(123, "a"))  # type: ignore[arg-type]


class TestWalkUnwalk:
    def test_walked_and_unwalk_roundtrip(self):
        data = {"a": {"b": [1, 2]}, "c": 3}
        w = walked(data)
        rebuilt = unwalk(w)
        assert deep_equals(rebuilt, data)

    def test_walk_returns_paths(self):
        data = {"a": {"b": 1}}
        w = list(walk(data))
        assert any(isinstance(p, Path) for p, _ in w)


class TestDiffAndMerge:
    def test_diff_nested_reports_missing(self):
        left = {"a": 1}
        right = {"a": 1, "b": 2}
        diffs = diff_nested(left, right)
        assert diffs[Path("$.b")] == (MISSING, 2)

    def test_deep_merge_with_missing_deletes(self):
        target = {"a": 1, "b": 2}
        deep_merge(target, {"b": MISSING})
        assert target == {"a": 1}


class TestFirstKeys:
    def test_first_keys(self):
        data = {"a": {"b": 1}}
        ks = first_keys(walked(data))
        assert ks == {"a"}


class TestIsSeqBased:
    def test_is_seq_based(self):
        assert is_seq_based(walked([{"a": 1}, {"b": 2}])) is True
        assert is_seq_based(walked({"a": [1, 2]})) is False
