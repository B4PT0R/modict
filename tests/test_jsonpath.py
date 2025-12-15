"""Comprehensive tests for JSONPath parsing and formatting.

Tests cover:
- Basic parsing and formatting
- The three disambiguation cases (d1, d2, d3)
- Edge cases (negative indices, empty paths, special characters)
- Round-trip conversion
"""

import pytest
from modict._collections_utils._path import (
    PathKey,
    Path,
    is_identifier
)

# Aliases for backward compatibility with tests
def parse_jsonpath(jsonpath: str) -> Path:
    """Alias for Path.from_jsonpath for test compatibility."""
    return Path.from_jsonpath(jsonpath)

def format_path_tuple(keys: tuple) -> str:
    """Convert a tuple of keys to a JSONPath string."""
    path = Path.from_tuple(keys)
    return path.to_jsonpath()

_is_simple_identifier = is_identifier  # Alias for old name


class TestPathKey:
    """Tests for PathKey dataclass."""

    def test_sequence_component(self):
        """Test creating a sequence component."""
        comp = PathKey(value=0, container_class=list)
        assert comp.value == 0
        assert comp.container_class == list

    def test_mapping_component(self):
        """Test creating a mapping component."""
        comp = PathKey(value='name', container_class=dict)
        assert comp.value == 'name'
        assert comp.container_class == dict

    def test_unknown_component(self):
        """Test creating an unknown container type component."""
        comp = PathKey(value='test', container_class=None)
        assert comp.value == 'test'
        assert comp.container_class is None

    def test_frozen(self):
        """Test that PathKey is immutable."""
        comp = PathKey(value='name', container_class=dict)
        with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
            comp.value = 'other'

    def test_invalid_value_type_raises(self):
        """PathKey rejects non-str/int values."""
        with pytest.raises(ValueError):
            PathKey(value=1.2, container_class=dict)  # type: ignore[arg-type]

    def test_resolve_container_mismatch(self):
        """Resolving with mismatched container_class raises TypeError."""
        comp = PathKey(value=0, container_class=list)
        with pytest.raises(TypeError):
            comp.resolve({"not": "a list"})

    def test_is_compatible(self):
        comp = PathKey(value=0, container_class=list)
        assert comp.is_compatible([1, 2])
        assert comp.is_compatible({"0": "val"}) is False


class TestPath:
    """Tests for Path class."""

    def test_to_tuple(self):
        """Test extracting tuple from Path."""
        path = Path.from_jsonpath('$.a[0].b')
        assert path.to_tuple() == ('a', 0, 'b')

    def test_len(self):
        """Test __len__ returns component count."""
        path = Path.from_jsonpath('$.a.b')
        assert len(path) == 2

    def test_getitem(self):
        """Test iteration over components."""
        path = Path.from_jsonpath('$.a[0]')
        components = list(path.components)
        assert components[0].value == 'a'
        assert components[1].value == 0

    def test_empty_path(self):
        """Test empty Path (root)."""
        path = Path.from_jsonpath('$')
        assert path.is_root
        assert path.to_tuple() == ()

    def test_equality_and_hash(self):
        """Paths with same components compare equal and are hashable."""
        p1 = Path.from_jsonpath('$.a[0].b')
        p2 = Path.from_tuple(('a', 0, 'b'))
        assert p1 == p2
        assert hash(p1) == hash(p2)


class TestParseJSONPath:
    """Tests for parse_jsonpath function."""

    def test_simple_keys(self):
        """Test parsing simple key access."""
        path = parse_jsonpath('$.a.b.c')
        assert path.to_tuple() == ('a', 'b', 'c')
        assert all(c.container_class == dict for c in path.components)

    def test_array_index(self):
        """Test parsing array index access."""
        path = parse_jsonpath('$.users[0].name')
        assert path.to_tuple() == ('users', 0, 'name')
        assert path.components[0].container_class == dict
        assert path.components[1].container_class == list
        assert path.components[2].container_class == dict

    def test_string_key_numeric(self):
        """Test parsing string key that looks like number."""
        path = parse_jsonpath("$.config['0'].value")
        assert path.to_tuple() == ('config', '0', 'value')
        assert path.components[1].container_class == dict
        assert path.components[1].value == '0'

    def test_multiple_array_indices(self):
        """Test parsing multiple consecutive array indices."""
        path = parse_jsonpath('$[0][1][2]')
        assert path.to_tuple() == (0, 1, 2)
        assert all(c.container_class == list for c in path.components)

    def test_negative_index(self):
        """Test parsing negative array index."""
        path = parse_jsonpath('$.items[-1]')
        assert path.to_tuple() == ('items', -1)
        assert path.components[1].container_class == list
        assert path.components[1].value == -1

    def test_root_only(self):
        """Test parsing root-only path."""
        path = parse_jsonpath('$')
        assert len(path) == 0
        assert path.to_tuple() == ()

    def test_invalid_jsonpath_raises(self):
        """JSONPath must start with '$'."""
        with pytest.raises(ValueError):
            parse_jsonpath("a.b")

    def test_mixed_access(self):
        """Test parsing mixed key and index access."""
        path = parse_jsonpath('$.data.items[0].metadata.tags[1]')
        assert path.to_tuple() == ('data', 'items', 0, 'metadata', 'tags', 1)
        assert path.components[0].container_class == dict  # data
        assert path.components[1].container_class == dict  # items
        assert path.components[2].container_class == list  # 0
        assert path.components[3].container_class == dict  # metadata
        assert path.components[4].container_class == dict  # tags
        assert path.components[5].container_class == list  # 1


class TestFormatPathTuple:
    """Tests for format_path_tuple function."""

    def test_simple_keys(self):
        """Test formatting simple key tuple."""
        result = format_path_tuple(('a', 'b', 'c'))
        assert result == '$.a.b.c'

    def test_with_array_index(self):
        """Test formatting with array index."""
        result = format_path_tuple(('users', 0, 'name'))
        assert result == '$.users[0].name'

    def test_string_key_numeric(self):
        """Test formatting string key that looks like number."""
        result = format_path_tuple(('config', '0', 'value'))
        assert result == "$.config['0'].value"

    def test_multiple_indices(self):
        """Test formatting multiple consecutive indices."""
        result = format_path_tuple((0, 1, 2))
        assert result == '$[0][1][2]'

    def test_negative_index(self):
        """Test formatting negative index."""
        result = format_path_tuple(('items', -1))
        assert result == '$.items[-1]'

    def test_empty_tuple(self):
        """Test formatting empty tuple."""
        result = format_path_tuple(())
        assert result == '$'

    def test_special_characters_in_key(self):
        """Test formatting keys with special characters."""
        result = format_path_tuple(('my-key', 'another.key'))
        assert result == "$['my-key']['another.key']"

    def test_underscore_in_key(self):
        """Test that underscores are allowed in simple identifiers."""
        result = format_path_tuple(('user_id', 'first_name'))
        assert result == '$.user_id.first_name'

    def test_invalid_type_in_tuple(self):
        """Test that non-str/int types raise ValueError."""
        with pytest.raises(ValueError, match="Invalid key type"):
            format_path_tuple(('a', 1.5, 'b'))


class TestIsSimpleIdentifier:
    """Tests for _is_simple_identifier helper function."""

    def test_simple_name(self):
        """Test simple alphabetic name."""
        assert _is_simple_identifier('name') is True

    def test_with_underscore(self):
        """Test name with underscores."""
        assert _is_simple_identifier('user_id') is True
        assert _is_simple_identifier('_private') is True

    def test_with_numbers(self):
        """Test name with numbers (not starting with digit)."""
        assert _is_simple_identifier('value1') is True
        assert _is_simple_identifier('test123') is True

    def test_numeric_string(self):
        """Test that numeric strings are not simple identifiers."""
        assert _is_simple_identifier('0') is False
        assert _is_simple_identifier('123') is False

    def test_starts_with_digit(self):
        """Test that strings starting with digit are not simple identifiers."""
        assert _is_simple_identifier('1abc') is False

    def test_special_characters(self):
        """Test that special characters disqualify simple identifier."""
        assert _is_simple_identifier('my-key') is False
        assert _is_simple_identifier('my.key') is False
        assert _is_simple_identifier('my key') is False

    def test_empty_string(self):
        """Test that empty string is not a simple identifier."""
        assert _is_simple_identifier('') is False


class TestRoundTrip:
    """Tests for round-trip conversion (parse → format, format → parse)."""

    def test_simple_path(self):
        """Test round-trip of simple path."""
        original = '$.a.b.c'
        path = parse_jsonpath(original)
        formatted = path.to_jsonpath()
        assert formatted == original

    def test_with_indices(self):
        """Test round-trip with array indices."""
        original = '$.users[0].posts[1].title'
        path = parse_jsonpath(original)
        formatted = path.to_jsonpath()
        assert formatted == original

    def test_numeric_string_keys(self):
        """Test round-trip with numeric string keys."""
        original = "$.config['0'].value"
        path = parse_jsonpath(original)
        formatted = path.to_jsonpath()
        assert formatted == original

    def test_tuple_to_path_and_back(self):
        """Test tuple → JSONPath → tuple."""
        original_tuple = ('data', 'items', 0, 'name')
        formatted = format_path_tuple(original_tuple)
        path = parse_jsonpath(formatted)
        assert path.to_tuple() == original_tuple


class TestDisambiguationCases:
    """Tests for the three critical disambiguation cases from the problem statement."""

    def test_d1_array_with_dict(self):
        """Test d1: {'a': [{'b': 'target'}]} → $.a[0].b"""
        # This is the JSONPath for accessing array index 0
        path = parse_jsonpath('$.a[0].b')

        assert path.to_tuple() == ('a', 0, 'b')
        assert path.components[0].value == 'a'
        assert path.components[0].container_class == dict
        assert path.components[1].value == 0
        assert path.components[1].container_class == list  # This is an array index!
        assert path.components[2].value == 'b'
        assert path.components[2].container_class == dict

    def test_d2_dict_with_int_key(self):
        """Test d2: {'a': {0: {'b': 'target'}}} → Direct assignment required

        Note: Integer keys in dicts cannot be represented in JSONPath.
        This is a documented limitation - users must use direct dict access.
        """
        # JSONPath $[0] always means array index, not int key
        # For int keys in dicts, users must use: d['a'][0] = {'b': 'target'}
        pass  # No JSONPath representation for int keys in dicts

    def test_d3_dict_with_string_key(self):
        """Test d3: {'a': {'0': {'b': 'target'}}} → $.a['0'].b"""
        # This is the JSONPath for accessing string key '0'
        path = parse_jsonpath("$.a['0'].b")

        assert path.to_tuple() == ('a', '0', 'b')
        assert path.components[0].value == 'a'
        assert path.components[0].container_class == dict
        assert path.components[1].value == '0'  # String '0'
        assert path.components[1].container_class == dict  # This is a string key!
        assert path.components[2].value == 'b'
        assert path.components[2].container_class == dict

    def test_disambiguation_formatting(self):
        """Test that format_path_tuple disambiguates correctly."""
        # Array index (int 0)
        path1 = format_path_tuple(('a', 0, 'b'))
        assert path1 == '$.a[0].b'

        # String key '0'
        path2 = format_path_tuple(('a', '0', 'b'))
        assert path2 == "$.a['0'].b"

        # These are different paths!
        assert path1 != path2

    def test_disambiguation_parsing(self):
        """Test that parse_jsonpath disambiguates correctly."""
        # Array index
        path1 = parse_jsonpath('$.a[0].b')
        assert path1.components[1].container_class == list
        assert path1.components[1].value == 0

        # String key
        path2 = parse_jsonpath("$.a['0'].b")
        assert path2.components[1].container_class == dict
        assert path2.components[1].value == '0'

        # Different types!
        assert path1.components[1].container_class != path2.components[1].container_class


class TestEdgeCases:
    """Tests for various edge cases."""

    def test_deeply_nested_path(self):
        """Test very deep nesting."""
        path = parse_jsonpath('$.a.b.c.d.e.f.g.h.i.j')
        assert len(path) == 10
        assert path.to_tuple() == ('a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j')

    def test_many_indices(self):
        """Test many consecutive indices."""
        path = parse_jsonpath('$[0][1][2][3][4]')
        assert path.to_tuple() == (0, 1, 2, 3, 4)
        assert all(c.container_class == list for c in path.components)

    def test_unicode_keys(self):
        """Test Unicode characters in keys."""
        result = format_path_tuple(('données', 'utilisateur'))
        assert 'données' in result
        assert 'utilisateur' in result

    def test_very_large_index(self):
        """Test very large array index."""
        path = parse_jsonpath('$.items[999999]')
        assert path.components[1].value == 999999
        assert path.components[1].container_class == list

    def test_single_key_path(self):
        """Test single key access."""
        path = parse_jsonpath('$.name')
        assert path.to_tuple() == ('name',)
        assert path.components[0].container_class == dict

    def test_single_index_path(self):
        """Test single index access."""
        path = parse_jsonpath('$[0]')
        assert path.to_tuple() == (0,)
        assert path.components[0].container_class == list
