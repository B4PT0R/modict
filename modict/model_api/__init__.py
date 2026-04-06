"""Shared model-layer API used by `modict` and `reactive_data`."""

from .src._computed import invalidate_dependants
from .src._config import Config
from .src._core import AnyValidator, Attribute, Computed, Factory, ModelValidator, Validator
from .src._field import Field
from .src._metaclass_fields import (
    build_any_validators,
    build_fields_and_model_validators,
    get_annotations,
    is_field,
    is_locally_defined_class,
    is_locally_defined_descriptor,
)
from .src._validation import (
    check_json_serializable,
    maybe_coerce,
)

__all__ = [
    "Factory",
    "Attribute",
    "Config",
    "Field",
    "AnyValidator",
    "Validator",
    "ModelValidator",
    "Computed",
    "invalidate_dependants",
    "maybe_coerce",
    "check_json_serializable",
    "get_annotations",
    "is_locally_defined_class",
    "is_locally_defined_descriptor",
    "is_field",
    "build_any_validators",
    "build_fields_and_model_validators",
]
