from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from ...typechecker import CoercionError, TypeCheckException, check_type, coerce


def apply_string_transformations(
    value: Any,
    *,
    strip_whitespace: bool,
    to_lower: bool,
    to_upper: bool,
) -> Any:
    if not isinstance(value, str):
        return value

    if strip_whitespace:
        value = value.strip()

    if to_lower:
        return value.lower()
    if to_upper:
        return value.upper()
    return value


def apply_enum_value_extraction(value: Any, *, use_enum_values: bool) -> Any:
    if not use_enum_values:
        return value
    from enum import Enum

    if isinstance(value, Enum):
        return value.value
    return value


def check_type_with_enum_values(hint: Any, value: Any, *, use_enum_values: bool) -> bool:
    if use_enum_values and isinstance(hint, type):
        from enum import Enum

        if issubclass(hint, Enum) and not isinstance(value, Enum):
            allowed = {type(m.value) for m in hint}  # type: ignore[arg-type]
            if any(isinstance(value, t) for t in allowed):
                return True
    return check_type(hint, value)


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

