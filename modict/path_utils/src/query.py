from __future__ import annotations

from typing import Any

from jsonpath_ng import parse
from jsonpath_ng.jsonpath import JSONPath

from .path import Path
from ._jsonpath import keys_from_jsonpath


def find_paths(root: Any, jsonpath_expr: str | JSONPath) -> tuple[Path, ...]:
    expr = parse(jsonpath_expr) if isinstance(jsonpath_expr, str) else jsonpath_expr
    paths: list[Path] = []
    for match in expr.find(root):
        keys = keys_from_jsonpath(match.full_path)
        paths.append(Path(keys, root=root))
    return tuple(paths)
