from __future__ import annotations
from typing import Any, Callable, List, Literal

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

    def __call__(self, instance, value, *, values=None, cls=None, info=None):
        try:
            return self.func(instance, value)
        except Exception as e:
            if isinstance(e, TypeError):
                raise TypeError(
                    f"Invalid validator signature for field '{self.field_name}'. "
                    "Expected: (self, value)"
                ) from e
            raise ValueError(f"Error in validator for field '{self.field_name}': {e}") from e


class ModelValidator:
    """Model-level validator (multi-field invariants).

    Expected signature: `(self, values) -> None|Mapping|self`.
    """

    def __init__(self, func: Callable, *, mode: Literal["before", "after"] = "after"):
        self.func = func
        self.mode = mode

    def __call__(self, instance, *, values=None, cls=None, info=None):
        try:
            if values is None and instance is not None:
                values = dict(instance)
            return self.func(instance, values)
        except Exception as e:
            if isinstance(e, TypeError):
                raise TypeError("Invalid model validator signature. Expected: (self, values)") from e
            raise ValueError(f"Error in model validator: {e}") from e