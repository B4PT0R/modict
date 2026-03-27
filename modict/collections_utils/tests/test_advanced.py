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
    def test_set_nested_root_path_is_rejected(self):
        with pytest.raises(ValueError, match="root path"):
            set_nested({}, Path(), 1)

    def test_set_nested_missing_intermediate_raises_by_default(self):
        data = {}
        with pytest.raises(KeyError, match="Missing intermediate container"):
            set_nested(data, "$.a.b[0].c", 42)

    def test_set_nested_creates_structure_with_factory(self):
        data = {}

        def factory(path):
            return [] if tuple(path) == ("a", "b") else {}

        set_nested(data, "$.a.b[0].c", 42, create_missing=True, container_factory=factory)
        assert data == {"a": {"b": [{"c": 42}]}}

    def test_set_nested_tuple_path(self):
        data = {"a": {"b": [{"c": 42}]}}
        set_nested(
            data,
            ("a", "b", 1, "d"),
            "hello",
            create_missing=True,
            container_factory=lambda path: {},
        )
        assert data == {"a": {"b": [{"c": 42}, {"d": "hello"}]}}

    def test_set_nested_existing_path(self):
        data = {"a": 1}
        set_nested(data, "$.a", 99)
        assert data == {"a": 99}

    def test_set_nested_on_non_container(self):
        with pytest.raises(TypeError):
            set_nested(123, "$.a", 1)

    def test_set_nested_default_factory_requires_path_metadata(self):
        data = {}
        with pytest.raises(TypeError, match="Cannot infer missing container type"):
            set_nested(data, "$.a.b", 1, create_missing=True)

    def test_set_nested_factory_must_return_mutable_container(self):
        data = {}

        with pytest.raises(TypeError, match="MutableMapping or MutableSequence"):
            set_nested(data, "$.a.b", 1, create_missing=True, container_factory=lambda path: ())

    def test_set_nested_default_factory_uses_path_metadata(self):
        template = {"a": {"b": [{"c": 0}]}}
        template_path = next(path for path, _ in walk(template) if str(path) == "$.a.b[0].c")

        data = {}
        set_nested(data, template_path, 42, create_missing=True)

        assert data == {"a": {"b": [{"c": 42}]}}

    def test_set_nested_fails_when_intermediate_value_is_not_a_container(self):
        data = {"a": 1}

        with pytest.raises(TypeError, match="non-container"):
            set_nested(data, "$.a.b", 2, create_missing=True, container_factory=lambda path: {})


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

    def test_walk_is_cycle_safe(self):
        data = {}
        data["self"] = data

        assert list(walk(data)) == []

    def test_unwalk_uses_interface_hints_for_int_key_mapping(self):
        data = {"headers": {0: "x-zero", 1: "x-one"}}
        snapshot = walked(data)

        rebuilt = unwalk(snapshot)

        assert isinstance(rebuilt, dict)
        assert isinstance(rebuilt["headers"], dict)
        assert rebuilt["headers"] == {0: "x-zero", 1: "x-one"}

    def test_unwalk_ignore_types_uses_local_heuristic(self):
        data = {"headers": {0: "x-zero", 1: "x-one"}}
        snapshot = walked(data)

        rebuilt = unwalk(snapshot, ignore_types=True)

        assert isinstance(rebuilt, dict)
        assert isinstance(rebuilt["headers"], list)
        assert rebuilt["headers"] == ["x-zero", "x-one"]

    def test_unwalk_kind_resolver_can_override_inferred_kind(self):
        data = {"headers": {0: "x-zero", 1: "x-one"}}
        snapshot = walked(data)

        rebuilt = unwalk(
            snapshot,
            ignore_types=True,
            kind_resolver=lambda path, kind: "mapping" if tuple(path) == ("headers",) else kind,
        )

        assert isinstance(rebuilt, dict)
        assert isinstance(rebuilt["headers"], dict)
        assert rebuilt["headers"] == {0: "x-zero", 1: "x-one"}

    def test_unwalk_kind_resolver_rejects_invalid_kind(self):
        snapshot = {Path("$.a"): 1}

        with pytest.raises(ValueError):
            unwalk(snapshot, kind_resolver=lambda path, kind: "set")

    def test_unwalk_empty_snapshot_returns_empty_mapping(self):
        assert unwalk({}) == {}

    def test_unwalk_rejects_conflicting_leaf_and_branch_paths(self):
        snapshot = {
            Path("$.a"): 1,
            Path("$.a.b"): 2,
        }

        with pytest.raises(ValueError, match="leaf path"):
            unwalk(snapshot)

    def test_unwalk_rejects_setting_leaf_where_children_already_exist(self):
        snapshot = {
            Path("$.a.b"): 2,
            Path("$.a"): 1,
        }

        with pytest.raises(ValueError, match="already has children"):
            unwalk(snapshot)


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

    def test_diff_nested_compares_sequences_by_index(self):
        diffs = diff_nested([1, {"a": 2}], [1, {"a": 3}, 4])

        assert diffs[Path("$[1].a")] == (2, 3)
        assert diffs[Path("$[2]")] == (MISSING, 4)


class TestFirstKeys:
    def test_first_keys(self):
        data = {"a": {"b": 1}}
        ks = first_keys(walked(data))
        assert ks == {"a"}


class TestIsSeqBased:
    def test_is_seq_based(self):
        assert is_seq_based(walked([{"a": 1}, {"b": 2}])) is True
        assert is_seq_based(walked({"a": [1, 2]})) is False
