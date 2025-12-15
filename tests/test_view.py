"""Tests for the generic View helper."""

import pytest

from modict._collections_utils._view import View


class KeysView(View[dict, str]):
    def _get_element(self, key):
        return key


class ValuesView(View[dict, int]):
    def _get_element(self, key):
        return self.data[key]


def test_view_iter_len_contains():
    data = {"a": 1, "b": 2}
    keys_view = KeysView(data)
    values_view = ValuesView(data)

    assert list(keys_view) == ["a", "b"]
    assert len(keys_view) == 2
    assert 2 in values_view
    assert 3 not in values_view


def test_view_repr_truncates():
    data = {str(i): i for i in range(12)}
    keys_view = KeysView(data)
    rep = repr(keys_view)
    assert rep.startswith("KeysView(")
    assert "..." in rep  # truncated after _nmax elements


def test_view_invalid_container():
    with pytest.raises(TypeError):
        KeysView(123)  # type: ignore[arg-type]
