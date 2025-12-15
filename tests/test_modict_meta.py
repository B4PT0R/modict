"""Tests for modict metaclass utilities (config and views)."""

import warnings
from modict import modict
from modict._modict_meta import modictConfig


def test_modictconfig_backward_compatibility():
    """Test that allow_extra parameter still works with deprecation warning."""
    # Test allow_extra=True → extra='allow'
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        config = modictConfig(allow_extra=True)
        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)
        assert "allow_extra" in str(w[0].message)
        assert config.extra == 'allow'

    # Test allow_extra=False → extra='forbid'
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        config = modictConfig(allow_extra=False)
        assert len(w) == 1
        assert config.extra == 'forbid'

    # Test that explicit extra parameter takes precedence
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        config = modictConfig(allow_extra=True, extra='ignore')
        assert len(w) == 1
        assert config.extra == 'ignore'  # extra wins


def test_modictconfig_copy_and_merge():
    base = modictConfig(strict=True, extra='forbid')
    copy_cfg = base.copy()

    assert copy_cfg.strict is True
    assert copy_cfg.extra == 'forbid'
    assert copy_cfg._explicit == base._explicit

    other = modictConfig(strict=False)
    merged = base.merge(other)

    # explicit fields from other override, rest from base
    assert merged.strict is False
    assert merged.extra == 'forbid'
    # _explicit union
    assert merged._explicit == base._explicit | other._explicit


def test_modict_views_reflect_mutations():
    m = modict(a=1, b=2)
    keys_view = m.keys()
    values_view = m.values()
    items_view = m.items()

    assert len(keys_view) == 2
    assert "a" in keys_view
    assert 2 in values_view
    assert ("a", 1) in items_view

    m["c"] = 3
    assert "c" in keys_view
    assert 3 in values_view
    assert ("c", 3) in items_view
