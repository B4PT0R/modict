"""JSON helpers for nested containers.

These helpers complement the deep operations in `collections_utils` by providing a
small, explicit surface for converting nested containers to JSON-serializable
structures.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from enum import Enum
import json
from typing import Any, Callable, Dict, Optional, Type


def to_jsonable(
    obj: Any,
    *,
    exclude_none: bool = False,
    encoders: Optional[Dict[Type, Callable[[Any], Any]]] = None,
    use_enum_values: bool = False,
) -> Any:
    """Convert `obj` to a JSON-serializable structure.

    - `Mapping` becomes a plain `dict` (optionally dropping keys with `None`).
    - `tuple`/`set` become a `list`.
    - `Enum` becomes its `.value` when `use_enum_values=True`.
    - `encoders` may map a type to an encoder callable applied to leaf values.

    This function is intentionally strict: if a value isn't JSON-serializable and
    no encoder applies, `json.dumps()` will raise.
    """

    if use_enum_values and isinstance(obj, Enum):
        obj = obj.value

    if encoders:
        for t, fn in encoders.items():
            if isinstance(obj, t):
                return fn(obj)

    if isinstance(obj, Mapping):
        out: dict[Any, Any] = {}
        for k, v in obj.items():
            if exclude_none and v is None:
                continue
            out[k] = to_jsonable(
                v,
                exclude_none=exclude_none,
                encoders=encoders,
                use_enum_values=use_enum_values,
            )
        return out

    if isinstance(obj, (list, tuple, set)):
        return [
            to_jsonable(
                v,
                exclude_none=exclude_none,
                encoders=encoders,
                use_enum_values=use_enum_values,
            )
            for v in obj
        ]

    if isinstance(obj, Sequence) and not isinstance(obj, (str, bytes, bytearray)):
        return [
            to_jsonable(
                v,
                exclude_none=exclude_none,
                encoders=encoders,
                use_enum_values=use_enum_values,
            )
            for v in obj
        ]

    return obj


def json_dumps(
    obj: Any,
    *,
    exclude_none: bool = False,
    encoders: Optional[Dict[Type, Callable[[Any], Any]]] = None,
    use_enum_values: bool = False,
    allow_nan: bool = True,
    **json_kwargs,
) -> str:
    """Serialize `obj` to JSON after `to_jsonable()` conversion."""

    payload = to_jsonable(
        obj,
        exclude_none=exclude_none,
        encoders=encoders,
        use_enum_values=use_enum_values,
    )
    return json.dumps(payload, allow_nan=allow_nan, **json_kwargs)
