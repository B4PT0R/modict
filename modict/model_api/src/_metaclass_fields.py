from __future__ import annotations

from types import FunctionType
from typing import Any, Dict, Tuple

from ...collections_utils import MISSING

from ._core import Attribute, Computed, ModelValidator, Validator
from ._field import Field


def get_annotations(dct: dict, name: str, bases: tuple) -> dict:
    """Get annotations from class dict, compatible with Python 3.10+ and 3.14+.

    Python 3.14+ (PEP 649) defers annotation evaluation, so __annotations__
    is not available in dct during metaclass __new__. We handle both cases.
    """
    if "__annotations__" in dct:
        return dct["__annotations__"]

    if "__annotate_func__" in dct:
        annotate_func = dct["__annotate_func__"]
        try:
            return annotate_func(1)
        except Exception:
            try:
                return annotate_func()
            except Exception:
                return {}

    return {}


def is_locally_defined_class(key: str, value: Any, name: str, dct: Dict[str, Any]) -> bool:
    if not isinstance(value, type):
        return False
    expected_qualname = f"{name}.{key}"
    module = dct.get("__module__")
    return bool(
        module is not None and value.__module__ == module and value.__qualname__ == expected_qualname
    )


def is_locally_defined_descriptor(key: str, value: Any, name: str, dct: Dict[str, Any]) -> bool:
    if isinstance(value, FunctionType):
        underlying_func = value
    elif isinstance(value, (classmethod, staticmethod)):
        underlying_func = value.__func__
    elif isinstance(value, property):
        underlying_func = value.fget
    else:
        return False

    expected_qualname = f"{name}.{key}"
    module = dct.get("__module__")
    return bool(
        module is not None
        and underlying_func is not None
        and underlying_func.__module__ == module
        and underlying_func.__qualname__ == expected_qualname
    )


def is_field(key: str, value: Any, name: str, bases: Tuple[type, ...], dct: Dict[str, Any]) -> bool:
    if isinstance(value, Field):
        return True

    if hasattr(value, "_is_computed"):
        return True

    if hasattr(value, "_is_validator"):
        return False

    if hasattr(value, "_is_model_validator"):
        return False

    if key.startswith("__"):
        return False

    for base in bases:
        if hasattr(base, key):
            return False

    if isinstance(value, type):
        return not is_locally_defined_class(key, value, name, dct)

    if hasattr(value, "__get__") or isinstance(value, (classmethod, staticmethod, property)):
        return not is_locally_defined_descriptor(key, value, name, dct)

    return True


def build_fields_and_model_validators(
    name: str,
    bases: Tuple[type, ...],
    dct: Dict[str, Any],
) -> tuple[dict[str, Field], list[ModelValidator], dict[str, Any]]:
    fields: dict[str, Field] = {}
    annotations = get_annotations(dct, name, bases)
    model_validators: list[ModelValidator] = []
    attributes: dict[str, Any] = {}

    for base in reversed(bases):
        if hasattr(base, "__fields__"):
            fields.update(base.__fields__)  # type: ignore[attr-defined]
        if hasattr(base, "__model_validators__"):
            model_validators.extend(list(base.__model_validators__))  # type: ignore[attr-defined]
        if hasattr(base, "__attributes__"):
            attributes.update(base.__attributes__)  # type: ignore[attr-defined]

    existing_model_validators = dct.get("__model_validators__")
    if existing_model_validators:
        model_validators.extend(list(existing_model_validators))

    for key, hint in annotations.items():
        if key in dct:
            value = dct[key]
            if isinstance(value, Attribute):
                fields.pop(key, None)
                attributes[key] = value.value
                dct[key] = value.value
                continue
            if isinstance(value, FunctionType) and hasattr(value, "_is_computed"):
                cache = getattr(value, "_computed_cache", False)
                deps = getattr(value, "_computed_deps", None)
                computed_obj = Computed(value, cache=cache, deps=deps)
                func_return_hint = getattr(value, "__annotations__", {}).get("return")
                final_hint = hint if hint is not None else func_return_hint
                attributes.pop(key, None)
                fields[key] = Field(default=computed_obj, hint=final_hint, required=False)
            elif not isinstance(value, Field):
                attributes.pop(key, None)
                fields[key] = Field(default=value, hint=hint, required=False)
            else:
                if value.hint is None:
                    value.hint = hint
                attributes.pop(key, None)
                fields[key] = value
            dct.pop(key)
        else:
            attributes.pop(key, None)
            fields[key] = Field(default=MISSING, hint=hint, required=False)

    for key, value in list(dct.items()):
        if key in annotations:
            continue
        if isinstance(value, Attribute):
            fields.pop(key, None)
            attributes[key] = value.value
            dct[key] = value.value
            continue
        if not is_field(key, value, name, bases, dct):
            continue

        if isinstance(value, FunctionType) and hasattr(value, "_is_computed"):
            cache = getattr(value, "_computed_cache", False)
            deps = getattr(value, "_computed_deps", None)
            computed_obj = Computed(value, cache=cache, deps=deps)
            func_return_hint = getattr(value, "__annotations__", {}).get("return")
            attributes.pop(key, None)
            fields[key] = Field(default=computed_obj, hint=func_return_hint, required=False)
        elif not isinstance(value, Field):
            attributes.pop(key, None)
            fields[key] = Field(default=value)
        else:
            attributes.pop(key, None)
            fields[key] = value
        dct.pop(key)

    for key, value in list(dct.items()):
        if isinstance(value, FunctionType) and hasattr(value, "_is_validator"):
            field_name = value._validator_field
            validator_mode = getattr(value, "_validator_mode", "before")
            check_obj = Validator(value, field_name, mode=validator_mode)

            if field_name in fields:
                fields[field_name].add_validator(check_obj)
            else:
                fields[field_name] = Field(validators=[check_obj])

            dct.pop(key)

    for key, value in list(dct.items()):
        if isinstance(value, FunctionType) and hasattr(value, "_is_model_validator"):
            mode = getattr(value, "_model_validator_mode", "after")
            if mode not in ("before", "after"):
                mode = "after"
            model_validators.append(ModelValidator(value, mode=mode))
            dct.pop(key)

    return fields, model_validators, attributes
