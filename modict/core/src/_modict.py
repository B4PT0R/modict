from collections.abc import Mapping
from types import ClassMethodDescriptorType
from typing import Optional, Union, Tuple, Set, Dict, List, Any, Callable, Type
from ...typechecker import TypeMismatchError, check_type
from ...model_api import (
    Attribute,
    check_json_serializable,
    invalidate_dependants,
    maybe_coerce,
)
from ._modict_meta import modictMeta, Factory, Computed, modictItemsView,modictKeysView,modictValuesView, modictConfig
from ...model_api.src._field import _normalize_required, _REQUIRED_ORDER


def _effective_required(field_required, require_all) -> str:
    """Return the stronger of field_required and require_all.

    Both arguments are normalized to RequiredLevel strings first.
    Strength order: "always" > "at_init" > "never".
    """
    a = _normalize_required(field_required)
    b = _normalize_required(require_all)
    return max(a, b, key=lambda x: _REQUIRED_ORDER[x])
from ...path_utils import Path, ResolutionError
from ...collections_utils import (
    keys,
    set_key,
    has_key,
    unroll,
    MISSING,
    is_container,
    is_mutable_container,
    has_nested,
    get_nested,
    set_nested,
    del_nested,
    pop_nested,
    walk,
    unwalk,
    deep_merge,
    diff_nested,
    deep_equals,
    exclude,
    extract,
    to_jsonable,
    json_dumps,
)
import copy
import json
import importlib
from typing import Literal
from collections.abc import MutableMapping, MutableSequence


class _ModictGenericAlias:
    def __init__(self, origin, key_hint, value_hint):
        self.__origin__ = origin
        self.__args__ = (key_hint, value_hint)
        self.__modict_generic_hints__ = (key_hint, value_hint)

    def __mro_entries__(self, bases):
        return (self.__origin__,)

    def __repr__(self) -> str:
        origin_name = getattr(self.__origin__, "__name__", repr(self.__origin__))
        key_hint, value_hint = self.__args__
        return f"{origin_name}[{key_hint!r}, {value_hint!r}]"


class modict(dict, metaclass=modictMeta):
    """A dict with additional capabilities.

    All native dict methods are supported, plus the following additional features:

    Features:
        - Attribute-style access to keys
        - Recursive conversion of nested dicts to modicts (including in nested containers)
        - Extract/exclude methods for convenient key filtering
        - Type annotations and defaults via class fields
        - Robust runtime type-checking and coercion (optional)
        - Computed values with caching and dependency-bound invalidation
        - Key translation via translate() without mutating the source object
        - JSONPath support (RFC 9535) for unambiguous nested access
        - Path-based access for nested structures (get_nested, set_nested, etc.)
        - Deep walking, merging, diffing, and comparing with other nested structures
        - Native JSON support

    Examples:
        >>> m = modict(a=[modict(b=1, c=2)])
        >>> m.a[0].b
        1
        >>> m.get_nested("$.a[0].c")  # JSONPath
        2
        >>> m.set_nested("$.a[0].d", 3)
        >>> # walk() returns Path objects for disambiguation
        >>> for path, value in m.walk():
        ...     print(f"{path}: {value}")
        $.a[0].b: 1
        $.a[0].c: 2
        $.a[0].d: 3
    """

    @classmethod
    def __class_getitem__(cls, params):
        if not isinstance(params, tuple):
            raise TypeError("modict[...] expects two parameters: [key_type, value_type]")
        if len(params) != 2:
            raise TypeError("modict[...] expects exactly two parameters: [key_type, value_type]")
        key_hint, value_hint = params
        return _ModictGenericAlias(cls, key_hint, value_hint)

    @classmethod
    def factory(cls, default_factory: Callable):
        """Create a factory for default values.

        Used to define a factory that generates default values dynamically.
        Instead of passing a static default value to a field, the callable
        is used to create a new value for every instance.

        Args:
            default_factory: A callable that returns a new default value

        Returns:
            Factory: A Factory instance wrapping the callable

        Examples:
            >>> class User(modict):
            ...     name: str
            ...     id = modict.factory(lambda: random.choice(range(10000)))
        """
        return Factory(default_factory)

    @classmethod
    def config(cls, **kwargs):
        """
        Class method to create a modictConfig for use in modict subclasses.

        Usage:
            class MyModict(modict):
                _config = modict.config(enforce_json=True, extra='forbid')
                name: str
                age: int

        Args:
            check_values: Enable/disable modict's validation pipeline (True/False)
            auto_convert: Automatically convert nested dicts to modicts
            ignore_none: Skip key assignments whose value is None
            extra: Control extra attributes ('allow', 'forbid', 'ignore')
            strict: Pydantic-like strict mode (no coercion)
            enforce_json: Ensure all values are JSON-serializable
            frozen: Make instances immutable
            validate_assignment: Validate values on assignment
            validate_default: Validate class defaults at definition time
            str_strip_whitespace/str_to_lower/str_to_upper: Optional string transforms
            use_enum_values: Normalize Enum to .value
            allow_inf_nan: Control NaN/Inf JSON encoding when enforce_json=True
            from_attributes: Allow building from objects with attributes
            json_encoders: Type -> callable encoders for serialization/enforce_json

            Note: `modict.config(...)` only accepts modict-supported options.

        Returns:
            modictConfig instance
        """
        base_config = getattr(cls, "_config", None)
        local_config = modictConfig(**kwargs)
        if base_config is None:
            return local_config
        return base_config.merge(local_config)

    @classmethod
    def field(
        cls,
        *,
        default=MISSING,
        hint=None,
        required: Optional[Union[bool, Literal["always", "at_init", "never"]]] = None,
        validators=None,
    ):
        """Convenience factory for Field(...) without importing Field directly.
        """
        from ._modict_meta import Field as ModictField
        f = ModictField(default=default, hint=hint)
        if required is not None:
            f.required = _normalize_required(required)
        if validators is not None:
            f.validators = list(validators)
        return f

    @classmethod
    def attr(cls, value: Any) -> Attribute:
        """Wrap a value so it stays an attribute instead of becoming a field."""
        return Attribute(value)

    @classmethod
    def wrap(cls, *wrap_args, **wrap_kwargs):
        """Return a wrapped constructor without changing the native dict signature.

        This exists for business/runtime parameters that should not be threaded
        through ``__init__`` itself. ``MyModict(data)`` and
        ``MyModict(**dict_kwargs)`` stay dict-like and predictable; enriched
        construction goes through ``MyModict.wrap(...)(...)`` instead.

        ``wrap(...)`` intentionally resolves a single ``__wrap_init__`` entry
        point on ``cls``. If subclasses want to compose with parent wrapping
        logic, they must route parameters and call parent ``__wrap_init__``
        explicitly from their own override.
        """
        return cls.__wrap_init__(cls, *wrap_args, **wrap_kwargs)

    @classmethod
    def __wrap_init__(cls, init, *wrap_args, **wrap_kwargs):
        """Special method reserved for wrapping the dict-like constructor."""
        return init

    @classmethod
    def validator(cls, field_name, *, mode: Literal["before", "after"] = "before"):
        """Decorator to create field validators/transformers.

        Args:
            field_name: The name of the field to validate/transform
            mode: Validator mode:
                - "before": run before coercion/type-checking (default, current modict behavior)
                - "after": run after coercion/type-checking (reserved for future use)

        Returns:
            A decorator function that marks methods as field validators

        Examples:
            >>> class User(modict):
            ...     email: str
            ...
            ...     @modict.validator('email')
            ...     def validate_email(self, value):
            ...         return value.lower().strip()
        """
        def decorator(f):
            f._is_validator = True
            f._validator_field = field_name
            f._validator_mode = mode
            return f
        return decorator

    @classmethod
    def any_validator(cls, func=None, *, mode: Literal["before", "after"] = "before"):
        """Decorator to create key-aware validators for any modified item.

        Expected signature: ``(self, key, value) -> value``.

        These validators run for every validated key, without having to declare
        an explicit field dependency.
        """
        if func is None:
            def decorator(f):
                f._is_any_validator = True
                f._any_validator_mode = mode
                return f
            return decorator
        else:
            func._is_any_validator = True
            func._any_validator_mode = mode
            return func

    @classmethod
    def model_validator(cls, func=None, *, mode: Literal["before", "after"] = "after"):
        """Decorator to create model-level validators (multi-field invariants).

        Expected signature: ``(self) -> None | Mapping | self``

        Model validators run in two phases relative to field-level validators and
        coercion/type-checking:
        - mode="before": runs after individual field validators "before", before coercion
        - mode="after": runs after individual field validators "after", after coercion

        In both modes the decorated function receives the live instance and must
        mutate it in place. The return value is ignored.
        """
        if func is None:
            def decorator(f):
                f._is_model_validator = True
                f._model_validator_mode = mode
                return f
            return decorator
        else:
            func._is_model_validator = True
            func._model_validator_mode = mode
            return func

    @classmethod
    def computed(cls, func=None, *, cache=False, deps=None):
        """Create computed properties or decorate methods as computed.

        Args:
            func: The function to use for computation
            cache: Whether to cache the computed value
            deps: List of keys to watch for invalidation. Can include:
                - Regular field names: ['a', 'b']
                - Other computed field names: ['other_computed']
                - None (default): invalidate on any change
                - []: never invalidate automatically

        Returns:
            Either a Computed instance or a decorator function

        Examples:
            Usage as function::

                sum = modict.computed(lambda m: m.a + m.b, cache=True, deps=['a', 'b'])

            Usage as decorator (always with parentheses)::

                @modict.computed(cache=True, deps=['a', 'b'])
                def sum_ab(self):
                    return self.a + self.b

                @modict.computed(cache=True, deps=['sum_ab', 'c'])  # Depends on another computed
                def final_result(self):
                    return self.sum_ab + self.c

                @modict.computed(cache=True, deps=[])  # Never invalidate automatically
                def expensive_once(self):
                    return heavy_calc()

            Cascading invalidation example::

                class Calculator(modict):
                    a: float = 0
                    b: float = 0
                    c: float = 0

                    @modict.computed(cache=True, deps=['a', 'b'])
                    def sum_ab(self):
                        print("Calculating sum_ab")
                        return self.a + self.b

                    @modict.computed(cache=True, deps=['sum_ab', 'c'])
                    def final_result(self):
                        print("Calculating final_result")
                        return self.sum_ab + self.c

                calc = Calculator(a=1, b=2, c=3)
                print(calc.final_result)  # "Calculating sum_ab", "Calculating final_result", prints 6
                print(calc.final_result)  # Prints 6 (cached, no calculation)

                calc.a = 10  # Change 'a' -> sum_ab invalid -> final_result invalid automatically
                print(calc.final_result)  # "Calculating sum_ab", "Calculating final_result", prints 15
        """
        if func is None:
            # Called as decorator: @modict.computed() or @modict.computed(cache=True, deps=['a'])
            def decorator(f):
                f._is_computed = True
                f._computed_cache = cache
                f._computed_deps = deps
                return f
            return decorator
        else:
            # Called as function: modict.computed(lambda m: m.a + m.b, cache=True, deps=['a', 'b'])
            return Computed(func, cache=cache, deps=deps)

    def __init__(self, *args, **kwargs):

        object.__setattr__(self, "_config", type(self)._config.copy())

        if (
            self._config.from_attributes
            and len(args) == 1
            and not kwargs
            and not isinstance(args[0], Mapping)
        ):
            src = args[0]
            data: dict[str, Any] = {}
            for field_name in getattr(self, "__fields__", {}):
                if hasattr(src, field_name):
                    data[field_name] = getattr(src, field_name)
            args = (data,)

        args, kwargs = self._filter_none_assignments(args, kwargs)

        super().__init__(*args,**kwargs)
        object.__setattr__(
            self,
            "_computed_field_count",
            sum(1 for value in dict.values(self) if isinstance(value, Computed)),
        )
        self._extract_attribute_wrappers()

        # Inject defaults and computed
        for key, field in self.__fields__.items():
            value = field.get_default()
            if value is not MISSING:
                if isinstance(value, Computed):
                    # During model instantiation/casting, target-class Computed fields
                    # always win over incoming data so the resulting instance respects
                    # the target model contract.
                    self._raw_setitem(key, value)
                else:
                    if key not in self and self._should_materialize_default(key, value):
                        self._raw_setitem(key, value)

        if self._check_keys_enabled():
            self._normalize_keys()

        # Enforce key-level constraints (required/extra/require_all) independently of value checking.
        if self._check_keys_enabled():
            self._enforce_extra_policy()
            self._check_required_fields()

        if self._check_values_enabled():
            self.validate()

    def _extract_attribute_wrappers(self) -> None:
        for key, value in list(dict.items(self)):
            if isinstance(value, Attribute):
                dict.__delitem__(self, key)
                self._store_attribute(key, value)

    def _store_attribute(self, key: str, value: Attribute) -> None:
        if key in getattr(self, "__fields__", {}):
            raise AttributeError(f"Cannot store attribute '{key}': that name is declared as a field")
        if key in self:
            raise AttributeError(f"Cannot store attribute '{key}': that name already exists as a mapping key")
        class_attributes = getattr(type(self), "__attributes__", {})
        if hasattr(type(self), key) and key not in class_attributes:
            raise AttributeError(
                f"Cannot assign attribute '{key}': '{type(self).__name__}.{key}' already exists. "
                "Use a different name for metadata attributes."
        )
        object.__setattr__(self, key, value.value)

    def _raw_setitem(self, key, value) -> None:
        existing = dict.get(self, key, MISSING)
        if isinstance(existing, Computed):
            object.__setattr__(self, "_computed_field_count", self._computed_field_count - 1)
        dict.__setitem__(self, key, value)
        if isinstance(value, Computed):
            object.__setattr__(self, "_computed_field_count", self._computed_field_count + 1)

    def _raw_delitem(self, key) -> None:
        existing = dict.__getitem__(self, key)
        if isinstance(existing, Computed):
            object.__setattr__(self, "_computed_field_count", self._computed_field_count - 1)
        dict.__delitem__(self, key)

    def _raw_clear(self) -> None:
        dict.clear(self)
        object.__setattr__(self, "_computed_field_count", 0)

    def _should_ignore_none_assignment(self, value) -> bool:
        return value is None and bool(getattr(self._config, "ignore_none", False))

    def _filter_none_assignments(self, args, kwargs):
        if not bool(getattr(self._config, "ignore_none", False)):
            return args, kwargs

        filtered_kwargs = {key: value for key, value in kwargs.items() if value is not None}
        if not args:
            return args, filtered_kwargs

        source = args[0]
        if hasattr(source, "items"):
            filtered_source = [(key, value) for key, value in source.items() if value is not None]
        else:
            filtered_source = [(key, value) for key, value in source if value is not None]
        return (filtered_source, *args[1:]), filtered_kwargs

    def _should_materialize_default(self, key, value) -> bool:
        if value is not None:
            return True
        if not bool(getattr(self._config, "ignore_none", False)):
            return True

        fields = getattr(self, "__fields__", {}) or {}
        field = fields.get(key)
        if field is None:
            return True

        require_all = getattr(self._config, "require_all", "never")
        effective = _effective_required(getattr(field, "required", "never"), require_all)
        return effective != "never"

    def _clone_for_assignment_validation(self):
        """Clone the raw instance state for transactional assignment validation."""
        new = type(self)._new_empty_like(config=self._config)
        for attr_key, attr_value in self.__dict__.items():
            if attr_key in {"_config", "_computed_field_count", "_in_model_validator"}:
                continue
            object.__setattr__(new, attr_key, attr_value)
        for key, value in dict.items(self):
            cloned = copy.copy(value) if isinstance(value, Computed) else value
            new._raw_setitem(key, cloned)
        return new

    def _replace_instance_state(self, other) -> None:
        """Replace raw mapping state from another validated instance clone."""
        for attr_key in list(self.__dict__.keys()):
            if attr_key in {"_config", "_computed_field_count", "_in_model_validator"}:
                continue
            object.__delattr__(self, attr_key)
        for attr_key, attr_value in other.__dict__.items():
            if attr_key in {"_config", "_computed_field_count", "_in_model_validator"}:
                continue
            object.__setattr__(self, attr_key, attr_value)

        self._raw_clear()
        for key, value in dict.items(other):
            self._raw_setitem(key, value)

    def _check_keys_enabled(self) -> bool:
        """Return True if modict should enforce key-level structural constraints."""
        config = self._config
        if not config.check_keys:
            return False

        if getattr(type(self), "__default_key_hint__", None) is not None:
            return True

        if config.require_all != "never" or config.extra != "allow":
            return True

        cls = type(self)
        if cls.__has_required_fields__ or cls.__has_declared_computed_fields__:
            return True

        # Also enable key checks as soon as the instance contains computed fields.
        # This preserves the default "computed override protection" even for plain `modict`
        # instances where computeds are inserted dynamically at runtime.
        return bool(self._computed_field_count)

    def _default_key_hint(self):
        return getattr(type(self), "__default_key_hint__", None)

    def _default_value_hint(self):
        return getattr(type(self), "__default_value_hint__", None)

    def _check_type_with_message(self, *, subject, value, hint, conflict_hint=None):
        try:
            check_type(hint, value)
            return True
        except TypeMismatchError as e:
            if conflict_hint is not None:
                raise TypeError(
                    f"Key {subject!r} uses incompatible hints: field hint {conflict_hint!r} "
                    f"accepts value {value!r}, but default hint {hint!r} rejects it"
                ) from e
            raise TypeError(f"Key {subject!r} expected {hint}, got {type(value)}") from e

    def _coerce_key(self, key):
        hint = self._default_key_hint()
        if hint is None or self._config.strict:
            return key
        return maybe_coerce(key, hint)

    def _normalize_key(self, key):
        hint = self._default_key_hint()
        if hint is None:
            return key
        normalized = self._coerce_key(key)
        self._check_type_with_message(subject=key, value=normalized, hint=hint)
        return normalized

    def _normalize_keys(self) -> None:
        hint = self._default_key_hint()
        if hint is None:
            return

        replacements: list[tuple[Any, Any, Any]] = []
        seen_targets: dict[Any, Any] = {}
        for key, value in list(dict.items(self)):
            normalized = self._normalize_key(key)
            if normalized == key and type(normalized) is type(key):
                continue

            other_source = seen_targets.get(normalized, key)
            if other_source != key:
                raise KeyError(f"Key normalization collision: {other_source!r} and {key!r} both normalize to {normalized!r}")
            if normalized in self and normalized != key:
                raise KeyError(f"Key normalization collision: {key!r} normalizes to existing key {normalized!r}")

            seen_targets[normalized] = key
            replacements.append((key, normalized, value))

        for old_key, new_key, value in replacements:
            self._raw_delitem(old_key)
            self._raw_setitem(new_key, value)

    def _enforce_extra_policy(self) -> None:
        """Enforce extra key policy (allow/forbid/ignore)."""
        if not isinstance(getattr(self, "__fields__", None), dict):
            return

        extra = getattr(self._config, "extra", "allow")
        if extra == "allow":
            return

        keys_to_remove: list[str] = []
        for key in dict.keys(self):
            if key in self.__fields__:
                continue
            if extra == "forbid":
                raise KeyError(
                    f"Key {key!r} is not allowed. Only the following keys are permitted: "
                    f"{list(self.__fields__.keys())}"
                )
            if extra == "ignore":
                keys_to_remove.append(key)

        for key in keys_to_remove:
            self._raw_delitem(key)

    def _check_required_fields(self) -> None:
        if not self._check_keys_enabled():
            return
        fields = getattr(self, "__fields__", {}) or {}
        require_all = getattr(self._config, "require_all", "never")
        for name, field in fields.items():
            effective = _effective_required(getattr(field, "required", "never"), require_all)
            # "at_init" and "always" both require presence at construction / validate() time
            if effective == "never":
                continue
            # Computed fields aren't populated from input, but they are still part of the
            # instance dict (stored as Computed objects). If the field is required, ensure
            # the key exists.
            if name not in self:
                raise KeyError(f"Missing required field '{name}'")

    def validate(self):
        values_enabled = self._check_values_enabled()
        keys_enabled = self._check_keys_enabled()

        if (not values_enabled) and (not keys_enabled):
            return

        if keys_enabled:
            self._normalize_keys()
            self._enforce_extra_policy()
            self._check_required_fields()

        # Model-level validators (pre)
        self._run_model_validators(mode="before")
        # A "before" model validator may have replaced the underlying mapping.
        if keys_enabled:
            self._normalize_keys()
            self._enforce_extra_policy()
            self._check_required_fields()

        if not values_enabled:
            return

        keys_to_remove = []
        for key, value in dict.items(self):
            # 1. Handle extra keys based on config
            if key not in self.__fields__:
                if self._config.extra == 'forbid':
                    raise KeyError(
                        f"Key {key!r} is not allowed. Only the following keys are permitted: "
                        f"{list(self.__fields__.keys())}"
                    )
                elif self._config.extra == 'ignore':
                    # Mark for removal (don't modify dict during iteration)
                    keys_to_remove.append(key)
                    continue
                # extra == 'allow': continue with validation

            # 2. Skip Computed fields — their values are not stored directly
            if isinstance(value, Computed):
                continue

            # 3. Validate and store
            self._raw_setitem(key, self._check_value(key, value))

        # Remove ignored keys after iteration
        for key in keys_to_remove:
            self._raw_delitem(key)

        # Model-level validators (post)
        self._run_model_validators(mode="after")

    def _check_values_enabled(self) -> bool:
        """Return True if modict should run its value/key checking pipeline."""
        config = self._config
        if not config.check_values:
            return False

        cls = type(self)
        if cls.__has_field_hints__ or cls.__has_field_validators__ or cls.__has_model_validators__:
            return True

        if config.enforce_json or config.validate_assignment or config.strict:
            return True

        return config.extra != "allow"

    def _run_model_validators(self, *, mode: Literal["before", "after"]) -> None:
        """Run model-level validators for a given phase."""
        if not self._check_values_enabled():
            return
        validators = getattr(self, "__model_validators__", ())
        if not validators:
            return

        depth = getattr(self, "_in_model_validator", 0)
        object.__setattr__(self, "_in_model_validator", depth + 1)
        try:
            for validator in validators:
                if getattr(validator, "mode", "after") != mode:
                    continue
                validator(self)
        finally:
            object.__setattr__(self, "_in_model_validator", depth)

    def _check_value(self, key, value, hint=None):
        """Consolidate all validation: validators + type checking.

        Used for incoming, outgoing, and computed property values.

        Args:
            key: The field name
            value: The value to check/transform
            hint: Optional type hint (if None, taken from Field)

        Returns:
            The checked and potentially transformed value
        """
        if not self._check_values_enabled():
            return value

        # 1. Apply validators "before" (permissive transformations)
        value = self._apply_validators(key, value, mode="before")

        field = self.__fields__.get(key)
        field_hint = hint
        if field_hint is None and field and field.hint is not None:
            field_hint = field.hint
        default_hint = self._default_value_hint()

        # 2. Coerce to expected type (skipped in strict mode)
        if not self._config.strict:
            value = self._coerce_value(key, value, field_hint or default_hint)

        # 3. Type check (always; strict controls whether coercion was attempted first)
        if field_hint is not None:
            self._check_type_with_message(subject=key, value=value, hint=field_hint)

        if default_hint is not None:
            try:
                same_hint = field_hint == default_hint
            except Exception:
                same_hint = field_hint is default_hint
            if not same_hint:
                self._check_type_with_message(
                    subject=key,
                    value=value,
                    hint=default_hint,
                    conflict_hint=field_hint if field_hint is not None else None,
                )

        # 4. Apply validators "after" (restrictive transformations)
        value = self._apply_validators(key, value, mode="after")

        if self._config.enforce_json:
            self._check_json_serializable(key, value)

        return value

    def _apply_validators(self, key, value, *, mode: Literal["before", "after"] = "before"):
        """Apply field validators for a given phase (parent → child).

        Args:
            key: The field name
            value: The value to check
            mode: "before" (default) or "after"

        Returns:
            The transformed value after all validators
        """
        any_validators = getattr(type(self), "__any_validators__", ())
        for validator in any_validators:
            if getattr(validator, "mode", "before") == mode:
                value = validator(self, key, value)

        field = self.__fields__.get(key)
        validators = getattr(field, "validators", None)
        if field and validators:
            for validator in validators:
                if getattr(validator, "mode", "before") == mode:
                    value = validator(self, value)
        return value

    
    def _coerce_value(self, key: str, value: Any, hint: Any = None) -> Any:
        """Attempt to coerce value to the expected type.

        Args:
            key: The field name
            value: The value to coerce
            hint: Optional type hint

        Returns:
            The coerced value, or original value if coercion fails
        """
        if hint is None:
            field = self.__fields__.get(key)
            if field and field.hint is not None:
                hint = field.hint
            else:
                return value  # No hint, no coercion
        
        return maybe_coerce(value, hint)
    
    def _check_json_serializable(self, key: str, value: Any) -> None:
        """Check that a value is JSON serializable.

        Args:
            key: The field name (for error messages)
            value: The value to check

        Raises:
            ValueError: If the value is not JSON serializable
        """
        check_json_serializable(
            value,
            key=key,
            allow_nan=bool(getattr(self._config, "allow_inf_nan", True)),
            encoders=getattr(self._config, "json_encoders", None) or {},
        )

    def _check_type(self, key, value, hint):
        return self._check_type_with_message(subject=key, value=value, hint=hint)
            
    def _invalidate_dependants(self, changed_keys: set):
        """Recursively invalidate computed properties that depend on the given keys.

        Handles cascading dependencies automatically in a single method.

        Args:
            changed_keys: Set of keys that have changed (initially the modified key,
                then computed names that got invalidated)
        """
        invalidate_dependants(self, changed_keys)

    def _invalidate_all(self):
        if not getattr(self, "_computed_field_count", 0):
            return
        for value in dict.values(self):
            if isinstance(value, Computed):
                value.invalidate_cache()

    def invalidate_computed(self, *names: str) -> None:
        """Manually invalidate cached computed fields.

        This is useful when you use `deps=[]` (never auto-invalidate) or when
        changes happen outside of `modict`'s assignment hooks.

        Args:
            *names: Names of computed fields to invalidate. If omitted, invalidates all.

        Raises:
            KeyError: If a name doesn't exist in the dict.
            TypeError: If a name exists but is not a computed field.
        """
        if not names:
            self._invalidate_all()
            return

        invalidated: set[str] = set()
        for name in names:
            if name not in self:
                raise KeyError(name)
            raw = dict.__getitem__(self, name)
            if not isinstance(raw, Computed):
                raise TypeError(f"'{name}' is not a computed field")
            raw.invalidate_cache()
            invalidated.add(name)

        # Cascade invalidation for computed fields depending on these names.
        self._invalidate_dependants(invalidated)

    def _auto_convert_value(self, value):
        if not self._config.auto_convert:
            return value
        # Stay data-structure agnostic: convert any mutable container to base modict
        if is_mutable_container(value):
            # Always convert to base modict, not a subclass
            return modict.convert(value, recurse=False)
        return value

    def _auto_convert_and_store(self, key, value):
        new = self._auto_convert_value(value)
        if new is not value:
            # Write raw to avoid re-triggering the full validation pipeline
            self._raw_setitem(key, new)
            return new
        return value

    def _check_mutable(self, action: Literal["assign", "delete", "clear"], key=None) -> None:
        if not self._config.frozen:
            return

        if action == "assign":
            raise TypeError(
                f"Cannot assign to field '{key}': instance is frozen (immutable). "
                f"Set frozen=False in config to allow modifications."
            )
        if action == "delete":
            raise TypeError(
                f"Cannot delete field '{key}': instance is frozen (immutable). "
                f"Set frozen=False in config to allow modifications."
            )
        raise TypeError(
            "Cannot clear instance: it is frozen (immutable). "
            "Set frozen=False in config to allow modifications."
        )

    def _enforce_assignment_policy(self, key, value, *, check_keys_enabled: bool) -> bool:
        # Prevent accidental overwrites of computed fields unless explicitly allowed.
        # This is a key-level constraint, controlled by check_keys.
        if check_keys_enabled:
            existing = dict.get(self, key, MISSING)
            if isinstance(existing, Computed) and not getattr(self._config, "override_computed", False):
                raise TypeError(f"Cannot override computed field '{key}' (override_computed=False)")

        if check_keys_enabled:
            # Handle extra keys based on config
            if key not in self.__fields__:
                if self._config.extra == 'forbid':
                    raise KeyError(
                        f"Key {key!r} is not allowed. Only the following keys are permitted: "
                        f"{list(self.__fields__.keys())}"
                    )
                elif self._config.extra == 'ignore':
                    # Silently ignore: don't store, just return
                    return False
                # extra == 'allow': continue with storage
        return True

    def _store_item(self, key, value, *, validate_value: bool) -> None:
        if self._should_ignore_none_assignment(value):
            return
        self._check_mutable("assign", key=key)
        normalized_key = self._normalize_key(key)
        key = normalized_key

        # Inside a model_validator the full pipeline is suspended: the validator
        # has authority over the instance and is responsible for correctness.
        # Assignments go straight to raw storage + dependant invalidation.
        if getattr(self, "_in_model_validator", 0):
            self._raw_setitem(key, value)
            self._invalidate_dependants({key})
            return

        # Computed objects bypass the normal value-validation pipeline, but still
        # respect override_computed — except when storing the exact same object
        # that is already there (no-op echo from a model_validator snapshot).
        if isinstance(value, Computed):
            existing_raw = dict.get(self, key, MISSING)
            if existing_raw is value:
                return  # Same Computed object — pure no-op, skip everything.
            check_keys_enabled = self._check_keys_enabled()
            if check_keys_enabled and isinstance(existing_raw, Computed) and not getattr(self._config, "override_computed", False):
                raise TypeError(f"Cannot override computed field '{key}' (override_computed=False)")
            self._raw_setitem(key, value)
            self._invalidate_dependants({key})
            return

        check_keys_enabled = self._check_keys_enabled()
        should_store = self._enforce_assignment_policy(key, value, check_keys_enabled=check_keys_enabled)
        if not should_store:
            return

        existing = dict.get(self, key, MISSING)

        # Fast path: if the raw stored value is already the same object or the
        # same concrete value, skip validation/coercion and cache invalidation.
        # Keep this strict enough that `"3"` -> `3` still goes through the
        # pipeline for typed fields.
        if existing is not MISSING and not isinstance(existing, Computed):
            if existing is value:
                return
            if type(existing) is type(value):
                try:
                    if existing == value:
                        return
                except Exception:
                    pass

        if validate_value:
            model_validators = getattr(type(self), "__model_validators__", ())
            if model_validators:
                working = self._clone_for_assignment_validation()
                working._store_item(key, value, validate_value=False)
                working.validate()
                self._replace_instance_state(working)
                return
            value = self._check_value(key, value)
        self._raw_setitem(key, value)
        self._invalidate_dependants({key})

    # changed dict methods

    def keys(self):
        """Return a view of the modict's keys.

        Returns:
            modictKeysView: A view object displaying the modict's keys
        """
        return modictKeysView(self)

    def values(self):
        """Return a view of the modict's values with validation.

        Returns:
            modictValuesView: A view object displaying the modict's values
        """
        return modictValuesView(self)

    def items(self):
        """Return a view of the modict's items with validation.

        Returns:
            modictItemsView: A view object displaying the modict's (key, value) pairs
        """
        return modictItemsView(self)

    def __getitem__(self, key):
        value = dict.__getitem__(self, key)

        if isinstance(value, Computed):
            if not bool(getattr(self._config, "evaluate_computed", True)):
                return value
            computed_value = value(self)
            checked = self._check_value(key, computed_value)
            # Computed values are not cached in the dict — just auto-convert and return.
            return self._auto_convert_value(checked)

        # Stored values: auto-convert and update the dict in-place
        return self._auto_convert_and_store(key, value)

    def __setitem__(self, key, value):
        if isinstance(value, Attribute):
            self._store_attribute(key, value)
            return
        self._store_item(
            key,
            value,
            validate_value=self._check_values_enabled() and self._config.validate_assignment,
        )

    def __delitem__(self, key):
        self._check_mutable("delete", key=key)
        check_keys_enabled = self._check_keys_enabled()
        if check_keys_enabled:
            # Only block deletion for fields whose effective required level is "always".
            fields = getattr(self, "__fields__", {})
            if key in fields:
                require_all = getattr(self._config, "require_all", "never")
                field_required = getattr(fields[key], "required", "never")
                effective = _effective_required(field_required, require_all)
                if effective == "always":
                    raise TypeError(f"Cannot delete declared field '{key}' (effective required='always')")
            existing = dict.get(self, key, MISSING)
            if isinstance(existing, Computed) and not getattr(self._config, "override_computed", False):
                raise TypeError(f"Cannot delete computed field '{key}' (override_computed=False)")
        # Let KeyError propagate naturally if key is missing
        self._raw_delitem(key)
        self._invalidate_dependants({key})

    def __repr__(self):
        parts = []
        for key, raw in dict.items(self):
            value = self[key]
            if isinstance(raw, Computed):
                rendered = f"Computed({value!r})"
            else:
                rendered = repr(value)
            parts.append(f"{key!r}: {rendered}")
        template = f"{{{', '.join(parts)}}}"
        return f"{self.__class__.__name__}({template})"
    
    def __str__(self):
        return repr(self)
        
    def get(self, key, default=None):
        """Get value for key with validation, or return default if key doesn't exist.

        Args:
            key: The key to look up
            default: Value to return if key is not found

        Returns:
            The value for key if key exists, else default
        """
        try:
            return self[key]  # Force validation
        except KeyError:
            return default

    def pop(self, key, default=MISSING):
        """Remove key and return its value with validation.

        Args:
            key: The key to remove
            default: Value to return if key is not found

        Returns:
            The value for key if it exists, else default

        Raises:
            KeyError: If key is not in modict and default is not provided
        """
        try:
            value = self[key]  # Force validation in read
            del self[key]
            return value
        except KeyError:
            if default is not MISSING:
                return default
            raise

    def popitem(self):
        """Remove and return a (key, value) pair with validation.

        Returns:
            Tuple[Any, Any]: A (key, value) pair from the modict

        Raises:
            KeyError: If the modict is empty
        """
        if not self:
            raise KeyError('popitem(): dictionary is empty')
        key = next(reversed(list(dict.keys(self))))
        return key, self.pop(key)

    def update(self, other=(), /, **kwargs):
        """Update the modict, routing all assignments through the validation pipeline.

        Overrides dict.update() which would bypass __setitem__ in CPython.
        Matches the native dict.update() signature (positional-only first arg).
        """
        validate_value = self._check_values_enabled() and self._config.validate_assignment
        store_item = self._store_item
        store_attribute = self._store_attribute

        if hasattr(other, 'items'):
            for key, value in other.items():
                if isinstance(value, Attribute):
                    store_attribute(key, value)
                else:
                    store_item(key, value, validate_value=validate_value)
        else:
            for key, value in other:
                if isinstance(value, Attribute):
                    store_attribute(key, value)
                else:
                    store_item(key, value, validate_value=validate_value)
        for key, value in kwargs.items():
            if isinstance(value, Attribute):
                store_attribute(key, value)
            else:
                store_item(key, value, validate_value=validate_value)

    @classmethod
    def _new_empty_like(cls, *, config=None):
        """Allocate an instance without running __init__."""
        new = dict.__new__(cls)
        source_config = config if config is not None else type(new)._config
        object.__setattr__(new, "_config", source_config.copy())
        object.__setattr__(new, "_computed_field_count", 0)
        return new

    def copy(self):
        """Create a shallow copy with validation.

        Returns:
            modict: A new modict with the same items
        """
        new = type(self)._new_empty_like(config=self._config)
        for key, value in self.__dict__.items():
            if key in {"_config", "_computed_field_count"}:
                continue
            object.__setattr__(new, key, value)
        for key, value in dict.items(self):
            cloned = value.copy() if isinstance(value, Computed) else value
            new._raw_setitem(key, cloned)
        return new

    def __copy__(self):
        return self.copy()

    @classmethod
    def fromkeys(cls, iterable, value=None):
        """Create a modict from keys with validation.

        Args:
            iterable: An iterable of keys
            value: The value to set for all keys

        Returns:
            modict: A new modict with keys from iterable, all set to value
        """
        return cls((key, value) for key in iterable)

    def __or__(self, other):
        """Merge operator (d1 | d2) with validation.

        Args:
            other: A Mapping to merge with this modict

        Returns:
            modict: A new modict with merged items

        Raises:
            TypeError: If other is not a Mapping
        """
        if not isinstance(other, Mapping):
            return NotImplemented
        result = self.copy()
        was_frozen = bool(getattr(result._config, "frozen", False))
        if was_frozen:
            result._config.frozen = False
        try:
            result.update(other)
        finally:
            result._config.frozen = was_frozen
        return result

    def __ior__(self, other):
        """In-place merge operator (d1 |= d2) with validation.

        Args:
            other: A Mapping to merge into this modict

        Returns:
            modict: This modict, updated with items from other

        Raises:
            TypeError: If other is not a Mapping
        """
        if not isinstance(other, Mapping):
            return NotImplemented
        self.update(other)
        return self

    def __reversed__(self):
        """Support for reversed(d).

        Returns:
            Iterator: An iterator over keys in reverse order
        """
        return reversed(list(self.keys()))

    def setdefault(self, key, default=None):
        """Get value for key, setting it to default if key doesn't exist.

        Args:
            key: The key to look up or set
            default: Value to set and return if key doesn't exist

        Returns:
            The value for key if it exists, else default
        """
        if key in self:
            return self[key]
        else:
            if self._should_ignore_none_assignment(default):
                return default
            self[key] = default
            return self[key]

    def clear(self):
        self._check_mutable("clear")
        check_keys_enabled = self._check_keys_enabled()
        if check_keys_enabled and getattr(self, "__fields__", None):
            require_all = getattr(self._config, "require_all", "never")
            fields = self.__fields__
            has_always_field = any(
                _effective_required(getattr(f, "required", "never"), require_all) == "always"
                for f in fields.values()
            )
            if has_always_field:
                raise TypeError("Cannot clear a model with fields that have effective required='always'")
        if (
            check_keys_enabled
            and not getattr(self._config, "override_computed", False)
            and getattr(self, "_computed_field_count", 0)
        ):
            raise TypeError("Cannot clear computed fields (override_computed=False)")
        self._raw_clear()
        self._invalidate_all()

    # additonal methods

    def __getattr__(self, key):
        """Allow attribute-style access to dictionary keys.

        Args:
            key: The attribute name to access

        Returns:
            The value associated with the key

        Raises:
            AttributeError: If the attribute/key doesn't exist
        """
        if hasattr(type(self), key):
            return super().__getattribute__(key)
        elif key in self:
            return self[key]
        else:
            return super().__getattribute__(key)

    def get_attr(self, key: str, default: Any = MISSING) -> Any:
        """Return plain metadata stored outside of the mapping payload.

        This only reads runtime/class metadata managed via ``set_attr()`` or
        ``modict.attr(...)``. Mapping keys are intentionally ignored.
        """
        if key in self.__dict__:
            return self.__dict__[key]
        class_attributes = getattr(type(self), "__attributes__", {})
        if key in class_attributes:
            return class_attributes[key]
        if default is not MISSING:
            return default
        raise AttributeError(f"'{type(self).__name__}' object has no metadata attribute '{key}'")

    def has_attr(self, key: str) -> bool:
        """Return True if a plain attribute metadata entry exists.

        This checks both instance-level attributes set via ``set_attr()`` /
        ``modict.attr(...)`` and inherited class-level attributes declared with
        ``modict.attr(...)``.
        """
        if key in self.__dict__:
            return True
        return key in getattr(type(self), "__attributes__", {})

    def set_attr(self, key: str, value: Any) -> None:
        """Store plain metadata outside of the mapping payload."""
        self._store_attribute(key, Attribute(value))

    def del_attr(self, key: str) -> None:
        """Delete an instance-level metadata override when present.

        If the name also exists as inherited class metadata, deleting the
        override simply falls back to the inherited value instead of raising.
        """
        if key in self.__dict__:
            object.__delattr__(self, key)
            return
        if key in getattr(type(self), "__attributes__", {}):
            return
        raise AttributeError(f"'{type(self).__name__}' object has no metadata attribute '{key}'")

    def __setattr__(self, key, value):
        """Allow attribute-style setting of dictionary keys.

        New keys are routed to dictionary storage. Existing class attributes are
        protected from instance-level shadowing; use item assignment explicitly
        if you want a key with the same name.

        Args:
            key: The attribute/key name
            value: The value to set
        """
        if isinstance(value, Attribute):
            self._store_attribute(key, value)
            return
        if hasattr(type(self), key):
            raise AttributeError(
                f"Cannot assign attribute '{key}': '{type(self).__name__}.{key}' already exists. "
                f"Use item assignment instead: obj[{key!r}] = value"
            )
        else:
            # New key → dict behavior
            self[key] = value

    def __delattr__(self, key):
        """Allow attribute-style deletion of dictionary keys.

        Args:
            key: The attribute/key name to delete

        Raises:
            AttributeError: If the attribute/key doesn't exist
        """
        if hasattr(type(self), key):
            object.__delattr__(self, key)
        elif key in self.__dict__:
            object.__delattr__(self, key)
        elif key in self:
            del self[key]
        else:
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{key}'")

    @classmethod
    def convert(
        cls,
        obj: Any,
        seen: Optional[Dict] = None,
        root: bool = True,
        *,
        recurse: bool = True,
    ) -> 'modict':
        """Convert dicts to modicts recursively.

        Takes any object as input and converts nested dictionaries to modicts.
        Handles circular references gracefully.

        Args:
            obj: The object to convert
            seen: Internal dict for tracking circular references (used in recursion)
            root: Whether this is the root call (affects which class is used)
            recurse: If False, stop recursion when reaching a modict node
                (either an existing modict or a dict that gets converted to a modict).
                This is useful for lazy auto-conversion: nested modicts will convert
                their own children upon access.

        Returns:
            The converted object:
                - If obj is a dict: upgraded to modict with nested conversion
                - If obj is a MutableMapping or MutableSequence: items are converted
                - Otherwise: returns obj directly

        Examples:
            >>> data = {'a': {'b': 1}, 'c': [{'d': 2}]}
            >>> m = modict.convert(data)
            >>> isinstance(m.a, modict)
            True
            >>> isinstance(m.c[0], modict)
            True
        """
        if seen is None:
            seen = {}  # Map object id -> converted value

        obj_id = id(obj)
        if obj_id in seen:
            return seen[obj_id]

        # if dict we upgrade to modict first
        if isinstance(obj, dict) and not isinstance(obj, modict):
            if root:
                obj = cls(obj)
            else:
                obj = modict(obj)

        # Register the new instance as output for an already seen input
        seen[obj_id] = obj

        # If recursion is disabled, stop at modict nodes (existing or newly converted)
        if not recurse and isinstance(obj, modict):
            return obj

        # then we recursively convert the values
        if is_mutable_container(obj):
            # We convert in situ to preserve references of original containers as much as possible
            if isinstance(obj, modict):
                # Use raw dict iteration to avoid re-entering __getitem__ during conversion.
                items = dict.items(obj)
            else:
                items = unroll(obj)
            for k, v in items:
                if isinstance(obj, modict):
                    obj._raw_setitem(k, cls.convert(v, seen, root=False, recurse=recurse))
                else:
                    obj[k] = cls.convert(v, seen, root=False, recurse=recurse)

        return obj

    def to_modict(self):
        """Convert this instance and all nested dicts to modicts in-place.

        Returns:
            modict: This modict instance with all nested dicts converted
        """
        return self.__class__.convert(self)

    @classmethod
    def unconvert(cls, obj: Any, seen: Optional[Dict] = None) -> dict:
        """Convert modicts to dicts recursively.

        Takes any object as input and converts nested modicts to plain dicts.
        Handles circular references gracefully.

        Args:
            obj: The object to unconvert
            seen: Internal dict for tracking circular references (used in recursion)

        Returns:
            The unconverted object:
                - If obj is a modict: downgraded to dict with nested unconversion
                - If obj is a MutableMapping or MutableSequence: items are unconverted
                - Otherwise: returns obj directly

        Examples:
            >>> m = modict(a=modict(b=1), c=[modict(d=2)])
            >>> data = modict.unconvert(m)
            >>> isinstance(data, dict) and not isinstance(data, modict)
            True
            >>> isinstance(data['a'], dict) and not isinstance(data['a'], modict)
            True
        """
        if seen is None:
            seen = {}  # Map object id -> unconverted value

        obj_id = id(obj)
        if obj_id in seen:
            return seen[obj_id]

        # if modict : we downgrade to dict first
        if isinstance(obj, modict):
            obj = dict(obj)

        seen[obj_id] = obj

        if is_mutable_container(obj):
            # We unconvert in situ to preserve references of original containers as much as possible
            if isinstance(obj, modict):
                # Read raw stored values so unconversion does not evaluate computed or auto-convert again.
                items = dict.items(obj)
            else:
                items = unroll(obj)
            for k, v in items:
                obj[k] = cls.unconvert(v, seen)

        return obj

    def to_dict(self):
        """Convert this modict and all nested modicts to plain dicts in-place.

        Returns:
            dict: A plain dict with all nested modicts converted
        """
        return self.__class__.unconvert(self)

    def get_nested(self, path: str | tuple | Path, default=MISSING):
        """Retrieve a nested value using a path.

        Supports multiple path formats:
        - JSONPath string (RFC 9535): "$.a[0].b"
        - Tuple of keys: ("a", 0, "b")
        - Path object: Path.from_jsonpath("$.a[0].b")

        Args:
            path: JSONPath string, tuple of keys, or Path object
            default: Value to return if path doesn't exist (default: MISSING)

        Returns:
            Value at path or default if provided

        Raises:
            KeyError: If path doesn't exist and no default provided

        Examples:
            >>> m = modict(a=modict(b=[1, 2, modict(c=3)]))
            >>> m.get_nested("$.a.b[2].c")  # JSONPath
            3
            >>> m.get_nested(("a", "b", 2, "c"))  # tuple
            3
            >>> m.get_nested("$.x.y.z", default=None)
            None
        """
        return get_nested(self,path,default=default)

    def set_nested(
        self,
        path: str | tuple | Path,
        value,
        *,
        create_missing: bool = False,
        container_factory=None,
    ):
        """Set a nested value.

        By default, all intermediate containers along the path must already
        exist. If `create_missing=True`, missing intermediate containers are
        created using `container_factory(path)`.

        Supports multiple path formats:
        - JSONPath string (RFC 9535): "$.a[0].b"
        - Tuple of keys: ("a", 0, "b")
        - Path object: Path.from_jsonpath("$.a[0].b")

        Args:
            path: JSONPath string, tuple of keys, or Path object
            value: Value to set
            create_missing: Whether to create missing intermediate containers
            container_factory: Factory called as `factory(path)` for each
                missing intermediate container when `create_missing=True`

        Raises:
            TypeError: If any container in the path is immutable

        Examples:
            >>> m = modict({"a": {"b": [{"c": 0}]}})
            >>> m.set_nested("$.a.b[0].c", 42)
            >>> m
            modict({'a': {'b': [{'c': 42}]}})
        """
        set_nested(
            self,
            path,
            value,
            create_missing=create_missing,
            container_factory=container_factory,
        )
            
    def del_nested(self, path: str | tuple | Path):
        """Delete a nested key/index.

        Supports multiple path formats:
        - JSONPath string (RFC 9535): "$.a[0].b"
        - Tuple of keys: ("a", 0, "b")
        - Path object: Path.from_jsonpath("$.a[0].b")

        Args:
            path: JSONPath string, tuple of keys, or Path object

        Raises:
            TypeError: If attempting to modify an immutable container in the path
            KeyError: If path doesn't exist

        Examples:
            >>> m = modict(a=modict(b=[1, 2, modict(c=3)]))
            >>> m.del_nested("$.a.b[2].c")  # JSONPath
            >>> m
            modict({'a': {'b': [1, 2, {}]}})
        """
        del_nested(self,path)

    def pop_nested(self, path: str | tuple | Path, default=MISSING):
        """Delete a nested key/index and return its value.

        If not found, returns default if provided, otherwise raises an error.
        If provided, default will be returned in ANY case of failure, including:
        - The path doesn't exist or doesn't make sense in the structure
        - The path exists but ends in an immutable container

        Supports multiple path formats:
        - JSONPath string (RFC 9535): "$.a[0].b"
        - Tuple of keys: ("a", 0, "b")
        - Path object: Path.from_jsonpath("$.a[0].b")

        Args:
            path: JSONPath string, tuple of keys, or Path object
            default: Value to return if operation fails (default: MISSING)

        Returns:
            The value that was deleted, or default if operation failed and default provided

        Raises:
            TypeError: If attempting to modify an immutable container and no default provided
            KeyError: If path doesn't exist and no default provided

        Examples:
            >>> m = modict(a=modict(b=[1, 2, modict(c=3)]))
            >>> m.pop_nested("$.a.b[2].c")  # JSONPath
            3
            >>> m.pop_nested("$.x.y.z", default=None)
            None
        """
        return pop_nested(self,path,default=default)

    def has_nested(self, path: str | tuple | Path):
        """Check if a nested path exists.

        Supports multiple path formats:
        - JSONPath string (RFC 9535): "$.a[0].b"
        - Tuple of keys: ("a", 0, "b")
        - Path object: Path.from_jsonpath("$.a[0].b")

        Args:
            path: JSONPath string, tuple of keys, or Path object

        Returns:
            True if path exists, False otherwise

        Examples:
            >>> m = modict(a=modict(b=[1, 2, modict(c=3)]))
            >>> m.has_nested("$.a.b[2].c")  # JSONPath
            True
            >>> m.has_nested("$.a.b[5].d")
            False
        """
        return has_nested(self,path)

    def translate(self, *args, **kwargs):
        """Return a plain modict with translated keys (order is preserved).

        Uses an internal mapping created by dict(*args, **kwargs) where
        the keys represent the old keys and the values represent the new keys.
        Keys not present in the mapping remain unchanged.

        Args:
            *args: Positional arguments passed to dict() to create the mapping
            **kwargs: Keyword arguments passed to dict() to create the mapping

        Returns:
            A new base `modict` instance containing the translated keys.

        Note:
            If two different keys are translated to the same new key,
            the last one encountered will overwrite the previous one.
            Raw stored values are preserved: Computed placeholders are copied,
            not evaluated.

        Examples:
            >>> m = modict(a=1, b=2, c=3)
            >>> translated = m.translate(a='x', b='y')
            >>> translated
            modict({'x': 1, 'y': 2, 'c': 3})
            >>> translated = translated.translate({'x': 'alpha', 'y': 'beta'})
            >>> translated
            modict({'alpha': 1, 'beta': 2, 'c': 3})
        """
        mapping = dict(*args, **kwargs)
        translated = modict._new_empty_like()
        for key, value in dict.items(self):
            raw = value.copy() if isinstance(value, Computed) else value
            translated._raw_setitem(mapping.get(key, key), raw)
        return translated
        
    def exclude(self, *excluded_keys):
        """Exclude specified keys from the modict, preserving the original order.

        Args:
            *excluded_keys: Keys to exclude from the result

        Returns:
            A new modict containing all keys except the excluded ones

        Examples:
            >>> m = modict(a=1, b=2, c=3, d=4)
            >>> m.exclude('b', 'd')
            modict({'a': 1, 'c': 3})
        """
        return modict(exclude(self, *excluded_keys))

    def extract(self, *extracted_keys):
        """Extract specified keys from the modict, preserving the original order.

        Args:
            *extracted_keys: Keys to extract from the modict

        Returns:
            A new modict containing only the extracted keys

        Examples:
            >>> m = modict(a=1, b=2, c=3, d=4)
            >>> m.extract('a', 'c')
            modict({'a': 1, 'c': 3})
        """
        return modict(extract(self, *extracted_keys)) 

    def _resolve_query(self, query, path_constraint, value_constraint):
        from ...collections_utils import Query
        if query is not MISSING:
            if path_constraint is not MISSING or value_constraint is not MISSING:
                raise TypeError("Cannot combine 'query' with 'path_constraint' or 'value_constraint'")
            return query
        return Query(
            path=path_constraint,
            value=value_constraint,
        )

    def find(self, query=MISSING, *, path_constraint=MISSING, value_constraint=MISSING):
        """Lazily yield (Path, value) pairs in this modict that match the given query.

        Args:
            query: a Query instance
            path_constraint: path argument passed to Query(path=...) — alternative to passing a Query
            value_constraint: value argument passed to Query(value=...) — alternative to passing a Query

        Returns:
            A generator of (Path, value) pairs

        Examples:
            >>> from modict import Query
            >>> m = modict(users=[{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}])
            >>> list(m.find(Query("$.users[*].age", lambda v: v > 28)))
            [(Path($.users[0].age), 30)]
            >>> list(m.find(path_constraint="$.users[*].age", value_constraint=lambda v: v > 28))
            [(Path($.users[0].age), 30)]
        """
        q = self._resolve_query(query, path_constraint, value_constraint)
        return (pair for pair in q.find(self))

    def found(self, query=MISSING, *, path_constraint=MISSING, value_constraint=MISSING):
        """Return all matches as a {Path: value} modict.

        Args:
            query: a Query instance
            path_constraint: path argument passed to Query(path=...) — alternative to passing a Query
            value_constraint: value argument passed to Query(value=...) — alternative to passing a Query

        Returns:
            A plain modict mapping each matching Path to its value

        Examples:
            >>> from modict import Query
            >>> m = modict(users=[{"name": "Alice"}, {"name": "Bob"}])
            >>> m.found(Query("$.users[*].name", "Alice"))
            modict({Path($.users[0].name): 'Alice'})
            >>> m.found(value_constraint="Alice")
            modict({Path($.users[0].name): 'Alice'})
        """
        return modict(self.find(query, path_constraint=path_constraint, value_constraint=value_constraint))

    def walk(self, callback=None, filter=None, excluded=None):
        """Walk through the nested modict yielding (Path, value) pairs.

        Recursively traverses the modict, yielding Path objects and values for leaf nodes.
        Leaves can be transformed by callback and filtered by the filter predicate.

        Note: This method now returns Path objects (not strings) for better disambiguation
        of integer keys vs. sequence indices. Use str(path) or path.to_jsonpath() to get
        the JSONPath string representation.

        Args:
            callback: Optional function to transform leaf values
            filter: Optional predicate to filter paths/values (receives Path and value)
            excluded: Container types to treat as leaves (default: str, bytes, bytearray)

        Yields:
            Tuples of (Path, value) for each leaf node
            If callback provided, value is transformed by callback
            If filter provided, only yields pairs that pass filter(path, value)

        Examples:
            >>> m = modict(a=[1, modict(b=2)], c=3)
            >>> for path, value in m.walk():
            ...     print(f"{path}: {value}")
            $.a[0]: 1
            $.a[1].b: 2
            $.c: 3

            >>> list(m.walk(callback=str))
            [(Path($.a[0]), '1'), (Path($.a[1].b), '2'), (Path($.c), '3')]
        """
        yield from walk(self,callback=callback,filter=filter,excluded=excluded)

    def walked(self, callback=None, filter=None):
        """Return a flattened modict of path:value pairs from the nested structure.

        Similar to walk(), but returns a modict instead of an iterator.

        Note: Keys are Path objects (not strings). Use str(path) to get the JSONPath
        string representation if needed.

        Args:
            callback: Optional function to transform leaf values
            filter: Optional predicate to filter paths/values (receives Path and value)

        Returns:
            A modict mapping Path objects to leaf values

        Examples:
            >>> m = modict(a=[1, modict(b=2)], c=3)
            >>> walked = m.walked()
            >>> for path, value in walked.items():
            ...     print(f"{path}: {value}")
            $.a[0]: 1
            $.a[1].b: 2
            $.c: 3

            >>> m.walked(callback=lambda x: x * 2)
            modict({Path($.a[0]): 2, Path($.a[1].b): 4, Path($.c): 6})
        """
        return modict(self.walk(callback=callback,filter=filter))

    @classmethod
    def unwalk(cls, walked, ignore_types: bool = False, *, kind_resolver=None):
        """Reconstruct a nested structure from a flattened dict.

        Args:
            walked: A path:value flattened dictionary (e.g., {'a.0.b': 1, 'a.1.c': 2})
            ignore_types: Legacy compatibility flag. If True, ignore Path-provided
                Mapping/Sequence hints and rely only on key-shape heuristics during
                structural reconstruction.
            kind_resolver: Optional hook called as ``kind_resolver(path, inferred_kind)``
                for every reconstructed container path. It may refine the inferred
                structure by returning either ``"mapping"`` or ``"sequence"``.

        Returns:
            Reconstructed nested structure. The structural rebuild uses plain
            dict/list containers; if the root is a mapping, it is then recast
            through `cls(...)` so the target model can re-apply validation and
            coercion.

        Examples:
            >>> walked_data = modict({'a.0': 1, 'a.1.b': 2, 'c': 3})
            >>> modict.unwalk(walked_data)
            modict({'a': [1, {'b': 2}], 'c': 3})

            >>> # With ignore_types=True, ignore Path hints during structural rebuild
            >>> modict.unwalk(walked_data, ignore_types=True)
            modict({'a': [1, {'b': 2}], 'c': 3})
        """
        unwalked = unwalk(walked, ignore_types=ignore_types, kind_resolver=kind_resolver)

        # Only convert to cls if:
        # 1. It's a Mapping AND
        # 2. It's a plain dict OR it's a modict but not the right subclass
        if isinstance(unwalked, Mapping):
            # Plain dict → convert to cls
            if type(unwalked) is dict:
                return cls(unwalked)
            # modict instance but wrong subclass → convert to cls
            elif isinstance(unwalked, modict) and not isinstance(unwalked, cls):
                return cls(unwalked)
            # Otherwise (OrderedDict, UserDict, correct modict subclass, etc.) → keep as-is
            else:
                return unwalked

        # Not a Mapping (e.g., list) → return as-is
        return unwalked

    def merge(self, other: Mapping):
        """Deeply merge another mapping into this modict, modifying it in-place.

        For mappings:
        - If a key exists in both and both values are containers, merge recursively
        - Otherwise, other's value overwrites this modict's value
        - If other's value is MISSING, the key is removed from this modict

        For sequences:
        - Elements are merged by index
        - If other has more elements, they are appended
        - If an element's value is MISSING, it is removed from the sequence

        Args:
            other: Mapping to merge from

        Raises:
            TypeError: If attempting to merge incompatible container types

        Examples:
            >>> m = modict(a=1, b=modict(x=1), d=4)
            >>> m.merge({'b': {'y': 2}, 'c': 3, 'd': MISSING})
            >>> m
            modict({'a': 1, 'b': {'x': 1, 'y': 2}, 'c': 3})

            >>> # Recursive deletion with MISSING
            >>> m = modict(a=modict(b=modict(c=1, d=2), e=3))
            >>> m.merge({'a': {'b': {'c': MISSING}}})
            >>> m
            modict({'a': {'b': {'d': 2}, 'e': 3}})
        """
        deep_merge(self,other)

    def diff(self, other: Mapping):
        """Compare this modict with another mapping and return their differences.

        Recursively compares two structures and returns a dictionary of differences.
        Keys are paths where values differ, values are tuples of (self_value, other_value).

        Args:
            other: Mapping to compare with

        Returns:
            Dictionary mapping paths to value pairs that differ
            MISSING is used when a key exists in one container but not the other

        Examples:
            >>> m1 = modict(x=1, y=modict(z=2))
            >>> m2 = modict(x=1, y=modict(z=3), w=4)
            >>> m1.diff(m2)
            {'y.z': (2, 3), 'w': (MISSING, 4)}
        """
        return diff_nested(self,other)

    def diffed(self, other: Mapping):
        """Return a new modict containing only the differences with another mapping.

        Recursively compares two structures and returns an unwalked nested modict with only
        the differing entries needed to transform this modict into the other.
        Meant to be used in conjunction with merge() so that self.merge(self.diffed(other))
        results in a structure equal to other.

        Args:
            other: Mapping to compare with

        Returns:
            modict: A new modict with only the differing keys and their values from other.
                Keys that exist in self but not in other are set to MISSING to indicate removal.

        Examples:
            >>> m1 = modict(x=1, y=modict(z=2, t=5), w=4)
            >>> m2 = modict(x=2, y=modict(z=3, t=5), u=6)
            >>> diff = m1.diffed(m2)
            >>> diff
            modict({'x': 2, 'y': {'z': 3}, 'w': MISSING, 'u': 6})
            >>> m1.merge(diff)
            >>> m1.deep_equals(m2)
            True
        """
        # Get the differences as a dict of Path: (self_value, other_value)
        diffs = self.diff(other)

        # Transform to Path: other_value (or MISSING if only in self)
        result = {}
        for path, (self_value, other_value) in diffs.items():
            result[path] = other_value

        # Use ignore_types=True to avoid reconstructing modict with defaults
        return modict(unwalk(result, ignore_types=True))

    def deep_equals(self, other: Mapping):
        """Compare two nested structures deeply for equality.

        Compares by walking through both structures and comparing their flattened
        representations.

        Args:
            other: Mapping to compare with

        Returns:
            True if structures are deeply equal, False otherwise

        Examples:
            >>> m1 = modict(a=[1, modict(b=2)])
            >>> m2 = {'a': [1, {'b': 2}]}
            >>> m1.deep_equals(m2)
            True
            >>> m3 = modict(a=[1, modict(b=3)])
            >>> m1.deep_equals(m3)
            False
        """
        return deep_equals(self,other)

    def deepcopy(self) -> "modict":
        """Create a deep copy of this modict.

        Returns:
            modict: A new modict with deep copies of all nested values

        Examples:
            >>> m = modict(a=modict(b=[1, 2, 3]))
            >>> m2 = m.deepcopy()
            >>> m2.a.b.append(4)
            >>> m.a.b
            [1, 2, 3]
            >>> m2.a.b
            [1, 2, 3, 4]
        """
        return copy.deepcopy(self)

    def __deepcopy__(self, memo):
        existing = memo.get(id(self))
        if existing is not None:
            return existing
        new = type(self)._new_empty_like(config=self._config)
        memo[id(self)] = new
        for key, value in self.__dict__.items():
            if key in {"_config", "_computed_field_count"}:
                continue
            object.__setattr__(new, key, copy.deepcopy(value, memo))
        for key, value in dict.items(self):
            cloned = value.copy() if isinstance(value, Computed) else copy.deepcopy(value, memo)
            new._raw_setitem(key, cloned)
        return new
    
    # JSON support
    
    @classmethod
    def loads(cls, s, *, cls_param=None, object_hook=None, parse_float=None,
              parse_int=None, parse_constant=None, object_pairs_hook=None, **kw):
        """Return a modict instance from a JSON string.
        
        This method has the same signature and behavior as json.loads(),
        but returns a modict instance instead of a plain dict.
        
        Args:
            s: JSON string to deserialize
            cls_param: Custom decoder class (usually None)
            object_hook: Function to call with result of every JSON object decoded
            parse_float: Function to call with string of every JSON float to be decoded
            parse_int: Function to call with string of every JSON int to be decoded  
            parse_constant: Function to call with one of: -Infinity, Infinity, NaN
            object_pairs_hook: Function to call with result of every JSON object 
                             decoded with an ordered list of pairs
            **kw: Additional keyword arguments passed to json.loads()
            
        Returns:
            modict: An modict instance containing the parsed JSON data
            
        Raises:
            JSONDecodeError: If the JSON string is invalid
            
        Examples:
            >>> config = AppConfig.loads('{"api_url": "https://api.com", "timeout": 30}')
            >>> config.api_url
            'https://api.com'
        """
        try:
            data = json.loads(s, cls=cls_param, object_hook=object_hook, 
                            parse_float=parse_float, parse_int=parse_int,
                            parse_constant=parse_constant, 
                            object_pairs_hook=object_pairs_hook, **kw)
            return cls(data)
        except json.JSONDecodeError as e:
            raise json.JSONDecodeError(
                f"Failed to parse JSON for {cls.__name__}: {e.msg}",
                e.doc, e.pos
            ) from e
    
    @classmethod 
    def load(cls, fp, *, cls_param=None, object_hook=None, parse_float=None,
             parse_int=None, parse_constant=None, object_pairs_hook=None, **kw):
        """Return a modict instance from a JSON file.
        
        This method has the same signature and behavior as json.load(),
        but returns a modict instance instead of a plain dict.
        
        Args:
            fp: File-like object containing JSON document, or path-like object
            cls_param: Custom decoder class (usually None)
            object_hook: Function to call with result of every JSON object decoded
            parse_float: Function to call with string of every JSON float to be decoded
            parse_int: Function to call with string of every JSON int to be decoded
            parse_constant: Function to call with one of: -Infinity, Infinity, NaN
            object_pairs_hook: Function to call with result of every JSON object
                             decoded with an ordered list of pairs  
            **kw: Additional keyword arguments passed to json.load()
            
        Returns:
            modict: An modict instance containing the parsed JSON data
            
        Raises:
            JSONDecodeError: If the JSON is invalid
            FileNotFoundError: If the file doesn't exist
            
        Examples:
            >>> config = AppConfig.load("config.json")
            >>> config = AppConfig.load(open("config.json"))
        """
        # Support path-like objects
        if hasattr(fp, 'read'):
            # File-like object
            try:
                data = json.load(fp, cls=cls_param, object_hook=object_hook,
                               parse_float=parse_float, parse_int=parse_int,
                               parse_constant=parse_constant,
                               object_pairs_hook=object_pairs_hook, **kw)
                return cls(data)
            except json.JSONDecodeError as e:
                raise json.JSONDecodeError(
                    f"Failed to parse JSON for {cls.__name__}: {e.msg}",
                    e.doc, e.pos
                ) from e
        else:
            # Path-like object
            with open(fp, 'r') as f:
                return cls.load(f, cls_param=cls_param, object_hook=object_hook,
                              parse_float=parse_float, parse_int=parse_int,
                              parse_constant=parse_constant,
                              object_pairs_hook=object_pairs_hook, **kw)

    def dumps(self, *, skipkeys=False, ensure_ascii=True, check_circular=True,
              allow_nan=True, cls=None, indent=None, separators=None,
              default=None, sort_keys=False,
              exclude_none: bool = False, encoders: Optional[Dict[Type, Callable[[Any], Any]]] = None, **kw):
        """Return a JSON string representation of the modict.

        This method has the same signature and behavior as json.dumps().

        Args:
            skipkeys: If True, dict keys that are not basic types will be skipped
            ensure_ascii: If True, non-ASCII characters are escaped
            check_circular: If False, circular reference check is skipped
            allow_nan: If False, ValueError raised for NaN/Infinity values
            cls: Custom encoder class
            indent: Number of spaces for indentation (None for compact)
            separators: (item_separator, key_separator) tuple
            default: Function called for objects that aren't serializable
            sort_keys: If True, output of dictionaries sorted by key
            exclude_none: If True, drop keys with value None
            encoders: Optional mapping of types to encoder callables
            **kw: Additional keyword arguments

        Returns:
            str: JSON string representation

        Raises:
            TypeError: If the object is not JSON serializable
            ValueError: If allow_nan=False and NaN/Infinity encountered

        Examples:
            >>> config.dumps()
            '{"api_url": "https://api.com", "timeout": 30}'
            >>> config.dumps(indent=2, sort_keys=True)
            # Pretty-printed JSON
        """
        effective_encoders = encoders if encoders is not None else (self._config.json_encoders or {})
        payload = to_jsonable(self, exclude_none=exclude_none, encoders=effective_encoders)
        return json.dumps(
            payload,
            skipkeys=skipkeys,
            ensure_ascii=ensure_ascii,
            check_circular=check_circular,
            allow_nan=allow_nan,
            cls=cls,
            indent=indent,
            separators=separators,
            default=default,
            sort_keys=sort_keys,
            **kw,
        )
    
    def dump(self, fp, *, skipkeys=False, ensure_ascii=True, check_circular=True,
             allow_nan=True, cls=None, indent=None, separators=None,
             default=None, sort_keys=False,
             exclude_none: bool = False, encoders: Optional[Dict[Type, Callable[[Any], Any]]] = None, **kw):
        """Write the modict as JSON to a file.

        This method has the same signature and behavior as json.dump().

        Args:
            fp: File-like object to write to, or path-like object
            skipkeys: If True, dict keys that are not basic types will be skipped
            ensure_ascii: If True, non-ASCII characters are escaped
            check_circular: If False, circular reference check is skipped
            allow_nan: If False, ValueError raised for NaN/Infinity values
            cls: Custom encoder class
            indent: Number of spaces for indentation (None for compact)
            separators: (item_separator, key_separator) tuple
            default: Function called for objects that aren't serializable
            sort_keys: If True, output of dictionaries sorted by key
            exclude_none: If True, drop keys with value None
            encoders: Optional mapping of types to encoder callables
            **kw: Additional keyword arguments

        Raises:
            TypeError: If the object is not JSON serializable
            ValueError: If allow_nan=False and NaN/Infinity encountered

        Examples:
            >>> config.dump("config.json")
            >>> config.dump(open("config.json", "w"), indent=2)
        """
        # Support path-like objects
        if hasattr(fp, 'write'):
            # File-like object
            effective_encoders = encoders if encoders is not None else (self._config.json_encoders or {})
            payload = to_jsonable(self, exclude_none=exclude_none, encoders=effective_encoders)
            json.dump(
                payload,
                fp,
                skipkeys=skipkeys,
                ensure_ascii=ensure_ascii,
                check_circular=check_circular,
                allow_nan=allow_nan,
                cls=cls,
                indent=indent,
                separators=separators,
                default=default,
                sort_keys=sort_keys,
                **kw,
            )
        else:
            # Path-like object
            with open(fp, 'w') as f:
                self.dump(f, skipkeys=skipkeys, ensure_ascii=ensure_ascii,
                         check_circular=check_circular, allow_nan=allow_nan,
                         cls=cls, indent=indent, separators=separators,
                         default=default, sort_keys=sort_keys,
                         exclude_none=exclude_none, encoders=encoders, **kw)
