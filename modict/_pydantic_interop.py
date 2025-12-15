"""Pydantic interoperability module.

Provides class-level conversion between modict and Pydantic model classes.
Uses conditional imports to avoid hard dependency on Pydantic.
"""

from typing import (
    TYPE_CHECKING,
    Type,
    Any,
    Optional,
    Dict,
    Tuple,
    get_type_hints,
    get_origin,
    get_args,
    Union,
    Annotated,
)
import types
import sys
import warnings
from weakref import WeakValueDictionary

if TYPE_CHECKING:
    try:
        from pydantic import BaseModel
    except ImportError:
        BaseModel = Any


class TypeCache:
    """Global cache for type conversions between Pydantic and modict.

    Uses weak references to avoid keeping classes alive unnecessarily.
    Provides bidirectional mapping stored as class attributes:
    - _pydantic_to_modict: Pydantic BaseModel → modict class
    - _modict_to_pydantic: modict class → Pydantic BaseModel
    """

    # Use WeakValueDictionary as class attributes for true global caching
    _pydantic_to_modict: Dict[Type, Type] = WeakValueDictionary()
    _modict_to_pydantic: Dict[Type, Type] = WeakValueDictionary()

    @classmethod
    def get_modict(cls, pydantic_class: Type) -> Optional[Type]:
        """Get cached modict class for a Pydantic class.

        Args:
            pydantic_class: Pydantic BaseModel class

        Returns:
            Cached modict class if exists, None otherwise
        """
        return cls._pydantic_to_modict.get(pydantic_class)

    @classmethod
    def get_pydantic(cls, modict_class: Type) -> Optional[Type]:
        """Get cached Pydantic class for a modict class.

        Args:
            modict_class: modict class

        Returns:
            Cached Pydantic BaseModel class if exists, None otherwise
        """
        return cls._modict_to_pydantic.get(modict_class)

    @classmethod
    def set_modict(cls, pydantic_class: Type, modict_class: Type) -> None:
        """Cache a Pydantic → modict conversion.

        Args:
            pydantic_class: Source Pydantic BaseModel class
            modict_class: Target modict class
        """
        cls._pydantic_to_modict[pydantic_class] = modict_class

    @classmethod
    def set_pydantic(cls, modict_class: Type, pydantic_class: Type) -> None:
        """Cache a modict → Pydantic conversion.

        Args:
            modict_class: Source modict class
            pydantic_class: Target Pydantic BaseModel class
        """
        cls._modict_to_pydantic[modict_class] = pydantic_class

    @classmethod
    def clear(cls) -> None:
        """Clear all cached conversions."""
        cls._pydantic_to_modict.clear()
        cls._modict_to_pydantic.clear()


class _ModictFieldMeta:
    """Internal metadata carrier for modict -> Pydantic -> modict round-trips.

    Stored in Pydantic FieldInfo.metadata (via typing.Annotated) so it doesn't
    interfere with validation or JSON schema output.
    """

    _modict_field_meta = True

    def __init__(self, *, required: bool, default_marker: Optional[str] = None):
        self.required = bool(required)
        self.default_marker = default_marker


def _check_pydantic_available() -> None:
    """Check if Pydantic is available and raise helpful error if not.

    Raises:
        ImportError: If Pydantic is not installed
    """
    if 'pydantic' not in sys.modules:
        try:
            import pydantic
        except ImportError:
            raise ImportError(
                "Pydantic is required for this feature. "
                "Install it with: pip install pydantic"
            )


def _pydantic_config_to_modict(pydantic_config: Any) -> Dict[str, Any]:
    """Convert Pydantic ConfigDict/Config to modict config dict.

    Maps Pydantic configuration to modict-compatible configuration.

    Args:
        pydantic_config: Pydantic ConfigDict or Config class

    Returns:
        Dictionary of modict configuration options
    """
    modict_config = {}

    # Handle both v2 ConfigDict and v1 Config class
    if isinstance(pydantic_config, dict):
        # Pydantic v2 ConfigDict
        config_dict = pydantic_config
    elif hasattr(pydantic_config, '__dict__'):
        # Pydantic v1 Config class
        config_dict = {
            k: v for k, v in vars(pydantic_config).items()
            if not k.startswith('_')
        }
    else:
        return modict_config

    # Pydantic defaults to ignoring extra fields; modict defaults to allowing them.
    # For round-trip parity (Model -> modict), always record the effective Pydantic default
    # when not explicitly configured.
    modict_config['extra'] = config_dict.get('extra', 'ignore')

    # Map 'frozen' directly
    if 'frozen' in config_dict:
        modict_config['frozen'] = config_dict['frozen']

    # Map 'strict' directly (both use same name)
    if 'strict' in config_dict:
        modict_config['strict'] = config_dict['strict']

    # Map string transformations
    if 'str_strip_whitespace' in config_dict:
        modict_config['str_strip_whitespace'] = config_dict['str_strip_whitespace']

    if 'str_to_lower' in config_dict:
        modict_config['str_to_lower'] = config_dict['str_to_lower']

    if 'str_to_upper' in config_dict:
        modict_config['str_to_upper'] = config_dict['str_to_upper']

    # Map validate_assignment directly
    if 'validate_assignment' in config_dict:
        modict_config['validate_assignment'] = config_dict['validate_assignment']

    # Map populate_by_name
    if 'populate_by_name' in config_dict:
        modict_config['populate_by_name'] = config_dict['populate_by_name']

    # Map alias_generator (callable)
    if 'alias_generator' in config_dict:
        modict_config['alias_generator'] = config_dict['alias_generator']

    # Map validate_default (v2)
    if 'validate_default' in config_dict:
        modict_config['validate_default'] = config_dict['validate_default']

    # Map use_enum_values
    if 'use_enum_values' in config_dict:
        modict_config['use_enum_values'] = config_dict['use_enum_values']

    # Map allow_inf_nan (v2), defaulting to True when not specified.
    if 'allow_inf_nan' in config_dict:
        modict_config['allow_inf_nan'] = config_dict['allow_inf_nan']

    # Map from_attributes (v2), defaulting to False when not specified.
    if 'from_attributes' in config_dict:
        modict_config['from_attributes'] = config_dict['from_attributes']

    return modict_config


def _extract_modict_field_metadata(field_info: Any) -> tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    """Extract a conservative subset of Field(...) metadata from Pydantic FieldInfo.

    Works for Pydantic v2 FieldInfo; for v1 this may work partially as well.
    """
    metadata: Dict[str, Any] = {}
    constraints: Dict[str, Any] = {}
    aliases: Dict[str, Any] = {}

    for key in ("title", "description"):
        val = getattr(field_info, key, None)
        if val is not None:
            metadata[key] = val

    # Preserve additional Pydantic-only metadata (non-destructive round-trip).
    pydantic_raw: Dict[str, Any] = {}
    for key in (
        "json_schema_extra",
        "repr",
        "examples",
        "deprecated",
    ):
        if hasattr(field_info, key):
            val = getattr(field_info, key, None)
            if val is not None:
                pydantic_raw[key] = val

    # Aliases (supported by modict)
    alias = getattr(field_info, "alias", None)
    if isinstance(alias, str) and alias:
        aliases["alias"] = alias

    validation_alias = getattr(field_info, "validation_alias", None)
    if validation_alias is not None:
        if isinstance(validation_alias, str):
            aliases["validation_alias"] = validation_alias
        elif isinstance(validation_alias, (list, tuple, set)) and all(isinstance(x, str) for x in validation_alias):
            aliases["validation_alias"] = list(validation_alias)
        else:
            # Keep complex alias objects for round-trips (Pydantic-only)
            pydantic_raw["validation_alias"] = validation_alias

    serialization_alias = getattr(field_info, "serialization_alias", None)
    if serialization_alias is not None:
        if isinstance(serialization_alias, str):
            aliases["serialization_alias"] = serialization_alias
        else:
            pydantic_raw["serialization_alias"] = serialization_alias

    # Pydantic v2 stores many constraints in FieldInfo.metadata as constraint objects.
    constraint_keys = {
        "gt",
        "ge",
        "lt",
        "le",
        "min_length",
        "max_length",
        "pattern",
        "regex",
        "multiple_of",
    }
    raw_constraints: list[Dict[str, Any]] = []
    for item in getattr(field_info, "metadata", []) or []:
        for key in constraint_keys:
            if hasattr(item, key):
                constraints[key] = getattr(item, key)
        # Preserve unknown/extra constraints as a best-effort dict.
        try:
            raw_constraints.append(
                {
                    "type": type(item).__name__,
                    "attrs": dict(vars(item)),
                    "repr": repr(item),
                }
            )
        except Exception:
            raw_constraints.append(
                {
                    "type": type(item).__name__,
                    "repr": repr(item),
                }
            )

    if raw_constraints:
        pydantic_raw.setdefault("constraints", raw_constraints)

    return metadata, constraints, aliases, pydantic_raw


def _modict_config_to_pydantic(modict_config) -> Dict[str, Any]:
    """Convert modict config to Pydantic ConfigDict.

    Maps modict configuration to Pydantic-compatible configuration.

    Args:
        modict_config: modictConfig instance

    Returns:
        Dictionary of Pydantic configuration options
    """
    pydantic_config: Dict[str, Any] = {}

    # Only emit values that differ from Pydantic defaults; this preserves behavior
    # while keeping generated JSON schema stable/canonical (e.g. avoid emitting
    # additionalProperties=True when extra='ignore' which is already the default).
    pydantic_defaults: Dict[str, Any] = {
        "extra": "ignore",
        "frozen": False,
        "strict": False,
        "validate_assignment": False,
        "validate_default": False,
        "str_strip_whitespace": False,
        "str_to_lower": False,
        "str_to_upper": False,
        "use_enum_values": False,
        "populate_by_name": False,
        "alias_generator": None,
    }

    # Map 'extra' (Pydantic default is "ignore")
    if hasattr(modict_config, "extra"):
        extra = modict_config.extra
        if extra != pydantic_defaults["extra"]:
            pydantic_config["extra"] = extra

    # Map 'frozen' directly
    if hasattr(modict_config, "frozen"):
        frozen = modict_config.frozen
        if frozen != pydantic_defaults["frozen"]:
            pydantic_config["frozen"] = frozen

    # Map 'strict' directly
    if hasattr(modict_config, "strict"):
        strict = modict_config.strict
        if strict != pydantic_defaults["strict"]:
            pydantic_config["strict"] = strict

    # Map string transformations
    if hasattr(modict_config, "str_strip_whitespace"):
        val = modict_config.str_strip_whitespace
        if val != pydantic_defaults["str_strip_whitespace"]:
            pydantic_config["str_strip_whitespace"] = val

    if hasattr(modict_config, "str_to_lower"):
        val = modict_config.str_to_lower
        if val != pydantic_defaults["str_to_lower"]:
            pydantic_config["str_to_lower"] = val

    if hasattr(modict_config, "str_to_upper"):
        val = modict_config.str_to_upper
        if val != pydantic_defaults["str_to_upper"]:
            pydantic_config["str_to_upper"] = val

    # Map validate_assignment directly
    if hasattr(modict_config, "validate_assignment"):
        val = modict_config.validate_assignment
        if val != pydantic_defaults["validate_assignment"]:
            pydantic_config["validate_assignment"] = val

    # Map validate_default
    if hasattr(modict_config, "validate_default"):
        val = modict_config.validate_default
        if val != pydantic_defaults["validate_default"]:
            pydantic_config["validate_default"] = val

    # Map populate_by_name
    if hasattr(modict_config, "populate_by_name"):
        val = modict_config.populate_by_name
        if val is not False:
            pydantic_config["populate_by_name"] = val

    # Map alias_generator
    if hasattr(modict_config, "alias_generator"):
        val = modict_config.alias_generator
        if val is not None:
            pydantic_config["alias_generator"] = val

    # Map use_enum_values
    if hasattr(modict_config, "use_enum_values"):
        val = modict_config.use_enum_values
        if val is not False:
            pydantic_config["use_enum_values"] = val

    # Map allow_inf_nan (Pydantic v2)
    if hasattr(modict_config, "allow_inf_nan"):
        val = modict_config.allow_inf_nan
        if val is not True:
            pydantic_config["allow_inf_nan"] = val

    # Map from_attributes (Pydantic v2)
    if hasattr(modict_config, "from_attributes"):
        val = modict_config.from_attributes
        if val is not False:
            pydantic_config["from_attributes"] = val

    # Note: modict's 'check_values' is modict-specific (no direct Pydantic equivalent)
    # Note: modict's 'enforce_json' doesn't have a direct Pydantic equivalent
    # Note: modict's 'auto_convert' is modict-specific

    return pydantic_config


def _get_pydantic_fields(pydantic_class: Type["BaseModel"]):
    """Return model_fields (v2) or __fields__ (v1) from a Pydantic class."""
    try:
        return pydantic_class.model_fields  # type: ignore[attr-defined]
    except AttributeError:
        return pydantic_class.__fields__  # type: ignore[attr-defined]


def _resolve_pydantic_validators(pydantic_class: Type["BaseModel"]) -> Dict[str, list[tuple[Any, str]]]:
    """Collect Pydantic field validators across v1/v2 APIs.

    Returns:
        Dict[field_name, List[(callable, mode)]], where mode is "before" or "after".
    """
    validators: Dict[str, list[tuple[Any, str]]] = {}

    # Pydantic v2 decorators
    try:
        if hasattr(pydantic_class, "__pydantic_decorators__"):
            decorators = pydantic_class.__pydantic_decorators__  # type: ignore[attr-defined]
            if hasattr(decorators, "field_validators"):
                for decorator_obj in decorators.field_validators.values():
                    if hasattr(decorator_obj, "info") and hasattr(decorator_obj.info, "fields"):
                        fields = decorator_obj.info.fields
                        validator_func = decorator_obj.func
                        mode = getattr(decorator_obj.info, "mode", "before")
                        if mode not in ("before", "after"):
                            mode = "before"
                        for field_name in fields:
                            validators.setdefault(field_name, []).append((validator_func, mode))
    except Exception:
        pass

    # Pydantic v1 validators
    try:
        if hasattr(pydantic_class, "__validators__"):
            for validator_obj in pydantic_class.__validators__.values():  # type: ignore[attr-defined]
                if hasattr(validator_obj, "field_name"):
                    field_name = validator_obj.field_name
                    mode = "before" if bool(getattr(validator_obj, "pre", False)) else "after"
                    func = getattr(validator_obj, "func", validator_obj)
                    validators.setdefault(field_name, []).append((func, mode))
    except Exception:
        pass

    return validators


def _resolve_pydantic_model_validators(pydantic_class: Type["BaseModel"]) -> list[tuple[Any, str]]:
    """Collect Pydantic model validators across v1/v2 APIs.

    Returns:
        List[(callable, mode)] where mode is "before" or "after".
    """
    validators: list[tuple[Any, str]] = []

    # Pydantic v2 decorators
    try:
        if hasattr(pydantic_class, "__pydantic_decorators__"):
            decorators = pydantic_class.__pydantic_decorators__  # type: ignore[attr-defined]
            if hasattr(decorators, "model_validators"):
                for decorator_obj in decorators.model_validators.values():
                    func = decorator_obj.func
                    mode = getattr(decorator_obj.info, "mode", "after")
                    if mode not in ("before", "after"):
                        continue  # ignore wrap/other modes for now
                    validators.append((func, mode))
    except Exception:
        pass

    # Pydantic v1 root validators
    try:
        for func in getattr(pydantic_class, "__pre_root_validators__", []) or []:  # type: ignore[attr-defined]
            validators.append((func, "before"))
        for func in getattr(pydantic_class, "__post_root_validators__", []) or []:  # type: ignore[attr-defined]
            validators.append((func, "after"))
    except Exception:
        pass

    return validators


def _convert_type_hint_from_pydantic(
    type_hint,
    *,
    pydantic_class,
    cls,
    strict,
    coerce,
    config_kwargs,
):
    """Recursively convert BaseModel annotations to modict subclasses."""
    from pydantic import BaseModel

    if type_hint is pydantic_class:
        return type_hint

    if isinstance(type_hint, type) and issubclass(type_hint, BaseModel):
        # Check global cache first
        cached = TypeCache.get_modict(type_hint)
        if cached is not None:
            return cached
        return from_pydantic_model(
            cls,
            type_hint,
            strict=strict,
            coerce=coerce,
            **config_kwargs,
        )

    origin = get_origin(type_hint)
    args = get_args(type_hint)

    if origin is None or not args:
        return type_hint

    if origin in (Union, types.UnionType):
        converted_args = tuple(
            _convert_type_hint_from_pydantic(
                arg,
                pydantic_class=pydantic_class,
                cls=cls,
                strict=strict,
                coerce=coerce,
                config_kwargs=config_kwargs,
            )
            for arg in args
        )
        return Union[converted_args]  # type: ignore[index]

    converted_args = tuple(
        _convert_type_hint_from_pydantic(
            arg,
            pydantic_class=pydantic_class,
            cls=cls,
            strict=strict,
            coerce=coerce,
            config_kwargs=config_kwargs,
        )
        for arg in args
    )

    try:
        if origin is tuple and len(converted_args) == 2 and converted_args[1] is Ellipsis:
            return tuple[converted_args[0], ...]  # type: ignore[index]
        if len(converted_args) == 1:
            return origin[converted_args[0]]  # type: ignore[index]
        return origin[converted_args]  # type: ignore[index]
    except TypeError:
        return type_hint


def _build_class_dict_from_pydantic(model_fields, type_hints, convert_type_hint):
    """Build class dict with annotations, defaults, and validators."""
    from ._collections_utils import MISSING
    from ._modict_meta import Factory, Field as ModictField
    class_dict: Dict[str, Any] = {}

    for field_name, field_info in model_fields.items():
        field_type = convert_type_hint(type_hints.get(field_name, Any))
        class_dict['__annotations__'] = class_dict.get('__annotations__', {})
        class_dict['__annotations__'][field_name] = field_type
        meta, constraints, aliases, pydantic_raw = _extract_modict_field_metadata(field_info)

        # modict-specific transport (best-effort):
        # - preferred: FieldInfo.metadata contains _ModictFieldMeta (from modict.to_model())
        # - fallback: older json_schema_extra transport if present
        modict_required: Optional[bool] = None
        modict_default_marker: Optional[str] = None

        for item in getattr(field_info, "metadata", []) or []:
            if getattr(item, "_modict_field_meta", False):
                modict_required = bool(getattr(item, "required", False))
                modict_default_marker = getattr(item, "default_marker", None)
                break

        if modict_required is None:
            extra = getattr(field_info, "json_schema_extra", None)
            if extra is None and isinstance(pydantic_raw, dict):
                extra = pydantic_raw.get("json_schema_extra")
            if isinstance(extra, dict):
                md = extra.get("x-modict-field") or extra.get("x_modict_field")
                if isinstance(md, dict):
                    if "required" in md:
                        modict_required = bool(md.get("required"))
                    if isinstance(md.get("default"), str):
                        modict_default_marker = md.get("default")

        try:
            from pydantic.fields import FieldInfo  # type: ignore
            if isinstance(field_info, FieldInfo):
                is_required = field_info.is_required()
                if modict_required is None:
                    modict_required = bool(is_required)

                if modict_default_marker == "MISSING":
                    class_dict[field_name] = ModictField(
                        default=MISSING,
                        required=bool(modict_required),
                        metadata=meta,
                        constraints=constraints,
                        aliases=aliases,
                        _pydantic=pydantic_raw,
                    )
                elif is_required:
                    class_dict[field_name] = ModictField(
                        default=MISSING,
                        required=bool(modict_required),
                        metadata=meta,
                        constraints=constraints,
                        aliases=aliases,
                        _pydantic=pydantic_raw,
                    )
                else:
                    if field_info.default_factory is not None:
                        class_dict[field_name] = ModictField(
                            default=Factory(field_info.default_factory),
                            required=bool(modict_required) if modict_required is not None else False,
                            metadata=meta,
                            constraints=constraints,
                            aliases=aliases,
                            _pydantic=pydantic_raw,
                        )
                    else:
                        default = field_info.default
                        if str(type(default).__name__) == 'PydanticUndefinedType':
                            class_dict[field_name] = ModictField(
                                default=MISSING,
                                required=bool(modict_required) if modict_required is not None else False,
                                metadata=meta,
                                constraints=constraints,
                                aliases=aliases,
                                _pydantic=pydantic_raw,
                            )
                        else:
                            class_dict[field_name] = ModictField(
                                default=default,
                                required=bool(modict_required) if modict_required is not None else False,
                                metadata=meta,
                                constraints=constraints,
                                aliases=aliases,
                                _pydantic=pydantic_raw,
                            )
            else:
                is_required = bool(field_info.required)  # type: ignore[attr-defined]
                if modict_required is None:
                    modict_required = bool(is_required)

                if modict_default_marker == "MISSING":
                    class_dict[field_name] = ModictField(
                        default=MISSING,
                        required=bool(modict_required),
                        metadata=meta,
                        constraints=constraints,
                        aliases=aliases,
                        _pydantic=pydantic_raw,
                    )
                elif is_required:
                    class_dict[field_name] = ModictField(
                        default=MISSING,
                        required=bool(modict_required),
                        metadata=meta,
                        constraints=constraints,
                        aliases=aliases,
                        _pydantic=pydantic_raw,
                    )
                else:
                    if hasattr(field_info, 'default_factory') and field_info.default_factory:  # type: ignore[attr-defined]
                        class_dict[field_name] = ModictField(
                            default=Factory(field_info.default_factory),  # type: ignore[attr-defined]
                            required=bool(modict_required) if modict_required is not None else False,
                            metadata=meta,
                            constraints=constraints,
                            aliases=aliases,
                            _pydantic=pydantic_raw,
                        )
                    else:
                        default = field_info.default  # type: ignore[attr-defined]
                        class_dict[field_name] = ModictField(
                            default=default,
                            required=bool(modict_required) if modict_required is not None else False,
                            metadata=meta,
                            constraints=constraints,
                            aliases=aliases,
                            _pydantic=pydantic_raw,
                        )
        except Exception:
            if hasattr(field_info, 'default'):
                default = field_info.default  # type: ignore[attr-defined]
                if default is not None and str(type(default).__name__) != 'PydanticUndefinedType':
                    class_dict[field_name] = ModictField(
                        default=default,
                        required=bool(modict_required) if modict_required is not None else False,
                        metadata=meta,
                        constraints=constraints,
                        aliases=aliases,
                        _pydantic=pydantic_raw,
                    )
                else:
                    class_dict[field_name] = ModictField(
                        default=MISSING,
                        required=bool(modict_required) if modict_required is not None else False,
                        metadata=meta,
                        constraints=constraints,
                        aliases=aliases,
                        _pydantic=pydantic_raw,
                    )
            else:
                class_dict[field_name] = ModictField(
                    default=MISSING,
                    required=bool(modict_required) if modict_required is not None else False,
                    metadata=meta,
                    constraints=constraints,
                    aliases=aliases,
                    _pydantic=pydantic_raw,
                )

    return class_dict


def _attach_validators(class_dict, pydantic_validators):
    """Convert Pydantic validators to modict @check methods."""
    if not pydantic_validators:
        return

    for field_name, validator_funcs in pydantic_validators.items():
        from ._modict_meta import Validator

        # Keep Pydantic mode semantics when possible by attaching mode metadata
        by_mode: Dict[str, list[Any]] = {"before": [], "after": []}
        for item in validator_funcs:
            if isinstance(item, tuple) and len(item) == 2:
                func, mode = item
            else:
                func, mode = item, "before"
            if mode not in ("before", "after"):
                mode = "before"
            by_mode[mode].append(func)

        def make_checker(field_nm, validators, *, mode: str):
            def checker_method(self, value):
                for validator_func in validators:
                    value = Validator._call_with_context(
                        validator_func,
                        instance=self,
                        value=value,
                        field_name=field_nm,
                        cls=type(self),
                        values=dict(self),
                        info=None,
                    )
                return value
            # Use the new validator metadata; modictMeta supports both.
            checker_method._is_validator = True
            checker_method._validator_field = field_nm
            checker_method._validator_mode = mode
            return checker_method

        if by_mode["before"]:
            class_dict[f"_validator_{field_name}_before"] = make_checker(
                field_name, by_mode["before"], mode="before"
            )
        if by_mode["after"]:
            class_dict[f"_validator_{field_name}_after"] = make_checker(
                field_name, by_mode["after"], mode="after"
            )


def _extract_pydantic_computed_fields(pydantic_class: Type["BaseModel"]) -> Dict[str, Any]:
    """Extract computed fields from a Pydantic v2 model.

    Args:
        pydantic_class: Pydantic BaseModel class

    Returns:
        Dictionary mapping field names to their property getter functions
    """
    computed_fields = {}

    # Pydantic v2: Check model_computed_fields
    if hasattr(pydantic_class, 'model_computed_fields'):
        for field_name, field_info in pydantic_class.model_computed_fields.items():
            # Extract the wrapped property
            if hasattr(field_info, 'wrapped_property'):
                prop = field_info.wrapped_property
                if isinstance(prop, property) and prop.fget is not None:
                    # Get the getter function
                    getter_func = prop.fget

                    # Internal metadata for modict round-trips (best-effort).
                    # Prefer explicit getter attributes (emitted by modict.to_model()),
                    # but also accept schema metadata as a more robust transport.
                    cache = getattr(getter_func, "_modict_computed_cache", False)
                    deps = getattr(getter_func, "_modict_computed_deps", None)
                    extra = getattr(field_info, "json_schema_extra", None)
                    if isinstance(extra, dict):
                        modict_meta = (
                            extra.get("x-modict-computed")
                            or extra.get("x_modict_computed")
                            or extra.get("modict_computed")
                        )
                        if isinstance(modict_meta, dict):
                            if "cache" in modict_meta:
                                cache = bool(modict_meta.get("cache"))
                            if "deps" in modict_meta:
                                deps = modict_meta.get("deps")
                    # Store with return type if available
                    computed_fields[field_name] = {
                        'func': getter_func,
                        'return_type': getattr(field_info, 'return_type', None),
                        'cache': cache,
                        'deps': deps,
                    }

    return computed_fields


def _convert_type_hint_to_pydantic(type_hint, *, cls, config_kwargs):
    """Recursively convert modict annotations inside hints to Pydantic models."""
    if type_hint is None:
        return type_hint

    if isinstance(type_hint, type) and hasattr(type_hint, "__fields__") and issubclass(type_hint, dict):
        if type_hint is cls:
            return type_hint
        # Check global cache first
        cached = TypeCache.get_pydantic(type_hint)
        if cached is not None:
            return cached
        return to_pydantic_model(
            type_hint,
            **config_kwargs,
        )

    origin = get_origin(type_hint)
    args = get_args(type_hint)

    # If we already have Annotated, keep it as-is (it may carry modict metadata).
    if origin is Annotated:
        return type_hint

    if origin is None or not args:
        return type_hint

    if origin in (Union, types.UnionType):
        converted_args = tuple(
            _convert_type_hint_to_pydantic(arg, cls=cls, config_kwargs=config_kwargs)
            for arg in args
        )
        return Union[converted_args]  # type: ignore[index]

    converted_args = tuple(
        _convert_type_hint_to_pydantic(arg, cls=cls, config_kwargs=config_kwargs)
        for arg in args
    )

    try:
        if origin is tuple and len(converted_args) == 2 and converted_args[1] is Ellipsis:
            return tuple[converted_args[0], ...]  # type: ignore[index]
        if len(converted_args) == 1:
            return origin[converted_args[0]]  # type: ignore[index]
        return origin[converted_args]  # type: ignore[index]
    except TypeError:
        return type_hint


def _add_field_to_class_dict(field_name, field, annotations, class_dict, validators_dict, pydantic_v2, cls, config_kwargs):
    """Populate annotations and defaults for a single modict field."""
    # For schema/interop we need access to the original default marker (e.g. Factory),
    # not the evaluated value returned by get_default().
    default_value = getattr(field, "default", field.get_default())
    from ._collections_utils import MISSING
    from ._modict_meta import Factory, Computed
    from pydantic import Field
    metadata = getattr(field, "metadata", {}) or {}
    constraints = getattr(field, "constraints", {}) or {}
    aliases = getattr(field, "aliases", {}) or {}
    pydantic_raw = getattr(field, "_pydantic", None)
    if pydantic_raw is None:
        pydantic_raw = metadata.get("_pydantic", {}) if isinstance(metadata, dict) else {}

    if pydantic_v2:
        allowed_meta = {
            "alias",
            "title",
            "description",
            "gt",
            "ge",
            "lt",
            "le",
            "min_length",
            "max_length",
            "pattern",
            "multiple_of",
            "examples",
            "deprecated",
            "validation_alias",
            "serialization_alias",
            "json_schema_extra",
            "repr",
        }
    else:
        allowed_meta = {
            "alias",
            "title",
            "description",
            "gt",
            "ge",
            "lt",
            "le",
            "min_length",
            "max_length",
            "regex",
            "repr",
            "const",
        }

    field_kwargs = {k: v for k, v in metadata.items() if k in allowed_meta and v is not None}
    if isinstance(constraints, dict):
        for k, v in constraints.items():
            if k in allowed_meta and v is not None:
                field_kwargs.setdefault(k, v)
    if isinstance(aliases, dict):
        for k, v in aliases.items():
            if k in allowed_meta and v is not None:
                field_kwargs.setdefault(k, v)
    if isinstance(pydantic_raw, dict):
        for k in allowed_meta:
            if k in pydantic_raw and pydantic_raw[k] is not None:
                field_kwargs.setdefault(k, pydantic_raw[k])

    if isinstance(default_value, Computed):
        if pydantic_v2:
            return "computed", default_value
        return None, None

    converted_hint = _convert_type_hint_to_pydantic(
        field.hint if field.hint is not None else Any,
        cls=cls,
        config_kwargs=config_kwargs,
    )
    # Store modict-specific info in Annotated metadata (doesn't affect schema).
    default_marker = "MISSING" if default_value is MISSING else None
    meta = _ModictFieldMeta(required=bool(getattr(field, "required", False)), default_marker=default_marker)
    annotations[field_name] = Annotated[converted_hint, meta]

    if field.validators:
        validators_dict[field_name] = field.validators

    if default_value is MISSING:
        class_dict[field_name] = Field(..., **field_kwargs)
    elif isinstance(default_value, Factory):
        class_dict[field_name] = Field(default_factory=default_value.factory, **field_kwargs)
    else:
        class_dict[field_name] = Field(default=default_value, **field_kwargs)

    return None, None


def _add_validators_to_class_dict(class_dict, validators_dict, pydantic_v2):
    """Add Pydantic validators generated from modict validators."""
    if not validators_dict:
        return

    class _ValidatorInstance(dict):
        def __getattr__(self, name):
            try:
                return self[name]
            except KeyError as e:
                raise AttributeError(name) from e

        def __setattr__(self, name, value):
            self[name] = value

    for field_name, validators in validators_dict.items():
        before_validators = [v for v in validators if getattr(v, "mode", "before") == "before"]
        after_validators = [v for v in validators if getattr(v, "mode", "before") == "after"]

        def make_validator(field_nm, checker_list, *, mode: str):
            if pydantic_v2:
                from pydantic import field_validator

                @field_validator(field_nm, mode=mode)
                @classmethod
                def validator_func(cls, value, info=None):
                    values = getattr(info, "data", None) if info is not None else None
                    for checker in checker_list:
                        inst = _ValidatorInstance(dict(values or {}))
                        inst[field_nm] = value
                        value = checker(inst, value, cls=cls, values=inst, info=info)
                    return value

                return validator_func
            else:
                from pydantic import validator

                @validator(field_nm, pre=(mode == "before"))
                @classmethod
                def validator_func(cls, value, values=None):
                    for checker in checker_list:
                        inst = _ValidatorInstance(dict(values or {}))
                        inst[field_nm] = value
                        value = checker(inst, value, cls=cls, values=inst, info=None)
                    return value

                return validator_func

        if before_validators:
            class_dict[f"validate_{field_name}_before"] = make_validator(
                field_name, before_validators, mode="before"
            )
        if after_validators:
            class_dict[f"validate_{field_name}_after"] = make_validator(
                field_name, after_validators, mode="after"
            )


def _add_computed_fields(class_dict, computed_fields, pydantic_v2):
    """Convert modict computed fields to Pydantic computed_field (v2)."""
    if not (pydantic_v2 and computed_fields):
        return
    import inspect  # noqa: F401
    from pydantic import computed_field

    for field_name, computed in computed_fields.items():
        return_type = Any
        if hasattr(computed.func, '__annotations__'):
            return_type = computed.func.__annotations__.get('return', Any)

        def make_computed_getter(comp, ret_type):
            def getter(self):
                return comp.func(self)
            getter.__annotations__ = {'return': ret_type}
            # Internal: preserve modict computed semantics for round-trips.
            setattr(getter, "_modict_computed_cache", bool(getattr(comp, "cache", False)))
            setattr(getter, "_modict_computed_deps", getattr(comp, "deps", None))
            return getter

        getter = make_computed_getter(computed, return_type)

        extra = {
            "x-modict-computed": {
                "cache": bool(getattr(computed, "cache", False)),
                "deps": getattr(computed, "deps", None),
            }
        }

        # Prefer passing metadata via json_schema_extra (robust transport),
        # but keep the no-args form as a fallback for older Pydantic v2 builds.
        try:
            kwargs = {"json_schema_extra": extra}
            if return_type is not Any:
                kwargs["return_type"] = return_type
            class_dict[field_name] = computed_field(**kwargs)(getter)
        except TypeError:
            class_dict[field_name] = computed_field(getter)


def _add_model_validators_to_class_dict(class_dict, model_validators, pydantic_v2):
    """Add Pydantic model validators generated from modict model validators."""
    if not model_validators:
        return

    if pydantic_v2:
        from pydantic import model_validator

        for idx, mv in enumerate(model_validators):
            mv_mode = getattr(mv, "mode", "after")
            if mv_mode not in ("before", "after"):
                continue

            if mv_mode == "before":
                @model_validator(mode="before")
                @classmethod
                def validator_func(cls, data, _mv=mv):
                    values = data if isinstance(data, dict) else data
                    result = _mv(None, cls=cls, values=values, info=None)
                    return values if result is None else result
            else:
                @model_validator(mode="after")
                def validator_func(self, _mv=mv):
                    values = self.model_dump()  # type: ignore[attr-defined]
                    result = _mv(self, cls=type(self), values=values, info=None)
                    if isinstance(result, dict):
                        for k, v in result.items():
                            setattr(self, k, v)
                    return self

            class_dict[f"model_validate_{idx}_{mv_mode}"] = validator_func
    else:
        from pydantic import root_validator

        for idx, mv in enumerate(model_validators):
            mv_mode = getattr(mv, "mode", "after")
            pre = (mv_mode == "before")

            @root_validator(pre=pre)
            @classmethod
            def validator_func(cls, values, _mv=mv):
                result = _mv(None, cls=cls, values=values, info=None)
                return values if result is None else result

            class_dict[f"root_validate_{idx}_{'pre' if pre else 'post'}"] = validator_func


def _add_config(class_dict, *, pydantic_v2, config_class, config_kwargs, modict_class=None):
    """Attach Pydantic config depending on version.

    Args:
        class_dict: Class dictionary to add config to
        pydantic_v2: Whether using Pydantic v2
        config_class: Optional explicit config class
        config_kwargs: Optional config kwargs
        modict_class: Optional modict class to extract config from
    """
    if pydantic_v2:
        from pydantic import ConfigDict
        config_dict = {}

        # Extract and map modict config if available
        if modict_class and hasattr(modict_class, '_config'):
            config_dict.update(_modict_config_to_pydantic(modict_class._config))

        # Override with explicit config kwargs
        if config_kwargs:
            config_dict.update(config_kwargs)

        if config_dict:
            class_dict['model_config'] = ConfigDict(**config_dict)
    else:
        if config_class:
            class_dict['Config'] = config_class
        elif config_kwargs:
            # For v1, also try to extract modict config
            if modict_class and hasattr(modict_class, '_config'):
                pydantic_config = _modict_config_to_pydantic(modict_class._config)
                pydantic_config.update(config_kwargs)
                class_dict['Config'] = type('Config', (), pydantic_config)
            else:
                class_dict['Config'] = type('Config', (), config_kwargs)


def from_pydantic_model(
    cls,
    pydantic_class: Type['BaseModel'],
    *,
    name: Optional[str] = None,
    strict: Optional[bool] = None,
    coerce: Optional[bool] = None,
    **config_kwargs
) -> Type:
    """Create a modict class from a Pydantic model class.

    Extracts field definitions, type hints, and default values from the Pydantic
    model and creates an equivalent modict class.

    Args:
        cls: The modict base class (usually modict itself)
        pydantic_class: Pydantic BaseModel class to convert
        name: Name for the new modict class (default: same as Pydantic class)
        strict: Pydantic-like strict mode (no coercion)
        coerce: Deprecated alias; use strict=False instead
        **config_kwargs: Additional modict config options

    Returns:
        A new modict class with fields matching the Pydantic model

    Raises:
        ImportError: If Pydantic is not installed
        TypeError: If pydantic_class is not a Pydantic BaseModel

    Examples:
        >>> from pydantic import BaseModel
        >>> class UserModel(BaseModel):
        ...     name: str
        ...     age: int = 25
        ...     email: str | None = None
        >>>
        >>> User = modict.from_model(UserModel)
        >>> user = User(name="Alice")
        >>> user.age
        25
    """
    _check_pydantic_available()

    from pydantic import BaseModel
    from pydantic.fields import FieldInfo

    if not isinstance(pydantic_class, type) or not issubclass(pydantic_class, BaseModel):
        raise TypeError(
            f"Expected Pydantic BaseModel class, got {type(pydantic_class).__name__}"
        )

    # Return cached conversion to handle shared nested models
    cached = TypeCache.get_modict(pydantic_class)
    if cached is not None:
        return cached

    # Determine the new class name
    class_name = name or pydantic_class.__name__

    # Extract fields from Pydantic model
    class_dict = {}

    # Get type hints
    type_hints = get_type_hints(pydantic_class)

    # Extract field information (Pydantic v2 and v1 compatible)
    model_fields = _get_pydantic_fields(pydantic_class)

    convert_hint = lambda th: _convert_type_hint_from_pydantic(  # noqa: E731
        th,
        pydantic_class=pydantic_class,
        cls=cls,
        strict=strict,
        coerce=coerce,
        config_kwargs=config_kwargs,
    )

    # Convert each field
    for field_name, field_info in model_fields.items():
        field_type = convert_hint(type_hints.get(field_name, Any))
        class_dict['__annotations__'] = class_dict.get('__annotations__', {})
        class_dict['__annotations__'][field_name] = field_type

    convert_hint = lambda th: _convert_type_hint_from_pydantic(  # noqa: E731
        th,
        pydantic_class=pydantic_class,
        cls=cls,
        strict=strict,
        coerce=coerce,
        config_kwargs=config_kwargs,
    )

    # Build class dict (fields + defaults)
    class_dict.update(_build_class_dict_from_pydantic(model_fields, type_hints, convert_hint))

    # Extract validators from Pydantic model
    pydantic_validators = _resolve_pydantic_validators(pydantic_class)

    # Attach validators as modict validators
    _attach_validators(class_dict, pydantic_validators)

    # Attach model validators (root/model validators)
    pydantic_model_validators = _resolve_pydantic_model_validators(pydantic_class)
    if pydantic_model_validators:
        from ._modict_meta import ModelValidator
        class_dict["__model_validators__"] = tuple(
            ModelValidator(func, mode=mode) for func, mode in pydantic_model_validators
        )

    # Extract and convert computed fields from Pydantic to modict
    pydantic_computed = _extract_pydantic_computed_fields(pydantic_class)
    if pydantic_computed:
        from ._modict_meta import Computed

        for field_name, field_data in pydantic_computed.items():
            # Create modict Computed field from Pydantic computed field
            getter_func = field_data['func']
            ret_type = field_data.get('return_type')
            cache = bool(field_data.get("cache", False))
            deps = field_data.get("deps", None)

            # Wrap the getter to work with modict instances
            # Use default parameters to capture variables in the closure
            def make_computed_wrapper(func, return_type):
                def wrapper(self):
                    return func(self)
                # Preserve annotations if available
                if return_type:
                    wrapper.__annotations__ = {'return': return_type}
                return wrapper

            wrapped_getter = make_computed_wrapper(getter_func, ret_type)

            # Add as Computed field to class dict
            class_dict[field_name] = Computed(wrapped_getter, cache=cache, deps=deps)

            # Add annotation if we have a return type
            if ret_type:
                if '__annotations__' not in class_dict:
                    class_dict['__annotations__'] = {}
                class_dict['__annotations__'][field_name] = ret_type

    # Build modict config
    config_dict = {}

    # modict -> Pydantic -> modict: restore modict-specific config when present.
    interop = getattr(pydantic_class, "__modict__", None)
    if isinstance(interop, dict):
        md_cfg = interop.get("config")
        if isinstance(md_cfg, dict):
            ck = md_cfg.get("check_keys", None)
            if ck in (True, False, "auto"):
                config_dict["check_keys"] = ck

    # Extract Pydantic model config
    pydantic_model_config = None
    if hasattr(pydantic_class, 'model_config'):
        # Pydantic v2
        pydantic_model_config = pydantic_class.model_config
    elif hasattr(pydantic_class, 'Config') or hasattr(pydantic_class, '__config__'):
        # Pydantic v1
        pydantic_model_config = getattr(pydantic_class, 'Config', getattr(pydantic_class, '__config__', None))

    # Map Pydantic config to modict config (including defaults when config is empty).
    if pydantic_model_config is not None:
        config_dict.update(_pydantic_config_to_modict(pydantic_model_config))

    # Override with explicit parameters
    if strict is not None:
        config_dict['strict'] = strict
    if coerce is not None:
        warnings.warn(
            "from_model(..., coerce=...) is deprecated; use strict=False/True instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        if 'strict' not in config_dict:
            config_dict['strict'] = (not bool(coerce))

    # Add user-provided config kwargs
    config_dict.update(config_kwargs)

    if config_dict:
        from ._modict_meta import modictConfig
        class_dict['_config'] = modictConfig(**config_dict)

    # Create the new modict class
    new_class = type(class_name, (cls,), class_dict)

    # Cache the conversion globally
    TypeCache.set_modict(pydantic_class, new_class)

    return new_class


def to_pydantic_model(
    cls,
    *,
    name: Optional[str] = None,
    config_class: Optional[Type] = None,
    **config_kwargs
) -> Type['BaseModel']:
    """Create a Pydantic model class from a modict class.

    Extracts field definitions, type hints, and default values from the modict
    class and creates an equivalent Pydantic BaseModel.

    Args:
        cls: The modict class to convert
        name: Name for the new Pydantic class (default: same as modict class)
        config_class: Optional Pydantic Config class to use
        **config_kwargs: Pydantic config options (e.g., arbitrary_types_allowed=True)

    Returns:
        A new Pydantic BaseModel class with fields matching the modict

    Raises:
        ImportError: If Pydantic is not installed

    Examples:
        >>> class User(modict):
        ...     name: str
        ...     age: int = 25
        ...     email: str | None = None
        >>>
        >>> UserModel = User.to_model()
        >>> user = UserModel(name="Bob")
        >>> user.age
        25
    """
    _check_pydantic_available()

    # Return cached conversion to handle shared nested modicts
    cached = TypeCache.get_pydantic(cls)
    if cached is not None:
        return cached

    from pydantic import BaseModel
    try:
        # Pydantic v2
        from pydantic import ConfigDict, Field, computed_field, field_validator
        pydantic_v2 = True
    except ImportError:
        # Pydantic v1
        from pydantic import Field, validator
        pydantic_v2 = False

    class_name = name or cls.__name__

    class_dict: Dict[str, Any] = {}
    annotations: Dict[str, Any] = {}
    computed_fields: Dict[str, Any] = {}
    validators_dict: Dict[str, Any] = {}

    if hasattr(cls, '__fields__'):
        for field_name, field in cls.__fields__.items():
            result = _add_field_to_class_dict(
                field_name,
                field,
                annotations,
                class_dict,
                validators_dict,
                pydantic_v2,
                cls,
                config_kwargs,
            )
            if result and result[0] == "computed":
                computed_fields[field_name] = result[1]

    class_dict['__annotations__'] = annotations

    _add_computed_fields(class_dict, computed_fields, pydantic_v2)
    _add_validators_to_class_dict(class_dict, validators_dict, pydantic_v2)
    _add_model_validators_to_class_dict(
        class_dict,
        getattr(cls, "__model_validators__", ()),
        pydantic_v2,
    )
    _add_config(
        class_dict,
        pydantic_v2=pydantic_v2,
        config_class=config_class,
        config_kwargs=config_kwargs,
        modict_class=cls  # Pass the modict class to extract config
    )

    new_model = type(class_name, (BaseModel,), class_dict)

    # Preserve modict-specific config for round-trips (class-level; doesn't affect schema).
    try:
        ck = getattr(getattr(cls, "_config", None), "check_keys", "auto")
        if ck in (True, False, "auto"):
            setattr(new_model, "__modict__", {"config": {"check_keys": ck}})
    except Exception:
        pass

    # Cache the conversion globally
    TypeCache.set_pydantic(cls, new_model)

    return new_model
