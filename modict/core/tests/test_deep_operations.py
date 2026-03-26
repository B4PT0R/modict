"""Test suite for modict deep operation methods: merge, diff, diffed, deep_equals."""

from ...core import modict
from ...collections_utils import MISSING


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
