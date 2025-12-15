from collections.abc import ValuesView, ItemsView, KeysView
from typing import Optional, Union, Tuple, Set, Dict, List, Any, Type, Callable, Literal
from types import FunctionType
from ._collections_utils import MISSING
from dataclasses import dataclass, field, fields, MISSING as DC_MISSING
from typing import FrozenSet
import warnings
import inspect


@dataclass
class modictConfig:
    """Configuration for modict instances.

    Follows Pydantic's ConfigDict semantics for consistency and familiarity.

    Attributes:
       check_values: Controls whether modict enforces its validation/processing pipeline:
           - 'auto' (default): enable when the class looks "model-like" (has hints/validators/config constraints)
           - True: always enable the pipeline
           - False: bypass validation entirely (dict-like behavior)

       # modict-specific fields
       auto_convert: If True, automatically convert dicts found in nested mutable containers
                     (MutableMapping or MutableSequence) to modicts (on first access).
       override_computed: If True, allow overriding/deleting computed fields at runtime
                         and allow providing initial values for computed fields.
       require_all: If True, require presence of all declared (non-computed) class fields
                    at initialization time (annotation-only fields become required).
       check_keys: Controls whether modict enforces key-level structural constraints:
           - 'auto' (default): enabled when the model declares key constraints (extra/require_all/required/computed)
           - True: always enforce key-level constraints
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
       validate_assignment: If True, validate values on assignment (Pydantic semantics).
       validate_default: If True, validate default values at class definition time.
       str_strip_whitespace: If True, strip whitespace from string values.
       str_to_lower: If True, convert string values to lowercase.
       str_to_upper: If True, convert string values to uppercase.
       use_enum_values: If True, extract .value from Enum instances automatically.
       allow_inf_nan: If False, disallow NaN/Infinity when enforce_json=True.
       from_attributes: If True, allow building a modict from an object with attributes.
       alias_generator: Optional callable (field_name -> alias string) applied at class creation.
       json_encoders: Optional mapping of types to encoder callables used by model_dump_json().

       # Pydantic-aligned fields (reserved for future use)
       populate_by_name: If True, allow population by field name as well as aliases.
       arbitrary_types_allowed: If True, allow arbitrary types (modict allows all types by default).
    """

    check_values: bool | Literal["auto"] = "auto"

    # modict-specific
    auto_convert: bool = True
    override_computed: bool = False
    require_all: bool = False
    check_keys: bool | Literal["auto"] = "auto"
    evaluate_computed: bool = True

    # Pydantic-aligned (actively used)
    extra: Literal['allow', 'forbid', 'ignore'] = 'allow'
    strict: bool = False
    enforce_json: bool = False
    frozen: bool = False
    validate_assignment: bool = False

    # Pydantic-aligned (reserved for future use)
    validate_default: bool = False
    populate_by_name: bool = False
    arbitrary_types_allowed: bool = False
    str_strip_whitespace: bool = False
    str_to_lower: bool = False
    str_to_upper: bool = False
    use_enum_values: bool = False
    allow_inf_nan: bool = True
    from_attributes: bool = False
    alias_generator: Optional[Callable[[str], str]] = None
    json_encoders: Optional[Dict[Type, Callable[[Any], Any]]] = None

    # champs passés explicitement à __init__
    _explicit: FrozenSet[str] = field(default_factory=frozenset, init=False, repr=False)

    def __init__(self, **kwargs):
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

        if 'check_values' in kwargs:
            cv = kwargs['check_values']
            if cv not in (True, False, 'auto'):
                raise TypeError("check_values must be True, False, or 'auto'")

        if 'check_keys' in kwargs:
            ck = kwargs['check_keys']
            if ck not in (True, False, 'auto'):
                raise TypeError("check_keys must be True, False, or 'auto'")

        # 1) garder la liste des clés explicitement fournies
        object.__setattr__(self, "_explicit", frozenset(kwargs.keys()))

        # 2) appliquer kwargs ou defaults de classe
        for f in fields(self):
            if not f.init or f.name == "_explicit":
                continue

            if f.name in kwargs:
                value = kwargs[f.name]
            else:
                if f.default is not DC_MISSING:
                    value = f.default
                elif f.default_factory is not DC_MISSING:  # type: ignore[attr-defined]
                    value = f.default_factory()            # type: ignore[misc]
                else:
                    raise TypeError(f"Missing required field {f.name!r}")

            # IMPORTANT : on bypass __setattr__ ici pour ne pas polluer _explicit
            object.__setattr__(self, f.name, value)

    def __setattr__(self, name, value):
        """
        Mutabilité assumée :
        - si on modifie un champ "normal" (init=True), on l'ajoute à _explicit
        - _explicit lui-même est géré à part
        """
        if name == "_explicit":
            object.__setattr__(self, name, value)
            return

        if name == "check_values" and value not in (True, False, "auto"):
            raise TypeError("check_values must be True, False, or 'auto'")
        if name == "check_keys" and value not in (True, False, "auto"):
            raise TypeError("check_keys must be True, False, or 'auto'")

        # On ne calcule la liste des champs init qu'une fois si tu veux optimiser,
        # mais même comme ça c'est ok.
        field_names = {f.name for f in fields(self) if f.init}

        if name in field_names:
            # on marque ce champ comme explicitement défini
            explicit = set(getattr(self, "_explicit", frozenset()))
            explicit.add(name)
            object.__setattr__(self, "_explicit", frozenset(explicit))

        object.__setattr__(self, name, value)

    @classmethod
    def _from_values(cls, values: dict[str, object], explicit: FrozenSet[str]) -> "modictConfig":
        """
        Constructeur interne qui contourne __init__ pour
        contrôler à la fois les valeurs et _explicit.
        """
        self = object.__new__(cls)  # n'appelle pas __init__
        for f in fields(cls):
            if f.name == "_explicit":
                continue
            object.__setattr__(self, f.name, values[f.name])
        object.__setattr__(self, "_explicit", explicit)
        return self

    def copy(self) -> "modictConfig":
        """Copie complète, en conservant _explicit."""
        values: dict[str, object] = {}
        for f in fields(self):
            if not f.init or f.name == "_explicit":
                continue
            values[f.name] = getattr(self, f.name)
        return modictConfig._from_values(values, self._explicit)

    def merge(self, other: "modictConfig") -> "modictConfig":
        """
        Comme dict.update :
        - les champs explicitement définis dans `other` écrasent ceux de `self`
        - les autres restent ceux de `self`
        - _explicit du résultat = union des explicites de self et other
        """
        merged_values: dict[str, object] = {}

        for f in fields(self):
            if not f.init or f.name == "_explicit":
                continue

            name = f.name
            if name in other._explicit:
                merged_values[name] = getattr(other, name)
            else:
                merged_values[name] = getattr(self, name)

        merged_explicit = self._explicit | other._explicit

        return modictConfig._from_values(merged_values, merged_explicit)


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

class Factory:

    def __init__(self,factory:Callable):
        self.factory=factory

    def __call__(self):
        return self.factory()
    
class Validator:
    """
    Représente un checker qui valide/transforme une valeur de field.
    
    Args:
        func: Une fonction qui prend (instance, value) et retourne la valeur transformée
        field_name: Le nom du field à checker
    """
    
    def __init__(self, func: Callable, field_name: str, *, mode: Literal["before", "after"] = "before"):
        self.func = func
        self.field_name = field_name
        self.mode = mode

    @staticmethod
    def _call_with_context(
        func: Callable,
        *,
        instance: Any,
        value: Any,
        field_name: str,
        cls: Any,
        values: Any,
        info: Any,
    ) -> Any:
        """
        Best-effort adapter to call validators coming from different ecosystems.

        Supports common signatures from:
        - modict validators: (self, value)
        - simple callables: (value)
        - Pydantic validators: (cls, value), (cls, value, values), (cls, value, info)
        """
        # Build kwargs from accepted parameter names.
        kwargs_by_name = {
            "self": instance,
            "instance": instance,
            "cls": cls,
            "value": value,
            "v": value,
            "values": values,
            "data": values,
            "info": info,
            "field": field_name,
            "field_name": field_name,
        }

        try:
            sig = inspect.signature(func)
        except (TypeError, ValueError):
            # Some callables (C-extensions, validators objects) don't expose signature.
            # Try a few common fallbacks (including modict's convention).
            for args in (
                (instance, value),
                (value,),
                (cls, value),
                (cls, value, values),
                (cls, value, info),
            ):
                try:
                    return func(*args)
                except TypeError:
                    continue
            raise

        kwargs = {}
        positional_args: list[Any] = []
        has_var_positional = False
        has_var_keyword = False

        for param in sig.parameters.values():
            if param.kind is param.VAR_POSITIONAL:
                has_var_positional = True
                continue
            if param.kind is param.VAR_KEYWORD:
                has_var_keyword = True
                continue

            if param.name in kwargs_by_name:
                if param.kind is param.POSITIONAL_ONLY:
                    positional_args.append(kwargs_by_name[param.name])
                else:
                    kwargs[param.name] = kwargs_by_name[param.name]

        if has_var_keyword:
            for name, val in kwargs_by_name.items():
                kwargs.setdefault(name, val)

        try:
            return func(*positional_args, **kwargs)
        except TypeError:
            # If we couldn't satisfy required parameters by name, fall back to common patterns.
            for args in (
                (instance, value),
                (value,),
                (cls, value),
                (cls, value, values),
                (cls, value, info),
            ):
                try:
                    return func(*args)
                except TypeError:
                    continue
            raise

    def __call__(self, instance, value, *, values=None, cls=None, info=None):
        """Execute le checker sur la valeur."""
        try:
            effective_cls = cls if cls is not None else type(instance) if instance is not None else None
            effective_values = values if values is not None else (dict(instance) if instance is not None else None)
            return self._call_with_context(
                self.func,
                instance=instance,
                value=value,
                field_name=self.field_name,
                cls=effective_cls,
                values=effective_values,
                info=info,
            )
        except Exception as e:
            raise ValueError(f"Error in checker for field '{self.field_name}': {e}")

class ModelValidator:
    """Model-level validator (multi-field invariants)."""

    def __init__(self, func: Callable, *, mode: Literal["before", "after"] = "after"):
        self.func = func
        self.mode = mode

    def __call__(self, instance, *, values=None, cls=None, info=None):
        try:
            effective_cls = cls if cls is not None else type(instance) if instance is not None else None
            effective_values = values if values is not None else (dict(instance) if instance is not None else None)
            # Reuse Validator adapter for signature flexibility.
            return Validator._call_with_context(
                self.func,
                instance=instance,
                value=effective_values,
                field_name="__model__",
                cls=effective_cls,
                values=effective_values,
                info=info,
            )
        except Exception as e:
            raise ValueError(f"Error in model validator: {e}")

class Computed:
    """
    Represents a computed property that dynamically calculates its value.
    
    Args:
        func: A callable that takes the modict instance and returns the computed value
        cache: Whether to cache the computed value (default: False)
        deps: List of keys to watch for cache invalidation. If None, cache is invalidated
              on any change. If empty list [], cache is never invalidated automatically.
    """
    
    def __init__(self, func: Callable, cache: bool = False, deps: Optional[List[str]] = None):
        self.func = func
        self.cache = cache
        # Si deps pas fourni explicitement, le récupérer de la fonction décorée
        if deps is None and hasattr(func, '_computed_deps'):
            deps = func._computed_deps
        self.deps = deps  # None = invalider sur tout changement, [] = jamais invalider auto
        self._cached_value = MISSING
        self._cache_valid = False

    def copy(self):
        return Computed(self.func,self.cache,deps=self.deps)

    def __call__(self, instance):
        """Compute the value for the given modict instance."""
        if self.cache and self._cache_valid:
            return self._cached_value
            
        try:
            value = self.func(instance)
            if self.cache:
                self._cached_value = value
                self._cache_valid = True
            return value
        except Exception as e:
            raise ValueError(f"Error computing value: {e}")
    
    def invalidate_cache(self):
        """Invalidate the cached value."""
        self._cache_valid = False
        self._cached_value = MISSING

    def should_invalidate_for_keys(self, keys: set) -> bool:
        """
        Check if this computed should be invalidated when any of the given keys change.
        
        Args:
            keys: Set of keys that have changed
            
        Returns:
            bool: True if cache should be invalidated
        """
        if not self.cache:
            return False  # Pas de cache = pas d'invalidation
            
        if self.deps is None:
            return True  # None = invalider sur tout changement
            
        if len(self.deps) == 0:
            return False  # Liste vide = jamais invalider automatiquement
            
        # Invalider si au moins une dépendance est dans les clés modifiées
        return bool(set(self.deps) & keys)

class Field:
    def __init__(
        self,
        hint=None,
        default=MISSING,
        validators=None,
        required: Optional[bool] = None,
        metadata: Optional[Dict[str, Any]] = None,
        constraints: Optional[Dict[str, Any]] = None,
        aliases: Optional[Dict[str, Any]] = None,
        _pydantic: Optional[Dict[str, Any]] = None,
    ):
        self.default = default
        self.hint = hint
        self.validators = validators or []  # List of Validator objects
        # Required is opt-in: fields are only required when explicitly requested.
        # This keeps modict dict-first (missing keys are allowed unless enforced).
        self.required = bool(required) if required is not None else False
        if metadata is not None and not isinstance(metadata, dict):
            raise TypeError("metadata must be a dict or None")
        self.metadata = dict(metadata or {})
        if constraints is not None and not isinstance(constraints, dict):
            raise TypeError("constraints must be a dict or None")
        self.constraints = dict(constraints or {})
        if aliases is not None and not isinstance(aliases, dict):
            raise TypeError("aliases must be a dict or None")
        self.aliases = dict(aliases or {})
        # Internal: bucket for Pydantic-only metadata preserved for round-trips.
        # Not part of the public Field metadata contract and not used for schema export.
        self._pydantic: Dict[str, Any] = dict(_pydantic or {})

    def add_validator(self, validator):
        """Add a validator to the field."""
        self.validators.append(validator)

    def get_default(self):
        if isinstance(self.default, Factory):
            value=self.default()
        else:
            value=self.default
        if isinstance(value,Computed):
            value=value.copy()
        return value

def is_locally_defined_class(key: str, value: Any, name: str, dct: Dict[str, Any]) -> bool:
    """Détermine si une classe a été définie dans ce namespace"""
    if not isinstance(value, type):
        return False
    
    # Même logique que pour les fonctions
    expected_qualname = f"{name}.{key}"
    module = dct.get("__module__")
    return (module is not None and value.__module__ == module and
            value.__qualname__ == expected_qualname)

def is_locally_defined_descriptor(key: str, value: Any, name: str, dct: Dict[str, Any]) -> bool:
    """Détermine si un descripteur a été défini dans cette classe vs assigné"""
    
    # Extraire la fonction sous-jacente selon le type
    if isinstance(value, FunctionType):
        underlying_func = value
    elif isinstance(value, (classmethod, staticmethod)):
        underlying_func = value.__func__
    elif isinstance(value, property):
        underlying_func = value.fget
    else:
        return False  # Autres descripteurs → assignés par défaut
    
    # Vérifier si défini localement via qualname
    expected_qualname = f"{name}.{key}"
    module = dct.get("__module__")
    return (module is not None and underlying_func.__module__ == module and
            underlying_func.__qualname__ == expected_qualname)

def is_field(key: str, value: Any, name: str, bases: Tuple[Type, ...], dct: Dict[str, Any]) -> bool:
    # Already a Field
    if isinstance(value, Field):
        return True
    
    # @modict.computed() decorated functions are always fields
    if hasattr(value, '_is_computed'):
        return True
    
    # @modict.validator() decorated functions are NOT fields - traitement spécial
    if hasattr(value, '_is_validator'):
        return False

    # @modict.model_validator() decorated functions are NOT fields
    if hasattr(value, "_is_model_validator"):
        return False
    
    # Skip private/special attributes
    if key.startswith('__'):
        return False
    
    # Exclude attrs already present in the hierarchy
    for base in bases:
        if hasattr(base, key):
            return False
        
    # check classes
    if isinstance(value, type):
        return not is_locally_defined_class(key, value, name, dct)
       
    # check descriptors
    if hasattr(value, '__get__') or isinstance(value, (classmethod, staticmethod, property)):
        return not is_locally_defined_descriptor(key, value, name, dct)
                   
    return True


class modictMeta(type):

    def __new__(mcls, name, bases, dct):
        fields = {}
        annotations = dct.get('__annotations__', {})
        model_validators: list[ModelValidator] = []

        # Merge with fields from parent classes respecting mro order
        for base in reversed(bases):
            if hasattr(base,'__fields__'):
                fields.update(base.__fields__)
            if hasattr(base, "__model_validators__"):
                model_validators.extend(list(base.__model_validators__))  # type: ignore[attr-defined]

        # If class dict already provides model validators (e.g. interop), include them too
        existing_model_validators = dct.get("__model_validators__")
        if existing_model_validators:
            model_validators.extend(list(existing_model_validators))

        # deal with annotations
        for key, hint in annotations.items():
            if key in dct:
                value = dct[key]
                if isinstance(value, FunctionType) and hasattr(value, '_is_computed'):
                    # @modict.computed() decorated method
                    cache = getattr(value, '_computed_cache', False)
                    deps = getattr(value, '_computed_deps', None)
                    computed_obj = Computed(value, cache=cache, deps=deps)
                    # Priorité : annotation de classe, puis annotation de retour de la fonction
                    func_return_hint = getattr(value, '__annotations__', {}).get('return')
                    final_hint = hint if hint is not None else func_return_hint
                    fields[key] = Field(default=computed_obj, hint=final_hint, required=False)
                elif not isinstance(value, Field):
                    fields[key] = Field(default=value, hint=hint, required=False)
                else:
                    # already a field, we add the hint (unless already defined)
                    if value.hint is None:
                        value.hint = hint
                    fields[key] = value
                dct.pop(key)
            else:
                # Annotation without value -> Field(default=MISSING)
                # Annotation-only fields are not required by default in modict (dict-first).
                fields[key] = Field(default=MISSING, hint=hint, required=False)
        
        # deal with namespace
        for key, value in list(dct.items()):
            if key not in annotations:
                if is_field(key, value, name, bases, dct):
                    if isinstance(value, FunctionType) and hasattr(value, '_is_computed'):
                        # @modict.computed() decorated method
                        cache = getattr(value, '_computed_cache', False)
                        deps = getattr(value, '_computed_deps', None)
                        computed_obj = Computed(value, cache=cache, deps=deps)
                        # Pour les champs computed, utiliser l'annotation de retour de la fonction
                        func_return_hint = getattr(value, '__annotations__', {}).get('return')
                        fields[key] = Field(default=computed_obj, hint=func_return_hint, required=False)
                    elif not isinstance(value, Field):
                        fields[key] = Field(default=value)
                    else:
                        fields[key] = value
                    dct.pop(key)

        # Traitement des validators
        for key, value in list(dct.items()):
            if isinstance(value, FunctionType) and hasattr(value, '_is_validator'):
                field_name = value._validator_field
                validator_mode = getattr(value, "_validator_mode", "before")
                check_obj = Validator(value, field_name, mode=validator_mode)
                
                # Field existe déjà (hérité ou déclaré dans cette classe) ?
                if field_name in fields:
                    fields[field_name].add_validator(check_obj)
                else:
                    # Créer un nouveau Field minimal pour le checker
                    fields[field_name] = Field(validators=[check_obj])
                
                # Retirer la fonction du namespace de la classe
                dct.pop(key)

        # Traitement des model validators
        for key, value in list(dct.items()):
            if isinstance(value, FunctionType) and hasattr(value, "_is_model_validator"):
                mode = getattr(value, "_model_validator_mode", "after")
                if mode not in ("before", "after"):
                    mode = "after"
                model_validators.append(ModelValidator(value, mode=mode))
                dct.pop(key)

        # Store fields in __fields__
        dct['__fields__'] = fields
        dct["__model_validators__"] = tuple(model_validators)

        # Setup _config using modictConfig with proper MRO merging

        # Construire une config parent à partir de TOUTES les bases
        parent_config = None

        # On parcourt les bases de la dernière à la première
        # pour que la base la plus à gauche (dans class X(A, B)) gagne
        for base in reversed(bases):
            base_conf = getattr(base, '_config', None)
            if base_conf is None:
                continue

            if parent_config is None:
                parent_config = base_conf
            else:
                # merge comme dict.update : les champs explicites de base_conf
                # écrasent ceux déjà dans parent_config
                parent_config = parent_config.merge(base_conf)

        if '_config' in dct:
            # _config explicitement défini dans cette classe
            local_config = dct['_config']
            if not isinstance(local_config, modictConfig):
                raise TypeError(
                    f"_config must be a modictConfig instance created via modict.config(), "
                    f"got {type(local_config)}. Use: _config = modict.config(enforce_json=True, ...)"
                )

            if parent_config is not None:
                # On empile la config locale par-dessus la config combinée des bases
                effective_config = parent_config.merge(local_config)
            else:
                # Pas de parents qui ont une config → on prend juste la locale
                effective_config = local_config
        else:
            # Pas de _config local → héritage pur ou defaults
            if parent_config is not None:
                effective_config = parent_config
            else:
                effective_config = modictConfig()

        dct['_config'] = effective_config

        # Apply alias_generator (if any) to fields lacking explicit aliases.
        alias_generator = getattr(effective_config, "alias_generator", None)
        if callable(alias_generator):
            for field_name, field_obj in fields.items():
                # Skip computed fields: they are not meant to be populated from input.
                if isinstance(field_obj.default, Computed):
                    continue
                # Respect explicit aliases provided on the Field.
                if isinstance(getattr(field_obj, "aliases", None), dict) and field_obj.aliases:
                    continue
                try:
                    alias = alias_generator(field_name)
                except Exception as e:
                    raise TypeError(
                        f"alias_generator failed for field '{field_name}' in class '{name}': {e}"
                    ) from e
                if alias is None:
                    continue
                if not isinstance(alias, str) or not alias:
                    raise TypeError(
                        f"alias_generator must return a non-empty str for field '{field_name}' "
                        f"in class '{name}', got {alias!r}"
                    )
                field_obj.aliases["alias"] = alias

        # Validate default values if validate_default is enabled
        if effective_config.validate_default:
            from ._typechecker import check_type, TypeMismatchError

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
