from __future__ import annotations

from functools import lru_cache
from typing import Any

from jsonpath_ng import parse
from jsonpath_ng.jsonpath import Child, Fields, Index, JSONPath, Root, This

from .path import PathKey, MISSING


def keys_from_jsonpath(path: JSONPath) -> tuple[PathKey, ...]:
    if isinstance(path, (Root, This)):
        return ()
    if isinstance(path, Child):
        return keys_from_jsonpath(path.left) + keys_from_jsonpath(path.right)
    if isinstance(path, Fields):
        if len(path.fields) != 1:
            raise ValueError(f"Unsupported multi-field path: {path.fields!r}")
        return (path.fields[0],)
    if isinstance(path, Index):
        index = getattr(path, "index", MISSING)
        if index is not MISSING:
            return (index,)
        indices = getattr(path, "indices", None)
        if isinstance(indices, (tuple, list)) and len(indices) == 1:
            return (indices[0],)
        raise ValueError(f"Unsupported jsonpath_ng Index node shape: {path!r}")
    raise ValueError(f"Unsupported jsonpath_ng path node: {type(path).__name__}")


@lru_cache(maxsize=512)
def _keys_from_str_expr(expr: str) -> tuple[PathKey, ...]:
    return keys_from_jsonpath(parse(expr))


def keys_from_expr(expr: str | JSONPath) -> tuple[PathKey, ...]:
    if isinstance(expr, str):
        return _keys_from_str_expr(expr)
    return keys_from_jsonpath(expr)
