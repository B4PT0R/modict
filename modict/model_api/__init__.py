"""Shared model-layer API used by `modict` and `reactive_data`."""

from .src._computed import invalidate_dependants
from .src._config import Config
from .src._core import Computed, Factory, ModelValidator, Validator
from .src._field import Field
from .src._metaclass_fields import (
    build_fields_and_model_validators,
    get_annotations,
    is_field,
    is_locally_defined_class,
    is_locally_defined_descriptor,
)
from .src._validation import (
    apply_enum_value_extraction,
    apply_string_transformations,
    check_json_serializable,
    check_type_with_enum_values,
    maybe_coerce,
)

__all__ = [
    "Factory",
    "Config",
    "Field",
    "Validator",
    "ModelValidator",
    "Computed",
    "invalidate_dependants",
    "apply_string_transformations",
    "apply_enum_value_extraction",
    "check_type_with_enum_values",
    "maybe_coerce",
    "check_json_serializable",
    "get_annotations",
    "is_locally_defined_class",
    "is_locally_defined_descriptor",
    "is_field",
    "build_fields_and_model_validators",
]
