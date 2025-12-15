"""Tests for container type preservation in walk/unwalk operations."""

import pytest
from collections import OrderedDict, UserDict, UserList
from modict._collections_utils._advanced import walk, walked, unwalk


class CustomDict(dict):
    """Custom dict subclass for testing."""
    pass


class CustomList(list):
    """Custom list subclass for testing."""
    pass


class TestContainerTypePreservation:
    """Test that walk/unwalk preserves exact container types."""

    def test_preserve_ordered_dict(self):
        """Test that OrderedDict is preserved through walk/unwalk."""
        original = OrderedDict([('x', 1), ('y', 2), ('z', 3)])
        walked_data = walked(original)
        reconstructed = unwalk(walked_data)
        
        assert type(reconstructed) == OrderedDict
        assert list(reconstructed.keys()) == ['x', 'y', 'z']

    def test_preserve_user_dict(self):
        """Test that UserDict is preserved through walk/unwalk."""
        original = UserDict({'a': 1, 'b': 2})
        walked_data = walked(original)
        reconstructed = unwalk(walked_data)
        
        assert type(reconstructed) == UserDict
        assert reconstructed['a'] == 1

    def test_preserve_user_list(self):
        """Test that UserList is preserved through walk/unwalk."""
        original = UserList([10, 20, 30])
        walked_data = walked(original)
        reconstructed = unwalk(walked_data)
        
        assert type(reconstructed) == UserList
        assert list(reconstructed) == [10, 20, 30]

    def test_preserve_custom_types(self):
        """Test that custom dict/list subclasses are preserved."""
        original = CustomDict({'items': CustomList([1, 2, 3])})
        walked_data = walked(original)
        reconstructed = unwalk(walked_data)
        
        assert type(reconstructed) == CustomDict
        assert type(reconstructed['items']) == CustomList
        assert list(reconstructed['items']) == [1, 2, 3]

    def test_preserve_nested_mixed_types(self):
        """Test preservation of nested structures with mixed container types."""
        original = {
            'config': OrderedDict([('x', 1), ('y', 2)]),
            'data': UserDict({'items': UserList([4, 5, 6])}),
            'plain': {'a': [7, 8, 9]}
        }
        
        walked_data = walked(original)
        reconstructed = unwalk(walked_data)
        
        assert type(reconstructed) == dict
        assert type(reconstructed['config']) == OrderedDict
        assert type(reconstructed['data']) == UserDict
        assert type(reconstructed['data']['items']) == UserList
        assert type(reconstructed['plain']) == dict
        assert type(reconstructed['plain']['a']) == list

    def test_container_class_captured_in_path(self):
        """Test that container classes are captured in Path components."""
        original = OrderedDict([('items', UserList([1, 2]))])
        walked_data = walked(original)
        
        # Check that container classes are captured
        for path, value in walked_data.items():
            if len(path.components) >= 1:
                # First component should be OrderedDict
                assert path.components[0].container_class == OrderedDict
            if len(path.components) >= 2:
                # Second component should be UserList
                assert path.components[1].container_class == UserList

    def test_ambiguous_paths_use_none(self):
        """Test that paths created from tuples have None for ambiguous int keys."""
        from modict._collections_utils._path import Path
        
        # String key → dict
        path1 = Path.from_tuple(('a',))
        assert path1.components[0].container_class == dict
        
        # Integer key → ambiguous (None)
        path2 = Path.from_tuple((0,))
        assert path2.components[0].container_class is None

    def test_jsonpath_parsing_uses_default_types(self):
        """Test that JSONPath parsing uses dict/list as defaults."""
        from modict._collections_utils._path import Path
        
        path = Path.from_jsonpath("$.users[0].name")
        
        # 'users' → dict
        assert path.components[0].container_class == dict
        # [0] → list
        assert path.components[1].container_class == list
        # 'name' → dict
        assert path.components[2].container_class == dict
