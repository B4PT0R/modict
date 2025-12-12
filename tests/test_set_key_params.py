"""Test suite for set_key() with expand and filler parameters."""

import pytest
from modict._collections_utils import set_key, MISSING


class TestSetKeyExpand:
    """Tests for set_key() expand parameter."""

    def test_expand_true_default(self):
        """Test set_key with expand=True (default)."""
        items = [1, 2]
        set_key(items, 5, 'x')
        assert items == [1, 2, MISSING, MISSING, MISSING, 'x']
        assert items[2] is MISSING

    def test_expand_false_within_bounds(self):
        """Test set_key with expand=False and index within bounds."""
        items = [1, 2, 3]
        set_key(items, 1, 99, expand=False)
        assert items == [1, 99, 3]

    def test_expand_false_out_of_bounds(self):
        """Test set_key with expand=False raises IndexError for out-of-bounds index."""
        items = [1, 2]
        with pytest.raises(IndexError, match="Index 5 out of range for sequence of length 2 \\(expand=False\\)"):
            set_key(items, 5, 'x', expand=False)


class TestSetKeyFiller:
    """Tests for set_key() filler parameter."""

    def test_filler_none(self):
        """Test set_key with filler=None."""
        items = [1, 2]
        set_key(items, 6, 'y', filler=None)
        assert items == [1, 2, None, None, None, None, 'y']
        assert items[2] is None

    def test_filler_zero(self):
        """Test set_key with filler=0."""
        items = ['a', 'b']
        set_key(items, 5, 'z', filler=0)
        assert items == ['a', 'b', 0, 0, 0, 'z']

    def test_filler_string(self):
        """Test set_key with filler='...'."""
        items = [10]
        set_key(items, 3, 99, filler='...')
        assert items == [10, '...', '...', 99]


class TestSetKeyMapping:
    """Tests for set_key() with MutableMapping."""

    def test_mapping_ignores_expand_filler(self):
        """Test that MutableMapping ignores expand and filler parameters."""
        data = {"a": 1}
        set_key(data, "b", 2, expand=False, filler="ignored")
        assert data == {"a": 1, "b": 2}


class TestSetKeyEdgeCases:
    """Edge case tests for set_key()."""

    def test_index_at_length(self):
        """Test set_key with index exactly at length (no gap to fill)."""
        items = [1, 2]
        set_key(items, 2, 'x', filler='.')
        assert items == [1, 2, 'x']

    def test_multiple_expansions_different_fillers(self):
        """Test multiple expansions with different filler values."""
        items = []
        set_key(items, 0, 'first')  # No gap, just append
        set_key(items, 3, 'fourth', filler=None)  # Creates gap with None
        set_key(items, 6, 'seventh', filler=MISSING)  # Creates gap with MISSING

        # After first call: ['first']
        # After second call: ['first', None, None, 'fourth']
        # After third call: ['first', None, None, 'fourth', MISSING, MISSING, 'seventh']
        assert len(items) == 7
        assert items[0] == 'first'
        assert items[1] is None      # from second expansion (filler=None)
        assert items[2] is None      # from second expansion (filler=None)
        assert items[3] == 'fourth'
        assert items[4] is MISSING   # from third expansion (filler=MISSING)
        assert items[5] is MISSING   # from third expansion (filler=MISSING)
        assert items[6] == 'seventh'


class TestSetKeyBackwardCompatibility:
    """Tests for backward compatibility of set_key()."""

    def test_backward_compatible_no_params(self):
        """Test that old behavior (without parameters) still works."""
        items = [1, 2]
        set_key(items, 5, 'x')  # Uses default expand=True, filler=MISSING
        assert items == [1, 2, MISSING, MISSING, MISSING, 'x']
