from __future__ import annotations

from typing import Any, Callable, List, Literal, Optional

from ...collections_utils import MISSING

from ._computed import Computed

from ._validators import Validator, ModelValidator


class Factory:
    """Explicit default factory wrapper (distinguishes callables from factory defaults)."""

    def __init__(self, factory: Callable[[], Any]):
        self.factory = factory

    def __call__(self) -> Any:
        return self.factory()







