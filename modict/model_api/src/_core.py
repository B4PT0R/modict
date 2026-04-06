from __future__ import annotations

from typing import Any, Callable, List, Literal, Optional

from ...collections_utils import MISSING

from ._computed import Computed

from ._validators import AnyValidator, Validator, ModelValidator


class Attribute:
    """Explicit wrapper for values that should stay plain attributes, not fields."""

    def __init__(self, value: Any):
        self.value = value

    def __repr__(self) -> str:
        return f"Attribute({self.value!r})"


class Factory:
    """Explicit default factory wrapper (distinguishes callables from factory defaults)."""

    def __init__(self, factory: Callable[[], Any]):
        self.factory = factory

    def __call__(self) -> Any:
        return self.factory()





