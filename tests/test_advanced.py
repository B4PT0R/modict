"""Test suite for the migrated _advanced.py module with JSONPath support."""

import pytest
from modict._collections_utils import (
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
)


class TestGetNested:
    """Tests for get_nested() with different path formats."""

    @pytest.fixture
    def sample_data(self):
        return {"users": [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]}

    def test_get_nested_jsonpath_string(self, sample_data):
        """Test get_nested() with JSONPath string."""
        result = get_nested(sample_data, "$.users[0].name")
        assert result == "Alice"

    def test_get_nested_tuple(self, sample_data):
        """Test get_nested() with tuple path."""
        result = get_nested(sample_data, ("users", 0, "name"))
        assert result == "Alice"

    def test_get_nested_path_object(self, sample_data):
        """Test get_nested() with Path object."""
        path = Path.from_jsonpath("$.users[1].age")
        result = get_nested(sample_data, path)
        assert result == 25

    def test_get_nested_with_default(self, sample_data):
        """Test get_nested() with default value for missing path."""
        result = get_nested(sample_data, "$.users[2].name", default="Not found")
        assert result == "Not found"

    def test_get_nested_missing_path_no_default(self, sample_data):
        """Test get_nested() raises KeyError for missing path without default."""
        with pytest.raises(KeyError):
            get_nested(sample_data, "$.users[5].missing")


class TestSetNested:
    """Tests for set_nested() function."""

    def test_set_nested_creates_structure(self):
        """Test set_nested() creates intermediate containers."""
        data = {}
        set_nested(data, "$.a.b[0].c", 42)
        assert data == {"a": {"b": [{"c": 42}]}}

    def test_set_nested_tuple_path(self):
        """Test set_nested() with tuple path."""
        data = {"a": {"b": [{"c": 42}]}}
        set_nested(data, ("a", "b", 1, "d"), "hello")
        assert data == {"a": {"b": [{"c": 42}, {"d": "hello"}]}}

    def test_set_nested_existing_path(self):
        """Test set_nested() updates existing value."""
        data = {"a": 1}
        set_nested(data, "$.a", 99)
        assert data == {"a": 99}


class TestHasNested:
    """Tests for has_nested() function."""

    def test_has_nested_existing_path(self):
        """Test has_nested() returns True for existing path."""
        data = {"users": [{"name": "Alice"}]}
        assert has_nested(data, "$.users[0].name") is True

    def test_has_nested_missing_path(self):
        """Test has_nested() returns False for missing path."""
        data = {"users": [{"name": "Alice"}]}
        assert has_nested(data, "$.users[5].name") is False


class TestWalk:
    """Tests for walk() - now returns Path objects."""

    @pytest.fixture
    def nested_data(self):
        return {"a": [1, {"b": 2}], "c": 3}

    def test_walk_returns_path_objects(self, nested_data):
        """Test walk() returns Path objects (not strings)."""
        walked_result = list(walk(nested_data))

        # All paths should be Path objects
        for path, value in walked_result:
            assert isinstance(path, Path), f"Expected Path object, got {type(path)}"

    def test_walk_yields_correct_values(self, nested_data):
        """Test walk() yields correct path-value pairs."""
        walked_result = dict(walk(nested_data))

        # Check we have the expected number of leaf nodes
        assert len(walked_result) == 3

        # Check values are correct (paths may vary in representation)
        values = set(walked_result.values())
        assert values == {1, 2, 3}


class TestWalked:
    """Tests for walked() - returns Dict[Path, Any]."""

    def test_walked_returns_path_dict(self):
        """Test walked() returns dictionary with Path keys."""
        data = {"a": [1, {"b": 2}], "c": 3}
        walked_dict = walked(data)

        # All keys should be Path objects
        for path in walked_dict.keys():
            assert isinstance(path, Path), f"Expected Path key, got {type(path)}"


class TestFirstKeys:
    """Tests for first_keys() with Path-based walked dict."""

    def test_first_keys_mapping(self):
        """Test first_keys() extracts first-level keys from mapping."""
        data = {"a": [1, {"b": 2}], "c": 3}
        walked_dict = walked(data)
        fk = first_keys(walked_dict)
        assert fk == {'a', 'c'}

    def test_first_keys_sequence(self):
        """Test first_keys() extracts indices from sequence."""
        data = [{"a": 1}, {"b": 2}, {"c": 3}]
        walked_dict = walked(data)
        fk = first_keys(walked_dict)
        assert fk == {0, 1, 2}


class TestIsSeqBased:
    """Tests for is_seq_based()."""

    def test_is_seq_based_true(self):
        """Test is_seq_based() returns True for sequence-based structures."""
        seq_data = [{"a": 1}, {"b": 2}]
        seq_walked = walked(seq_data)
        assert is_seq_based(seq_walked) is True

    def test_is_seq_based_false(self):
        """Test is_seq_based() returns False for mapping-based structures."""
        map_data = {"a": 1, "b": 2}
        map_walked = walked(map_data)
        assert is_seq_based(map_walked) is False


class TestUnwalk:
    """Tests for unwalk()."""

    def test_unwalk_mapping(self):
        """Test unwalk() reconstructs mapping structures."""
        data = {"a": [1, {"b": 2}], "c": 3}
        walked_dict = walked(data)
        reconstructed = unwalk(walked_dict)
        assert reconstructed == data

    def test_unwalk_sequence(self):
        """Test unwalk() reconstructs sequence structures."""
        data = [{"a": 1}, {"b": 2}]
        walked_dict = walked(data)
        reconstructed = unwalk(walked_dict)
        assert reconstructed == data


class TestDiffNested:
    """Tests for diff_nested() - returns Dict[Path, Tuple[Any, Any]]."""

    def test_diff_nested_returns_path_keys(self):
        """Test diff_nested() returns dictionary with Path keys."""
        a = {"x": 1, "y": {"z": 2}}
        b = {"x": 1, "y": {"z": 3}, "w": 4}
        diffs = diff_nested(a, b)

        # All keys should be Path objects
        for path in diffs.keys():
            assert isinstance(path, Path), f"Expected Path key in diff, got {type(path)}"

    def test_diff_nested_identifies_changes(self):
        """Test diff_nested() correctly identifies changes."""
        a = {"x": 1, "y": {"z": 2}}
        b = {"x": 1, "y": {"z": 3}, "w": 4}
        diffs = diff_nested(a, b)

        # Should have 2 differences: y.z changed, w added
        assert len(diffs) == 2

        # Check the values in diffs
        diff_values = list(diffs.values())
        assert (2, 3) in diff_values  # z changed from 2 to 3
        assert (MISSING, 4) in diff_values  # w added (MISSING -> 4)


class TestPopAndDelNested:
    """Tests for pop_nested() and del_nested()."""

    def test_pop_nested_returns_value(self):
        """Test pop_nested() returns the popped value."""
        data = {"a": {"b": [1, 2, 3]}}
        popped = pop_nested(data, "$.a.b[1]")
        assert popped == 2
        assert data == {"a": {"b": [1, 3]}}

    def test_del_nested_removes_value(self):
        """Test del_nested() removes the value."""
        data = {"a": {"b": [1, 3]}}
        del_nested(data, "$.a.b[0]")
        assert data == {"a": {"b": [3]}}

    def test_pop_nested_with_default(self):
        """Test pop_nested() returns default for missing path."""
        data = {"a": 1}
        result = pop_nested(data, "$.missing", default="not found")
        assert result == "not found"
        assert data == {"a": 1}

    def test_pop_nested_missing_no_default(self):
        """Test pop_nested() raises KeyError for missing path without default."""
        data = {"a": 1}
        with pytest.raises(KeyError):
            pop_nested(data, "$.missing")
