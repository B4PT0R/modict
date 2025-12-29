"""Test suite for deep operations: merge, diff, diffed, and deep_equals.

This module tests the deep manipulation operations on nested structures,
with particular focus on the MISSING sentinel value for deletions.
"""

import pytest
from modict import modict
from modict._collections_utils import (
    deep_merge,
    diff_nested,
    deep_equals,
    MISSING,
    Path,
)


class TestDeepMerge:
    """Tests for deep_merge() function."""

    def test_simple_merge_dict(self):
        """Test basic dictionary merge."""
        target = {'a': 1, 'b': 2}
        src = {'b': 3, 'c': 4}
        deep_merge(target, src)
        assert target == {'a': 1, 'b': 3, 'c': 4}

    def test_nested_merge_dict(self):
        """Test nested dictionary merge."""
        target = {'a': 1, 'b': {'x': 10, 'y': 20}}
        src = {'b': {'y': 30, 'z': 40}, 'c': 3}
        deep_merge(target, src)
        assert target == {'a': 1, 'b': {'x': 10, 'y': 30, 'z': 40}, 'c': 3}

    def test_merge_list(self):
        """Test list merge by index."""
        target = [1, 2, 3]
        src = [10, 20]
        deep_merge(target, src)
        assert target == [10, 20, 3]

    def test_merge_list_append(self):
        """Test list merge with append."""
        target = [1, 2]
        src = [10, 20, 30, 40]
        deep_merge(target, src)
        assert target == [10, 20, 30, 40]

    def test_merge_nested_list_dict(self):
        """Test merge with nested lists and dicts."""
        target = {'items': [{'a': 1}, {'b': 2}]}
        src = {'items': [{'a': 10}, {'b': 20, 'c': 30}]}
        deep_merge(target, src)
        assert target == {'items': [{'a': 10}, {'b': 20, 'c': 30}]}


class TestDeepMergeWithMISSING:
    """Tests for deep_merge() with MISSING sentinel for deletions."""

    def test_delete_key_with_missing(self):
        """Test deleting a key using MISSING."""
        target = {'a': 1, 'b': 2, 'c': 3}
        src = {'b': MISSING, 'd': 4}
        deep_merge(target, src)
        assert target == {'a': 1, 'c': 3, 'd': 4}
        assert 'b' not in target

    def test_delete_multiple_keys_with_missing(self):
        """Test deleting multiple keys using MISSING."""
        target = {'a': 1, 'b': 2, 'c': 3, 'd': 4}
        src = {'b': MISSING, 'd': MISSING}
        deep_merge(target, src)
        assert target == {'a': 1, 'c': 3}

    def test_delete_nested_key_with_missing(self):
        """Test deleting a nested key using MISSING."""
        target = {'a': 1, 'b': {'x': 10, 'y': 20, 'z': 30}}
        src = {'b': {'y': MISSING}}
        deep_merge(target, src)
        assert target == {'a': 1, 'b': {'x': 10, 'z': 30}}
        assert 'y' not in target['b']

    def test_delete_deeply_nested_key_with_missing(self):
        """Test deleting a deeply nested key using MISSING."""
        target = {
            'level1': {
                'level2': {
                    'level3': {
                        'a': 1,
                        'b': 2,
                        'c': 3
                    }
                }
            }
        }
        src = {'level1': {'level2': {'level3': {'b': MISSING}}}}
        deep_merge(target, src)
        assert target == {
            'level1': {
                'level2': {
                    'level3': {
                        'a': 1,
                        'c': 3
                    }
                }
            }
        }

    def test_delete_nonexistent_key_with_missing(self):
        """Test that deleting a non-existent key with MISSING is safe."""
        target = {'a': 1, 'b': 2}
        src = {'c': MISSING, 'd': 3}
        deep_merge(target, src)
        assert target == {'a': 1, 'b': 2, 'd': 3}

    def test_delete_from_list_with_missing(self):
        """Test deleting from a list using MISSING."""
        target = [1, 2, 3, 4, 5]
        src = [MISSING, 10, MISSING]
        deep_merge(target, src)
        # Indices 0 and 2 deleted, index 1 replaced
        assert target == [10, 4, 5]

    def test_delete_from_nested_list_with_missing(self):
        """Test deleting from nested list structures."""
        target = {'items': [{'a': 1}, {'b': 2}, {'c': 3}]}
        src = {'items': [MISSING, {'b': 20}]}
        deep_merge(target, src)
        assert target == {'items': [{'b': 20}, {'c': 3}]}

    def test_delete_multiple_list_indices_with_missing(self):
        """Test deleting multiple indices from a list."""
        target = [10, 20, 30, 40, 50]
        src = [MISSING, MISSING, 300, MISSING]
        deep_merge(target, src)
        # Indices 0, 1, 3 deleted, index 2 replaced
        assert target == [300, 50]

    def test_mixed_merge_and_delete(self):
        """Test combining merge and delete operations."""
        target = {
            'keep': 1,
            'update': 2,
            'delete': 3,
            'nested': {
                'keep': 10,
                'delete': 20
            }
        }
        src = {
            'update': 22,
            'delete': MISSING,
            'add': 4,
            'nested': {
                'delete': MISSING,
                'add': 30
            }
        }
        deep_merge(target, src)
        assert target == {
            'keep': 1,
            'update': 22,
            'add': 4,
            'nested': {
                'keep': 10,
                'add': 30
            }
        }


class TestDiffNested:
    """Tests for diff_nested() function."""

    def test_diff_identical_dicts(self):
        """Test diff of identical dictionaries."""
        dict1 = {'a': 1, 'b': 2}
        dict2 = {'a': 1, 'b': 2}
        diffs = diff_nested(dict1, dict2)
        assert diffs == {}

    def test_diff_simple_change(self):
        """Test diff with simple value change."""
        dict1 = {'a': 1, 'b': 2}
        dict2 = {'a': 1, 'b': 3}
        diffs = diff_nested(dict1, dict2)
        assert len(diffs) == 1
        assert Path.from_jsonpath('$.b') in diffs
        assert diffs[Path.from_jsonpath('$.b')] == (2, 3)

    def test_diff_added_key(self):
        """Test diff with added key."""
        dict1 = {'a': 1}
        dict2 = {'a': 1, 'b': 2}
        diffs = diff_nested(dict1, dict2)
        assert len(diffs) == 1
        assert Path.from_jsonpath('$.b') in diffs
        assert diffs[Path.from_jsonpath('$.b')] == (MISSING, 2)

    def test_diff_removed_key(self):
        """Test diff with removed key."""
        dict1 = {'a': 1, 'b': 2}
        dict2 = {'a': 1}
        diffs = diff_nested(dict1, dict2)
        assert len(diffs) == 1
        assert Path.from_jsonpath('$.b') in diffs
        assert diffs[Path.from_jsonpath('$.b')] == (2, MISSING)

    def test_diff_nested_change(self):
        """Test diff with nested change."""
        dict1 = {'a': {'x': 1, 'y': 2}}
        dict2 = {'a': {'x': 1, 'y': 3}}
        diffs = diff_nested(dict1, dict2)
        assert len(diffs) == 1
        assert Path.from_jsonpath('$.a.y') in diffs
        assert diffs[Path.from_jsonpath('$.a.y')] == (2, 3)

    def test_diff_complex(self):
        """Test diff with complex nested structure."""
        dict1 = {
            'a': 1,
            'b': {'x': 10, 'y': 20},
            'c': 3
        }
        dict2 = {
            'a': 1,
            'b': {'x': 10, 'y': 30},
            'd': 4
        }
        diffs = diff_nested(dict1, dict2)
        assert len(diffs) == 3  # b.y changed, c removed, d added
        assert Path.from_jsonpath('$.b.y') in diffs
        assert Path.from_jsonpath('$.c') in diffs
        assert Path.from_jsonpath('$.d') in diffs


class TestDeepEquals:
    """Tests for deep_equals() function."""

    def test_deep_equals_identical(self):
        """Test deep_equals with identical structures."""
        dict1 = {'a': [1, 2, {'b': 3}], 'c': 4}
        dict2 = {'a': [1, 2, {'b': 3}], 'c': 4}
        assert deep_equals(dict1, dict2)

    def test_deep_equals_different(self):
        """Test deep_equals with different structures."""
        dict1 = {'a': [1, 2, {'b': 3}]}
        dict2 = {'a': [1, 2, {'b': 4}]}
        assert not deep_equals(dict1, dict2)

    def test_deep_equals_nested(self):
        """Test deep_equals with nested structures."""
        dict1 = {
            'level1': {
                'level2': {
                    'level3': [1, 2, 3]
                }
            }
        }
        dict2 = {
            'level1': {
                'level2': {
                    'level3': [1, 2, 3]
                }
            }
        }
        assert deep_equals(dict1, dict2)


class TestModictDeepOperations:
    """Tests for modict deep operation methods."""

    def test_modict_merge(self):
        """Test modict.merge() method."""
        m = modict(a=1, b=modict(x=1))
        m.merge({'b': {'y': 2}, 'c': 3})
        assert m == {'a': 1, 'b': {'x': 1, 'y': 2}, 'c': 3}

    def test_modict_merge_with_missing(self):
        """Test modict.merge() with MISSING."""
        m = modict(a=1, b=2, c=3)
        m.merge({'b': MISSING, 'd': 4})
        assert m == {'a': 1, 'c': 3, 'd': 4}

    def test_modict_merge_nested_missing(self):
        """Test modict.merge() with nested MISSING."""
        m = modict(
            user=modict(
                name='Alice',
                email='alice@example.com',
                age=30
            )
        )
        m.merge({'user': {'email': MISSING}})
        assert m == {'user': {'name': 'Alice', 'age': 30}}

    def test_modict_diff(self):
        """Test modict.diff() method."""
        m1 = modict(x=1, y=modict(z=2))
        m2 = modict(x=1, y=modict(z=3), w=4)
        diffs = m1.diff(m2)
        assert len(diffs) == 2

    def test_modict_diffed(self):
        """Test modict.diffed() method."""
        m1 = modict(x=1, y=modict(z=2, t=5), w=4)
        m2 = modict(x=2, y=modict(z=3, t=5), u=6)
        diff = m1.diffed(m2)

        # Verify that diff contains the changes needed
        assert isinstance(diff, modict)
        # The diff should contain paths as keys when returned from diffed

    def test_modict_diffed_roundtrip(self):
        """Test that diffed + merge produces the target structure."""
        m1 = modict(x=1, y=modict(z=2, t=5), w=4)
        m2 = modict(x=2, y=modict(z=3, t=5), u=6)

        # Get the diff
        diff = m1.diffed(m2)

        # Apply the diff to a copy of m1
        m1_copy = m1.deepcopy()
        m1_copy.merge(diff)

        # m1_copy should now equal m2
        assert m1_copy.deep_equals(m2)
        assert m1_copy == m2

    def test_modict_deep_equals(self):
        """Test modict.deep_equals() method."""
        m1 = modict(a=[1, modict(b=2)])
        m2 = {'a': [1, {'b': 2}]}
        assert m1.deep_equals(m2)

    def test_modict_deep_equals_false(self):
        """Test modict.deep_equals() returns False for different structures."""
        m1 = modict(a=[1, modict(b=2)])
        m2 = modict(a=[1, modict(b=3)])
        assert not m1.deep_equals(m2)


class TestIgnoreTypes:
    """Tests for ignore_types parameter in unwalk and diffed."""

    def test_unwalk_with_ignore_types(self):
        """Test that ignore_types prevents modict reconstruction."""
        from modict._collections_utils import Path, unwalk

        # Create walked data with modict container_class
        walked = {
            Path.from_jsonpath('$.x'): 1,
            Path.from_jsonpath('$.y.z'): 2,
        }

        # Without ignore_types (default)
        result_with_types = unwalk(walked, ignore_types=False)
        # Should work fine
        assert 'x' in result_with_types

        # With ignore_types
        result_without_types = unwalk(walked, ignore_types=True)
        assert 'x' in result_without_types
        assert isinstance(result_without_types, dict)

    def test_diffed_with_modict_defaults(self):
        """Test that diffed() works correctly with modict classes having defaults."""
        # Define a modict class with defaults
        class Config(modict):
            api_url: str = 'https://api.example.com'
            timeout: int = 30
            debug: bool = True

        c1 = Config(api_url='https://old.com', timeout=10, debug=False)
        c2 = Config(api_url='https://new.com', timeout=10)  # debug=True (default)

        # Get diff
        diff = c1.diffed(c2)

        # Apply diff
        c1_copy = c1.deepcopy()
        c1_copy.merge(diff)

        # Should be equal
        assert c1_copy.deep_equals(c2)
        assert dict(c1_copy) == dict(c2)

    def test_diffed_ignores_container_types(self):
        """Test that diffed() returns plain dicts to avoid default injection."""
        m1 = modict(x=1, y=modict(z=2, t=5), w=4)
        m2 = modict(x=2, y=modict(z=3, t=5), u=6)

        diff = m1.diffed(m2)

        # The diff should contain a nested structure
        assert 'y' in diff
        # The nested 'y' should only have changed values, not defaults
        assert 'z' in diff['y']
        assert 't' not in diff['y']  # t unchanged, should not be in diff


class TestComplexScenarios:
    """Tests for complex real-world scenarios."""

    def test_config_update_scenario(self):
        """Test a configuration update scenario."""
        config = modict(
            api_url='https://api.example.com',
            timeout=30,
            retry_count=3,
            debug=True,
            features=modict(
                auth=True,
                logging=True,
                caching=False
            )
        )

        # Update: remove debug, update timeout, add features
        updates = {
            'debug': MISSING,
            'timeout': 60,
            'features': {
                'caching': True,
                'analytics': True
            }
        }

        config.merge(updates)

        assert 'debug' not in config
        assert config.timeout == 60
        assert config.features.caching is True
        assert config.features.analytics is True
        assert config.features.auth is True

    def test_user_preferences_scenario(self):
        """Test a user preferences update scenario."""
        preferences = modict(
            theme='dark',
            notifications=modict(
                email=True,
                sms=True,
                push=True
            ),
            privacy=modict(
                show_email=False,
                show_phone=True
            )
        )

        # User disables SMS and push, removes privacy.show_phone
        updates = {
            'notifications': {
                'sms': MISSING,
                'push': MISSING
            },
            'privacy': {
                'show_phone': MISSING
            }
        }

        preferences.merge(updates)

        assert preferences.notifications == {'email': True}
        assert preferences.privacy == {'show_email': False}

    def test_version_diff_scenario(self):
        """Test capturing version differences."""
        v1 = modict(
            version='1.0.0',
            features=modict(
                auth=True,
                api=True,
                ui=True
            ),
            beta=True
        )

        v2 = modict(
            version='2.0.0',
            features=modict(
                auth=True,
                api=True,
                ml=True
            ),
            stable=True
        )

        # Get the diff needed to upgrade v1 to v2
        upgrade_patch = v1.diffed(v2)

        # Apply the patch
        v1_upgraded = v1.deepcopy()
        v1_upgraded.merge(upgrade_patch)

        # Should be identical to v2
        assert v1_upgraded.deep_equals(v2)
        assert 'ui' not in v1_upgraded.features
        assert v1_upgraded.features.ml is True
        assert 'beta' not in v1_upgraded
        assert v1_upgraded.stable is True

    def test_list_of_modicts_with_missing(self):
        """Test merging lists containing modict instances."""
        data = modict(
            items=[
                modict(id=1, name='Item 1', active=True),
                modict(id=2, name='Item 2', active=True),
                modict(id=3, name='Item 3', active=False)
            ]
        )

        # Remove first item, update second
        updates = {
            'items': [
                MISSING,
                modict(active=False)
            ]
        }

        data.merge(updates)

        assert len(data['items']) == 2
        assert data['items'][0]['id'] == 2
        assert data['items'][0]['active'] is False
        assert data['items'][1]['id'] == 3
