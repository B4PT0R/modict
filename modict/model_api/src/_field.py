from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from ...collections_utils import MISSING

from ._core import Computed, Factory, Validator


@dataclass
class Field:
    hint: Any = None
    default: Any = MISSING
    validators: List[Validator] = None  # type: ignore[assignment]
    required: bool = False
    metadata: Dict[str, Any] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.validators is None:
            self.validators = []
        if self.metadata is None:
            self.metadata = {}

    def add_validator(self, validator: Validator) -> None:
        self.validators.append(validator)

    def merge(self, other: "Field") -> "Field":
        return Field(
            hint=self.hint or other.hint,
            default=self.default if self.default is not MISSING else other.default,
            validators=(other.validators + self.validators),
            required=self.required or other.required,
            metadata={**other.metadata, **self.metadata},
        )

    def get_default(self) -> Any:
        if isinstance(self.default, Factory):
            value = self.default()
        else:
            value = self.default
        if isinstance(value, Computed):
            value = value.copy()
        return value

