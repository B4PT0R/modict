"""Subpackage hosting shared collection/path utilities."""

from .src._missing import MISSING

from .src._basic import (
    get_key,
    set_key,
    has_key,
    keys,
    unroll,
)
from .src._types import (
    Key,
    KeyType,
    PathType,
    Container,
    MutableContainer,
    Namespace,
    MutableCollection,
    is_container,
    is_mutable_container,
    is_dict_like,
    is_list_like,
)

from ...path_utils import (
    Path,
    PathKey,
    PathNode,
    is_identifier,
    ensure_absolute,
)

from .src._view import View

from .src._advanced import (
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

from .src._json import (
    to_jsonable,
    json_dumps,
)

__all__ = [
    "Key",
    "Container",
    "MutableContainer",
    "Namespace",
    "MutableCollection",
    "keys",
    "has_key",
    "get_key",
    "set_key",
    "is_container",
    "is_mutable_container",
    "is_dict_like",
    "is_list_like",
    "MISSING",
    "Path",
    "PathKey",
    "PathNode",
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
    "to_jsonable",
    "json_dumps",
    "unroll",
]
