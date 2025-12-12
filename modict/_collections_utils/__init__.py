"""Subpackage hosting shared collection/path utilities."""

from ._missing import MISSING

from ._basic import (
    get_key,
    set_key,
    has_key,
    keys,
    unroll,
)
from ._types import (
    Key,
    KeyType,
    PathType,
    Container,
    MutableContainer,
    is_container,
    is_mutable_container,
)

from ._path import (
    Path,
    PathKey,
    is_identifier,
    ensure_absolute,
)

from ._view import View

from ._advanced import (
    get_nested,
    set_nested,
    pop_nested,
    del_nested,
    has_nested,
    extract,
    exclude,
    walk,
    walked,
    first_keys,
    is_seq_based,
    unwalk,
    deep_equals,
    diff_nested,
    deep_merge,
)

__all__ = [
    "Key",
    "Container",
    "MutableContainer",
    "keys",
    "has_key",
    "get_key",
    "set_key",
    "is_container",
    "is_mutable_container",
    "MISSING",
    "Path",
    "PathKey",
    "is_identifier",
    "ensure_absolute",
    "View",
    "get_nested",
    "set_nested",
    "pop_nested",
    "del_nested",
    "has_nested",
    "extract",
    "exclude",
    "walk",
    "walked",
    "first_keys",
    "is_seq_based",
    "unwalk",
    "deep_equals",
    "diff_nested",
    "deep_merge",
    "unroll",
]
