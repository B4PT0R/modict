from __future__ import annotations

import pytest

from modict.collections_utils.src._types import (
    MutableCollection,
    Namespace,
    is_container,
    is_dict_like,
    is_list_like,
    is_mutable_container,
)


class Holder:
    value = 1


def test_namespace_supports_mapping_protocol_and_mutations():
    namespace = Namespace(Holder)

    assert namespace["value"] == 1
    assert "value" in namespace
    assert len(namespace) >= 1
    assert "value" in list(namespace)

    namespace["extra"] = 2
    assert Holder.extra == 2

    del namespace["extra"]
    assert not hasattr(Holder, "extra")


def test_namespace_missing_keys_raise_keyerror():
    namespace = Namespace(Holder)

    with pytest.raises(KeyError):
        namespace["missing"]

    with pytest.raises(KeyError):
        del namespace["missing"]


def test_mutable_collection_is_abstract():
    with pytest.raises(TypeError):
        MutableCollection()


def test_container_helpers_distinguish_mutable_and_excluded_types():
    assert is_container({"a": 1}) is True
    assert is_container([1, 2]) is True
    assert is_container("abc") is False
    assert is_container(("a", "b"), excluded=(tuple,)) is False

    assert is_mutable_container({"a": 1}) is True
    assert is_mutable_container([1, 2]) is True
    assert is_mutable_container((1, 2)) is False

    assert is_dict_like({"a": 1}) is True
    assert is_dict_like([1, 2]) is False

    assert is_list_like([1, 2]) is True
    assert is_list_like({"a": 1}) is False
