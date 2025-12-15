"""Test suite for Path.normalize() classmethod."""

import pytest
from modict._collections_utils import Path, get_nested


class TestPathNormalize:
    """Tests for Path.normalize() classmethod."""

    def test_normalize_jsonpath_string(self):
        """Test Path.normalize() with JSONPath string."""
        path = Path.normalize("$.users[0].name")
        assert isinstance(path, Path)
        assert str(path) == "$.users[0].name"

    def test_normalize_tuple(self):
        """Test Path.normalize() with tuple."""
        path = Path.normalize(('users', 0, 'name'))
        assert isinstance(path, Path)
        assert len(path.components) == 3

    def test_normalize_path_object(self):
        """Test Path.normalize() with Path object (should return same object)."""
        path1 = Path.from_jsonpath("$.a.b.c")
        path2 = Path.normalize(path1)
        assert path2 is path1  # Should return the same object
        assert str(path2) == "$.a.b.c"

    def test_normalize_invalid_type_int(self):
        """Test Path.normalize() with invalid type (int)."""
        with pytest.raises(TypeError, match="Path must be a str, tuple, or Path object"):
            Path.normalize(123)

    def test_normalize_invalid_type_list(self):
        """Test Path.normalize() with invalid type (list)."""
        with pytest.raises(TypeError, match="Path must be a str, tuple, or Path object"):
            Path.normalize(['a', 'b', 'c'])

    def test_normalize_preserves_metadata(self):
        """Test that Path.normalize() preserves container type metadata."""
        jsonpath_str = "$.data[0].items['key']"
        path = Path.normalize(jsonpath_str)

        assert path.components[0].value == 'data'
        assert path.components[0].container_class == dict
        assert path.components[1].value == 0
        assert path.components[1].container_class == list
        assert path.components[2].value == 'items'
        assert path.components[2].container_class == dict
        assert path.components[3].value == 'key'
        assert path.components[3].container_class == dict

    def test_normalize_empty_tuple(self):
        """Test Path.normalize() with empty tuple (root path)."""
        root_path = Path.normalize(())
        assert root_path.is_root
        assert str(root_path) == "$"

    def test_normalize_root_jsonpath(self):
        """Test Path.normalize() with root JSONPath string."""
        root_path = Path.normalize("$")
        assert root_path.is_root
        assert str(root_path) == "$"

    def test_normalize_in_get_nested(self):
        """Test that Path.normalize() works correctly in get_nested()."""
        data = {"users": [{"name": "Alice", "age": 30}]}

        # All these should work the same way
        result1 = get_nested(data, "$.users[0].name")
        result2 = get_nested(data, ("users", 0, "name"))
        result3 = get_nested(data, Path.from_jsonpath("$.users[0].name"))

        assert result1 == result2 == result3 == "Alice"
