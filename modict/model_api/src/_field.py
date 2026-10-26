from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, List, Literal, Union

from ...collections_utils import MISSING

from ._core import Computed, Factory, Validator

RequiredLevel = Literal["always", "at_init", "never"]

_REQUIRED_LEVELS = ("never", "at_init", "always")


def _normalize_required(value: Union[bool, RequiredLevel]) -> RequiredLevel:
    """Normalize a bool or string required value to a RequiredLevel string."""
    if value is True:
        return "always"
    if value is False:
        return "never"
    if value in _REQUIRED_LEVELS:
        return value  # type: ignore[return-value]
    raise ValueError(f"Invalid required value: {value!r}. Expected 'always', 'at_init', 'never', True, or False.")


@dataclass
class Field:
    hint: Any = None
    default: Any = MISSING
    validators: List[Validator] = None  # type: ignore[assignment]
    required: Union[bool, RequiredLevel] = MISSING

    def __post_init__(self) -> None:
        if self.validators is None:
            self.validators = []
        if self.required is not MISSING:
            self.required = _normalize_required(self.required)

    def copy(self) -> "Field":
        """Copy field metadata with an independent validator list, sharing defaults."""
        return replace(self, validators=list(self.validators))

    def add_validator(self, validator: Validator) -> None:
        self.validators.append(validator)

    def merge(self, other: "Field") -> "Field":
        # Explicit local metadata overrides inherited metadata.
        return Field(
            hint=self.hint or other.hint,
            default=self.default if self.default is not MISSING else other.default,
            validators=(other.validators + self.validators),
            required=self.required if self.required is not MISSING else other.required,
        )

    def get_default(self) -> Any:
        if isinstance(self.default, Factory):
            value = self.default()
        else:
            value = self.default
        if isinstance(value, Computed):
            value = value.copy()
        return value

