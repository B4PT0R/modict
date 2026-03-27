from collections.abc import ValuesView, ItemsView, KeysView
from typing import Any, Callable, Dict, Literal, Optional, Type
from types import FunctionType
from ...collections_utils import MISSING
from dataclasses import dataclass
import warnings
import sys

from ...model_api import Config as BaseConfig
from ...model_api import (
    Computed,
    Factory,
    Field,
    ModelValidator,
    Validator,
    build_fields_and_model_validators,
)


@dataclass(init=False)
class modictConfig(BaseConfig):
    """Configuration for modict instances.

    This is a modict-native configuration object.

    Many option names intentionally overlap with Pydantic's `ConfigDict` for
    familiarity, but `modictConfig` is **not** a drop-in replacement for
    Pydantic config: unsupported/unknown options raise `TypeError`.

    Attributes:
       check_values: Controls whether modict enforces its validation/processing pipeline:
           - True (default): enable when the class looks "model-like" (has hints/validators/config constraints)
           - False: bypass validation entirely (dict-like behavior)

       # modict-specific fields
       auto_convert: If True, automatically convert dicts found in nested mutable containers
                     (MutableMapping or MutableSequence) to modicts (on first access).
       override_computed: If True, allow overriding/deleting computed fields at runtime.
                         During model instantiation/casting, class-declared computed
                         fields still override incoming values to preserve the target
                         model contract.
       require_all: If True, require presence of all declared (non-computed) class fields
                    at initialization time (annotation-only fields become required).
       check_keys: Controls whether modict enforces key-level structural constraints:
           - True (default): enabled when the model declares key constraints (extra/require_all/required/computed)
           - False: bypass key-level constraints (dict-like keys)
       evaluate_computed: If False, do not evaluate Computed fields on access; treat them
                         as raw stored objects (pure storage mode).

       # Pydantic-aligned fields (actively used)
       extra: Controls handling of extra attributes ('allow', 'forbid', 'ignore').
              - 'allow': Allow extra attributes and store them
              - 'forbid': Raise error on extra attributes
              - 'ignore': Silently ignore extra attributes
       strict: Pydantic-like strict mode. If True, do not coerce values and require exact types.
       enforce_json: If True, enforce JSON-serializable values.
       frozen: If True, make instances immutable (faux-immutable).
       validate_assignment: If True, validate values on assignment (Pydantic semantics). Defaults to True.
       validate_default: If True, validate default values at class definition time.
       allow_inf_nan: If False, disallow NaN/Infinity when enforce_json=True.
       from_attributes: If True, allow building a modict from an object with attributes.
       json_encoders: Default encoders applied by dumps()/dump() when no encoders are passed explicitly.
    """

    # modict-specific
    auto_convert: bool = True
    override_computed: bool = False
    require_all: bool = False
    check_keys: bool = True
    check_values: bool = True
    evaluate_computed: bool = True

    # Pydantic-aligned (actively used)
    extra: Literal['allow', 'forbid', 'ignore'] = 'allow'
    strict: bool = False
    enforce_json: bool = False
    frozen: bool = False
    validate_assignment: bool = True

    # Pydantic-aligned (also implemented by modict)
    validate_default: bool = False
    allow_inf_nan: bool = True
    from_attributes: bool = False
    json_encoders: Optional[Dict[Type, Callable[[Any], Any]]] = None

    @classmethod
    def _normalize_kwargs(cls, kwargs: dict[str, Any]) -> dict[str, Any]:
        # Deprecated: coerce -> strict
        if 'coerce' in kwargs:
            warnings.warn(
                "The 'coerce' parameter is deprecated. Use Pydantic-like 'strict' instead:\n"
                "  coerce=True  → strict=False (lax mode, coercion allowed)\n"
                "  coerce=False → strict=True  (strict mode, no coercion)",
                DeprecationWarning,
                stacklevel=2,
            )
            coerce_value = kwargs.pop('coerce')
            if 'strict' not in kwargs:
                kwargs['strict'] = (not bool(coerce_value))

        # Handle backward compatibility: allow_extra → extra
        if 'allow_extra' in kwargs:
            warnings.warn(
                "The 'allow_extra' parameter is deprecated. Use 'extra' instead:\n"
                "  allow_extra=True  → extra='allow'\n"
                "  allow_extra=False → extra='forbid'",
                DeprecationWarning,
                stacklevel=2
            )
            allow_extra_value = kwargs.pop('allow_extra')
            # Only set 'extra' if not already provided
            if 'extra' not in kwargs:
                kwargs['extra'] = 'allow' if allow_extra_value else 'forbid'

        return kwargs

    @classmethod
    def _unknown_keys_error(cls, unknown: set[str]) -> TypeError:
        unknown_list = ", ".join(sorted(unknown))
        return TypeError(
            f"Unsupported modict config option(s): {unknown_list}. "
            "modictConfig is not Pydantic's ConfigDict; only modict's supported options are accepted."
        )


class modictKeysView(KeysView):
    def __init__(self, mapping):
        self._mapping = mapping
    
    def __len__(self):
        return len(self._mapping)
    
    def __contains__(self, key):
        return key in self._mapping
    
    def __iter__(self):
        return iter(self._mapping)

class modictValuesView(ValuesView):
    def __init__(self, mapping):
        self._mapping = mapping
    
    def __len__(self):
        return len(self._mapping)
    
    def __contains__(self, value):
        for key in self._mapping:
            if self._mapping[key] == value:  # Validation via __getitem__
                return True
        return False
    
    def __iter__(self):
        for key in self._mapping:
            yield self._mapping[key]  # Validation via __getitem__

class modictItemsView(ItemsView):
    def __init__(self, mapping):
        self._mapping = mapping
    
    def __len__(self):
        return len(self._mapping)
    
    def __contains__(self, item):
        key, value = item
        try:
            return self._mapping[key] == value  # Validation via __getitem__
        except KeyError:
            return False
    
    def __iter__(self):
        for key in self._mapping:
            yield (key, self._mapping[key])  # Validation via __getitem__

class modictMeta(type):

    def __new__(mcls, name, bases, dct):
        fields, model_validators, attributes = build_fields_and_model_validators(name, bases, dct)

        # Store fields in __fields__
        dct['__fields__'] = fields
        dct["__model_validators__"] = tuple(model_validators)
        dct["__attributes__"] = attributes
        dct["__has_field_hints__"] = any(field.hint is not None for field in fields.values())
        dct["__has_field_validators__"] = any(
            bool(getattr(field, "validators", ())) for field in fields.values()
        )
        dct["__has_required_fields__"] = any(
            bool(getattr(field, "required", False)) for field in fields.values()
        )
        dct["__has_declared_computed_fields__"] = any(
            isinstance(getattr(field, "default", None), Computed) for field in fields.values()
        )
        dct["__has_model_validators__"] = bool(model_validators)

        # Setup _config using modictConfig with proper MRO merging

        # Build a parent config from ALL bases
        parent_config = None

        # Iterate bases from last to first
        # so the leftmost base (in class X(A, B)) wins
        for base in reversed(bases):
            base_conf = getattr(base, '_config', None)
            if base_conf is None:
                continue

            if parent_config is None:
                parent_config = base_conf
            else:
                # merge like dict.update: explicit fields from base_conf
                # override those already in parent_config
                parent_config = parent_config.merge(base_conf)

        if '_config' in dct:
            # _config explicitly defined in this class
            local_config = dct['_config']
            if not isinstance(local_config, modictConfig):
                raise TypeError(
                    f"_config must be a modictConfig instance created via modict.config(), "
                    f"got {type(local_config)}. Use: _config = modict.config(enforce_json=True, ...)"
                )

            if parent_config is not None:
                # Stack the local config on top of the combined base config
                effective_config = parent_config.merge(local_config)
            else:
                # No parent with a config — use local config only
                effective_config = local_config
        else:
            # No local _config — pure inheritance or defaults
            if parent_config is not None:
                effective_config = parent_config
            else:
                effective_config = modictConfig()

        dct['_config'] = effective_config

        # Validate default values if validate_default is enabled
        if effective_config.validate_default:
            from ...typechecker import check_type, TypeMismatchError

            for field_name, field_obj in fields.items():
                # Skip fields without defaults
                if field_obj.default is MISSING:
                    continue

                # Skip Computed and Factory fields (they're dynamic)
                if isinstance(field_obj.default, (Computed, Factory)):
                    continue

                # Skip fields without type hints
                if field_obj.hint is None:
                    continue

                # Validate the default value against its type hint
                try:
                    check_type(field_obj.hint, field_obj.default)
                except TypeMismatchError as e:
                    raise TypeError(
                        f"Invalid default value for field '{field_name}' in class '{name}': "
                        f"expected {field_obj.hint}, got {type(field_obj.default).__name__} "
                        f"({field_obj.default!r}). "
                        f"Set validate_default=False to disable this check."
                    ) from e

        return super().__new__(mcls, name, bases, dct)
