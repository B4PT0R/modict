from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Literal, Union

from ...collections_utils import MISSING

from ._core import Computed, Factory, Validator

RequiredLevel = Literal["always", "at_init", "never"]

_REQUIRED_ORDER = {"never": 0, "at_init": 1, "always": 2}


def _normalize_required(value: Union[bool, RequiredLevel]) -> RequiredLevel:
    """Normalize a bool or string required value to a RequiredLevel string."""
    if value is True:
        return "always"
    if value is False:
        return "never"
    if value in _REQUIRED_ORDER:
        return value  # type: ignore[return-value]
    raise ValueError(f"Invalid required value: {value!r}. Expected 'always', 'at_init', 'never', True, or False.")


@dataclass
class Field:
    hint: Any = None
    default: Any = MISSING
    validators: List[Validator] = None  # type: ignore[assignment]
    required: Union[bool, RequiredLevel] = "never"

    def __post_init__(self) -> None:
        if self.validators is None:
            self.validators = []
        self.required = _normalize_required(self.required)

    def add_validator(self, validator: Validator) -> None:
        self.validators.append(validator)

    def merge(self, other: "Field") -> "Field":
        # Stronger constraint wins when merging
        self_level = _REQUIRED_ORDER.get(str(self.required), 0)
        other_level = _REQUIRED_ORDER.get(str(other.required), 0)
        merged_required = self.required if self_level >= other_level else other.required
        return Field(
            hint=self.hint or other.hint,
            default=self.default if self.default is not MISSING else other.default,
            validators=(other.validators + self.validators),
            required=merged_required,
        )

    def get_default(self) -> Any:
        if isinstance(self.default, Factory):
            value = self.default()
        else:
            value = self.default
        if isinstance(value, Computed):
            value = value.copy()
        return value

