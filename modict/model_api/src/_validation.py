from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from ...typechecker import CoercionError, coerce


def maybe_coerce(value: Any, hint: Any) -> Any:
    if hint is None:
        return value

    try:
        # coerce internally checks first if the type already matches
        # before attempting coercion if the type does not match
        return coerce(value, hint)
    except CoercionError:
        return value


def check_json_serializable(
    value: Any,
    *,
    key: str,
    allow_nan: bool,
    encoders: Optional[Dict[type, Callable[[Any], Any]]] = None,
) -> None:
    import json

    encoders = encoders or {}

    def _default(o: Any) -> Any:
        for t, fn in encoders.items():
            if isinstance(o, t):
                return fn(o)
        raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")

    try:
        json.dumps(value, allow_nan=allow_nan, default=_default if encoders else None)
    except (TypeError, ValueError, OverflowError) as e:
        raise ValueError(
            f"Field '{key}' contains non-JSON-serializable value: {type(value).__name__}"
        ) from e
