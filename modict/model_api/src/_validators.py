from __future__ import annotations
import inspect
from typing import Any, Callable, Literal


def _validate_signature(func: Callable, expected_error: str, *sample_args: Any) -> None:
    try:
        inspect.signature(func).bind(*sample_args)
    except TypeError as exc:
        raise TypeError(expected_error) from exc

class Validator:
    """Field-level validator/transformer.

    Expected signature: `(self, value) -> value`.
    """

    def __init__(
        self,
        func: Callable[[Any, Any], Any],
        field_name: str,
        *,
        mode: Literal["before", "after"] = "before",
    ):
        self.func = func
        self.field_name = field_name
        self.mode = mode
        _validate_signature(
            func,
            f"Invalid validator signature for field '{field_name}'. Expected: (self, value)",
            object(),
            object(),
        )

    def __call__(self, instance, value, *, values=None, cls=None, info=None):
        return self.func(instance, value)


class AnyValidator:
    """Key-aware validator/transformer applied to every modified item.

    Expected signature: `(self, key, value) -> value`.
    """

    def __init__(
        self,
        func: Callable[[Any, Any, Any], Any],
        *,
        mode: Literal["before", "after"] = "before",
    ):
        self.func = func
        self.mode = mode
        _validate_signature(
            func,
            "Invalid any-validator signature. Expected: (self, key, value)",
            object(),
            object(),
            object(),
        )

    def __call__(self, instance, key, value, *, values=None, cls=None, info=None):
        return self.func(instance, key, value)


class ModelValidator:
    """Model-level validator (multi-field invariants).

    Expected signature: `(self) -> None`.
    """

    def __init__(self, func: Callable, *, mode: Literal["before", "after"] = "after"):
        self.func = func
        self.mode = mode
        _validate_signature(
            func,
            "Invalid model validator signature. Expected: (self)",
            object(),
        )

    def __call__(self, instance, *, values=None, cls=None, info=None):
        return self.func(instance)
