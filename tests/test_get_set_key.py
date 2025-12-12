"""Test suite for get_key() and set_key() basic functionality."""

import pytest
from modict._collections_utils import get_key, set_key, MISSING


class TestGetKey:
    """Tests for get_key() function."""

    def test_get_from_mapping(self):
        """Test get_key() with Mapping."""
        data = {"a": 1, "b": 2}
        assert get_key(data, "a") == 1
        assert get_key(data, "b") == 2

    def test_get_from_mapping_with_default(self):
        """Test get_key() with Mapping and default value."""
        data = {"a": 1, "b": 2}
        assert get_key(data, "c", default=None) is None
        assert get_key(data, "c", default=-1) == -1

    def test_get_from_mapping_missing_key(self):
        """Test get_key() with Mapping raises KeyError for missing key."""
        data = {"a": 1}
        with pytest.raises(KeyError):
            get_key(data, "missing")

    def test_get_from_sequence(self):
        """Test get_key() with Sequence."""
        items = [10, 20, 30]
        assert get_key(items, 0) == 10
        assert get_key(items, 1) == 20
        assert get_key(items, 2) == 30

    def test_get_from_sequence_with_default(self):
        """Test get_key() with Sequence and default value."""
        items = [10, 20, 30]
        assert get_key(items, 5, default=-1) == -1
        assert get_key(items, 100, default=None) is None

    def test_get_from_sequence_out_of_bounds(self):
        """Test get_key() with Sequence raises IndexError for out-of-bounds index."""
        items = [10, 20, 30]
        with pytest.raises(IndexError):
            get_key(items, 10)

    def test_get_from_sequence_invalid_key_type(self):
        """Test get_key() with Sequence raises TypeError for non-int key."""
        items = [10, 20, 30]
        with pytest.raises(TypeError, match="Sequence indices must be int"):
            get_key(items, "not_an_int")

    def test_get_invalid_container(self):
        """Test get_key() raises TypeError for invalid container."""
        with pytest.raises(TypeError, match="Expected a Mapping or Sequence container"):
            get_key(123, "key")


class TestSetKey:
    """Tests for set_key() basic functionality."""

    def test_set_in_mapping(self):
        """Test set_key() with MutableMapping."""
        data = {"a": 1}
        set_key(data, "b", 2)
        assert data == {"a": 1, "b": 2}

    def test_set_in_sequence_within_bounds(self):
        """Test set_key() with MutableSequence within bounds."""
        items = [10, 20, 30]
        set_key(items, 1, 99)
        assert items == [10, 99, 30]

    def test_set_in_sequence_auto_expand(self):
        """Test set_key() with MutableSequence auto-expansion."""
        items = [1, 2]
        set_key(items, 5, 'x')
        assert items == [1, 2, MISSING, MISSING, MISSING, 'x']

    def test_set_in_sequence_invalid_key_type(self):
        """Test set_key() with Sequence raises TypeError for non-int key."""
        items = [10, 20, 30]
        with pytest.raises(TypeError, match="Sequence indices must be int"):
            set_key(items, "not_an_int", 99)

    def test_set_invalid_container(self):
        """Test set_key() raises TypeError for invalid container."""
        with pytest.raises(TypeError, match="Expected a MutableMapping or MutableSequence container"):
            set_key(123, "key", "value")

    def test_get_set_together(self):
        """Test get_key() and set_key() working together."""
        # Create sparse list
        items = []
        set_key(items, 3, "third")
        set_key(items, 1, "first")
        set_key(items, 5, "fifth")

        # Get values
        assert get_key(items, 1) == "first"
        assert get_key(items, 3) == "third"
        assert get_key(items, 5) == "fifth"
        assert get_key(items, 0) is MISSING
        assert get_key(items, 2) is MISSING
        assert get_key(items, 4) is MISSING
