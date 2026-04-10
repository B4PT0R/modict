"""
TypeChecker - A comprehensive runtime type checking library
"""
from dataclasses import dataclass
import inspect
import types
import typing
from typing import Any, Dict, List, Set, Tuple, Union, Optional, Callable, TypeVar, get_origin, get_args
import collections
import collections.abc
import sys
import functools

try:  # pragma: no cover - optional backport on older Python versions
    import typing_extensions as _typing_extensions
except Exception:  # pragma: no cover
    _typing_extensions = None

#region: Errors

class TypeCheckException(Exception):
    pass

class TypeCheckError(TypeCheckException):
    """Exception raised for common type check errors"""
    pass

class TypeMismatchError(TypeCheckException):
    """Exception raised when a value doesn't match the type."""
    pass

class TypeCheckFailureError(TypeCheckException):
    """Exception raised for other uncaught or critical errors"""
    pass

#endregion

#region: Hint compilation

@dataclass(frozen=True)
class CompiledHint:
    kind: str
    origin: Any = None
    args: tuple[Any, ...] = ()
    special_form_name: str | None = None
    checker_kind: str | None = None
    parameterized_generic: bool = False
    hint_origin: Any = None

#endregion

#region: TypeChecker Class
class TypeChecker:
    """
    A comprehensive runtime type checker that supports modern typing constructs.
    """
    
    def __init__(self, *, use_cache: bool = True):
        self.use_cache = use_cache
        self._active_checks: set[tuple[int, int]] = set()
        self._compiled_hint_cache: dict[Any, CompiledHint] = {}
        self._checker_kind_cache: dict[Any, str | None] = {}
        self._abc_checker_kind_cache: dict[Any, str | None] = {}

        self.origin_to_type_map = {
            # Basic collections
            typing.List: list,
            typing.Tuple: tuple,
            typing.Dict: dict,
            typing.Set: set,
            typing.FrozenSet: frozenset,
            
            # Sequence abstractions
            typing.Sequence: collections.abc.Sequence,
            typing.MutableSequence: collections.abc.MutableSequence,
            
            # Mapping abstractions
            typing.Mapping: collections.abc.Mapping,
            typing.MutableMapping: collections.abc.MutableMapping,
            
            # Set abstractions
            typing.AbstractSet: collections.abc.Set,
            typing.MutableSet: collections.abc.MutableSet,
            
            # Collection abstractions
            typing.Collection: collections.abc.Collection,
            typing.Container: collections.abc.Container,
            typing.Sized: collections.abc.Sized,
            
            # Iterator types
            typing.Iterable: collections.abc.Iterable,
            typing.Iterator: collections.abc.Iterator,
            typing.Generator: collections.abc.Generator,
            typing.Reversible: collections.abc.Reversible,
            
            # Callable types
            typing.Callable: collections.abc.Callable,
            typing.Type: type,
            
            # Bytes-like types
            typing.ByteString: collections.abc.ByteString,
            
            # Additional sequence types
            typing.Deque: collections.deque,
            
            # Additional mapping types
            typing.DefaultDict: collections.defaultdict,
            typing.OrderedDict: collections.OrderedDict,
            typing.ChainMap: collections.ChainMap,
            typing.Counter: collections.Counter,
            
            # Additional set types
            # (None needed, Set and FrozenSet cover the built-ins)
            
            # View types
            typing.KeysView: collections.abc.KeysView,
            typing.ItemsView: collections.abc.ItemsView,
            typing.ValuesView: collections.abc.ValuesView,
            
            # Async types (if we want to support them)
            typing.AsyncIterator: collections.abc.AsyncIterator,
            typing.AsyncIterable: collections.abc.AsyncIterable,
            typing.AsyncGenerator: collections.abc.AsyncGenerator,
            typing.Coroutine: collections.abc.Coroutine,
            typing.Awaitable: collections.abc.Awaitable,
            
            # Additional ABCs from collections.abc
            typing.Hashable: collections.abc.Hashable,
        }
        
        self.type_checkers = {
            # Basic collections
            (typing.List, list): self._check_sequence_like,
            (typing.Tuple, tuple): self._check_tuple_like,
            (typing.Dict, dict): self._check_mapping_like,
            (typing.Set, set): self._check_set_like,
            (typing.FrozenSet, frozenset): self._check_set_like,
            (typing.Type, type): self._check_type_type,
            
            # Sequence abstractions
            (typing.Sequence, collections.abc.Sequence): self._check_sequence_like,
            (typing.MutableSequence, collections.abc.MutableSequence): self._check_sequence_like,
            
            # Mapping abstractions
            (typing.Mapping, collections.abc.Mapping): self._check_mapping_like,
            (typing.MutableMapping, collections.abc.MutableMapping): self._check_mapping_like,
            
            # Set abstractions
            (typing.AbstractSet, collections.abc.Set): self._check_set_like,
            (typing.MutableSet, collections.abc.MutableSet): self._check_set_like,
            
            # Collection abstractions
            (typing.Collection, collections.abc.Collection): self._check_collection_like,
            (typing.Container, collections.abc.Container): self._check_container_like,
            (typing.Sized, collections.abc.Sized): lambda h, v: isinstance(v, collections.abc.Sized),
            
            # Iterator types
            (typing.Iterable, collections.abc.Iterable): self._check_iterable_like,
            (typing.Iterator, collections.abc.Iterator): self._check_iterator_like,
            (typing.Generator, collections.abc.Generator): self._check_iterator_like,
            (typing.Reversible, collections.abc.Reversible): lambda h, v: isinstance(v, collections.abc.Reversible),
            
            # Callable types
            (typing.Callable, collections.abc.Callable): self._check_callable,
            
            # View types
            (typing.KeysView, collections.abc.KeysView): self._check_mapping_view,
            (typing.ItemsView, collections.abc.ItemsView): self._check_mapping_view,
            (typing.ValuesView, collections.abc.ValuesView): self._check_mapping_view,
            
            # ByteString types
            (typing.ByteString, collections.abc.ByteString): lambda h, v: isinstance(v, collections.abc.ByteString),
            
            # Additional collection types with concrete implementations
            (typing.Deque, collections.deque): self._check_sequence_like,
            (typing.OrderedDict, collections.OrderedDict): self._check_mapping_like,
            (typing.DefaultDict, collections.defaultdict): self._check_mapping_like,
            (typing.ChainMap, collections.ChainMap): self._check_mapping_like,
            (typing.Counter, collections.Counter): self._check_mapping_like,
        }
        self._checker_by_origin = {
            origin: checker
            for origins, checker in self.type_checkers.items()
            for origin in origins
        }
        self._runtime_wrapper_origins = tuple(
            wrapper
            for wrapper in (
                getattr(typing, "Required", None),
                getattr(typing, "NotRequired", None),
                getattr(typing, "ReadOnly", None),
                getattr(_typing_extensions, "Required", None) if _typing_extensions is not None else None,
                getattr(_typing_extensions, "NotRequired", None) if _typing_extensions is not None else None,
                getattr(_typing_extensions, "ReadOnly", None) if _typing_extensions is not None else None,
            )
            if wrapper is not None
        )
        self._required_wrapper_origins = tuple(
            wrapper
            for wrapper in (
                getattr(typing, "Required", None),
                getattr(_typing_extensions, "Required", None) if _typing_extensions is not None else None,
            )
            if wrapper is not None
        )
        self._notrequired_wrapper_origins = tuple(
            wrapper
            for wrapper in (
                getattr(typing, "NotRequired", None),
                getattr(_typing_extensions, "NotRequired", None) if _typing_extensions is not None else None,
            )
            if wrapper is not None
        )
        self._annotated_origins = tuple(
            wrapper
            for wrapper in (
                getattr(typing, "Annotated", None),
                getattr(_typing_extensions, "Annotated", None) if _typing_extensions is not None else None,
            )
            if wrapper is not None
        )
        self._NoneType = type(None)
        self._self_type = getattr(typing, "Self", None)
        self._type_alias_type = getattr(typing, "TypeAliasType", None)
        self._special_form_names = frozenset({
            'Union', 'Optional', 'ClassVar', 'Final', 'Literal',
            'TypeGuard', 'ParamSpec', 'Concatenate', 'Annotated',
            'LiteralString', 'Never', 'NoReturn',
        })
        self._generic_alias_types = tuple(filter(None, (
            getattr(typing, '_GenericAlias', None),
            getattr(typing, 'GenericAlias', None),
            getattr(typing, '_SpecialGenericAlias', None),
            getattr(types, 'GenericAlias', None),
        )))
        self._has_union_type = hasattr(types, "UnionType")
        self._union_type = getattr(types, "UnionType", None)

    def _maybe_get_cached(self, cache: dict[Any, Any], key: Any, factory: Callable[[], Any]) -> Any:
        if not self.use_cache:
            return factory()
        try:
            return cache[key]
        except KeyError:
            value = factory()
            try:
                cache[key] = value
            except TypeError:
                pass
            return value
        except TypeError:
            return factory()

    #region: entry point
    def check_type(self, hint: Any, value: Any) -> bool:
        """
        Check if a value matches the given type hint.
        Main entry point of the TypeChecker class

        Args:
            hint: A type annotation or typing construct
            value: The value to check against the type hint

        Returns:
            bool: True if the value matches the type hint

        Raises:
            TypeMismatchError: When the value doesn't match the type hint
            TypeCheckError: When some minor error made the type check impossible
            TypeCheckFailureError: When any other uncaught exception occurs
        """
        fast_result = self._check_type_fast_path(hint, value)
        if fast_result is not None:
            if not fast_result:
                raise TypeMismatchError()
            return True

        guard_key = (id(hint), id(value))
        if guard_key in self._active_checks:
            return True

        try:
            self._active_checks.add(guard_key)
            # Go directly to plan dispatch — fast path already failed
            result = self._check_type_from_plan(hint, value)
            if not isinstance(result, bool):
                raise TypeCheckFailureError(
                    f"_check_type_from_plan returned non-boolean value: {result}"
                )
            if not result:
                raise TypeMismatchError()
            return result
        except TypeMismatchError:
            raise
        except TypeCheckError:
            raise
        except Exception as e:
            raise TypeCheckFailureError(f"Error during type checking: {str(e)}")
        finally:
            self._active_checks.discard(guard_key)
    #endregion

    #region: hint parsing

    def _origin_to_type(self,origin):
        return self.origin_to_type_map.get(origin,origin)

    def _typing_wrapper_origins(self):
        """Return runtime-transparent typing wrappers that should be unwrapped."""
        return self._runtime_wrapper_origins

    def _is_runtime_wrapper(self, hint: Any) -> bool:
        """Return True for wrappers such as Required[T] and NotRequired[T]."""
        origin = get_origin(hint)
        return origin in self._runtime_wrapper_origins

    def _unwrap_runtime_wrapper(self, hint: Any) -> Any:
        """Unwrap runtime-transparent typing wrappers to their inner type."""
        if not self._is_runtime_wrapper(hint):
            return hint
        args = get_args(hint)
        if len(args) != 1:
            raise TypeCheckError(f"{get_origin(hint)} requires exactly 1 type argument")
        return args[0]

    def _is_forward_ref_hint(self, hint: Any) -> bool:
        """Return True for explicit ForwardRef objects."""
        return isinstance(hint, typing.ForwardRef)

    def _unwrap_forward_ref_hint(self, hint: Any) -> str:
        """Extract the string payload from a ForwardRef object."""
        arg = getattr(hint, "__forward_arg__", None)
        if not isinstance(arg, str):
            raise TypeCheckError(f"Invalid ForwardRef payload: {hint!r}")
        return arg

    def _is_type_alias_hint(self, hint: Any) -> bool:
        """Return True for modern TypeAliasType objects when available."""
        alias_type = getattr(typing, "TypeAliasType", None)
        return alias_type is not None and isinstance(hint, alias_type)

    def _unwrap_type_alias_hint(self, hint: Any) -> Any:
        """Return the underlying value of a TypeAliasType."""
        value = getattr(hint, "__value__", None)
        if value is None:
            raise TypeCheckError(f"Invalid TypeAliasType payload: {hint!r}")
        return value

    def _resolved_annotations(self, hint: Any) -> dict[str, Any]:
        """Return annotations with extras preserved when the runtime supports it."""
        try:
            return typing.get_type_hints(hint, include_extras=True)
        except Exception:
            return getattr(hint, "__annotations__", {}) or {}

    def _literal_values_equal(self, left: Any, right: Any) -> bool:
        """Compare literal values while keeping bool and int distinct."""
        return type(left) is type(right) and left == right

    def _typed_dict_required_keys(self, hint: Any) -> set[str]:
        """Return the required keys for a TypedDict, including Required/NotRequired overrides."""
        required = getattr(hint, "__required_keys__", None)
        required_names = set(required or ())

        annotations = self._resolved_annotations(hint)
        is_total = getattr(hint, "__total__", True)
        required_keys: set[str] = set(required_names)
        for name, annotation in annotations.items():
            origin = get_origin(annotation)
            if origin in self._required_wrapper_origins:
                required_keys.add(name)
            elif origin in self._notrequired_wrapper_origins:
                required_keys.discard(name)
            elif is_total:
                required_keys.add(name)
            elif name in required_names:
                required_keys.add(name)
        return required_keys

    def _protocol_member_names(self, protocol: type) -> set[str]:
        """Return the protocol members explicitly declared by a protocol type."""
        protocol_attr_getter = getattr(typing, "_get_protocol_attrs", None)
        if protocol_attr_getter is None and _typing_extensions is not None:
            protocol_attr_getter = getattr(_typing_extensions, "_get_protocol_attrs", None)
        if protocol_attr_getter is not None:
            try:
                return set(protocol_attr_getter(protocol))
            except Exception:
                pass

        names = getattr(protocol, "__protocol_attrs__", None)
        if names is not None:
            return set(names)

        collected: set[str] = set()
        for base in getattr(protocol, "__mro__", (protocol,)):
            if base is typing.Protocol or base is object or not getattr(base, "_is_protocol", False):
                continue
            collected.update(getattr(base, "__annotations__", {}).keys())
            for name, attr in getattr(base, "__dict__", {}).items():
                if isinstance(attr, property) or (callable(attr) and not isinstance(attr, type)):
                    collected.add(name)
        return collected

    def _protocol_members(self, protocol: type) -> dict[str, Any]:
        """Build the declared member specification for a protocol."""
        members: dict[str, Any] = {}
        for base in reversed(getattr(protocol, "__mro__", (protocol,))):
            if base is typing.Protocol or base is object or not getattr(base, "_is_protocol", False):
                continue

            base_annotations = self._resolved_annotations(base)
            for name in self._protocol_member_names(base):
                if name in base_annotations:
                    members[name] = self._unwrap_runtime_wrapper(base_annotations[name])
                    continue

                attr = getattr(base, "__dict__", {}).get(name, None)
                if isinstance(attr, property):
                    return_hint = getattr(attr.fget, "__annotations__", {}).get("return", Any) if attr.fget else Any
                    members[name] = self._unwrap_runtime_wrapper(return_hint)
                elif callable(attr) and not isinstance(attr, type):
                    members[name] = attr
        return members

    def _callable_hint_from_callable(self, func: Any, *, drop_first_parameter: bool = False):
        """Derive a Callable[...] hint from a callable object's signature when possible."""
        try:
            sig = inspect.signature(func)
        except (TypeError, ValueError):
            return Callable

        params = [
            p for p in sig.parameters.values()
            if p.kind in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.KEYWORD_ONLY,
            )
        ]
        if drop_first_parameter and params and params[0].name in {"self", "cls"}:
            params = params[1:]

        arg_hints = [
            (Any if p.annotation == inspect.Parameter.empty else p.annotation)
            for p in params
        ]
        return_hint = sig.return_annotation
        if return_hint == inspect.Parameter.empty:
            return_hint = Any

        return Callable[arg_hints, return_hint]

    def _is_annotation_subtype(self, actual: Any, expected: Any) -> bool:
        """Return True when ``actual`` is a subtype-like annotation of ``expected``."""
        if actual is expected:
            return True

        if actual == inspect.Parameter.empty or expected == inspect.Parameter.empty:
            return True

        if actual in (None, type(None)) and expected in (None, type(None)):
            return True

        if actual is Any or expected is Any:
            return True

        if self._is_type_alias_hint(actual):
            return self._is_annotation_subtype(self._unwrap_type_alias_hint(actual), expected)
        if self._is_type_alias_hint(expected):
            return self._is_annotation_subtype(actual, self._unwrap_type_alias_hint(expected))

        if self._is_forward_ref_hint(actual):
            return self._is_annotation_subtype(self._unwrap_forward_ref_hint(actual), expected)
        if self._is_forward_ref_hint(expected):
            return self._is_annotation_subtype(actual, self._unwrap_forward_ref_hint(expected))

        if self._is_runtime_wrapper(actual):
            return self._is_annotation_subtype(self._unwrap_runtime_wrapper(actual), expected)
        if self._is_runtime_wrapper(expected):
            return self._is_annotation_subtype(actual, self._unwrap_runtime_wrapper(expected))

        actual_form = self._get_special_form_name(actual) if self._is_special_form(actual) else None
        expected_form = self._get_special_form_name(expected) if self._is_special_form(expected) else None

        if actual_form == "Annotated":
            args = get_args(actual)
            return self._is_annotation_subtype(args[0], expected) if args else False
        if expected_form == "Annotated":
            args = get_args(expected)
            return self._is_annotation_subtype(actual, args[0]) if args else False

        if actual_form in {"Final", "ClassVar"}:
            args = get_args(actual)
            return self._is_annotation_subtype(args[0], expected) if args else True
        if expected_form in {"Final", "ClassVar"}:
            args = get_args(expected)
            return self._is_annotation_subtype(actual, args[0]) if args else True

        if actual_form == "Literal":
            return all(
                self._is_annotation_subtype(type(literal), expected)
                for literal in get_args(actual)
            )
        if expected_form == "Literal":
            expected_literals = get_args(expected)
            if actual_form == "Literal":
                return all(
                    any(self._literal_values_equal(left, right) for right in expected_literals)
                    for left in get_args(actual)
                )
            return False

        actual_origin = get_origin(actual)
        expected_origin = get_origin(expected)

        if actual_origin in (typing.Union, Union):
            return all(self._is_annotation_subtype(arg, expected) for arg in get_args(actual))
        if expected_origin in (typing.Union, Union):
            return any(self._is_annotation_subtype(actual, arg) for arg in get_args(expected))

        if actual_origin in (collections.abc.Callable, typing.Callable) or expected_origin in (collections.abc.Callable, typing.Callable):
            return self._is_callable_annotation_compatible(actual, expected)

        if isinstance(actual, type) and isinstance(expected, type):
            try:
                return issubclass(actual, expected)
            except TypeError:
                return False

        if actual_origin is not None and expected_origin is not None:
            try:
                origins_ok = (
                    actual_origin == expected_origin
                    or (
                        isinstance(actual_origin, type)
                        and isinstance(expected_origin, type)
                        and issubclass(actual_origin, expected_origin)
                    )
                )
            except TypeError:
                origins_ok = (actual_origin == expected_origin)

            if not origins_ok:
                return False

            actual_args = get_args(actual)
            expected_args = get_args(expected)
            if len(actual_args) != len(expected_args):
                return False
            return all(
                self._is_annotation_subtype(a, e)
                for a, e in zip(actual_args, expected_args)
            )

        return actual == expected

    def _is_callable_annotation_compatible(self, actual: Any, expected: Any) -> bool:
        """Return True when ``actual`` is compatible with ``expected`` as a Callable annotation."""
        actual_origin = get_origin(actual)
        expected_origin = get_origin(expected)

        callable_origins = (collections.abc.Callable, typing.Callable)
        if actual_origin not in callable_origins or expected_origin not in callable_origins:
            return actual == expected

        actual_args = get_args(actual)
        expected_args = get_args(expected)

        if not actual_args:
            return True
        if not expected_args:
            return True
        if len(actual_args) != 2 or len(expected_args) != 2:
            return actual == expected

        actual_params, actual_return = actual_args
        expected_params, expected_return = expected_args

        if actual_params is ...:
            params_ok = (expected_params is ...)
        elif expected_params is ...:
            params_ok = True
        else:
            if len(actual_params) != len(expected_params):
                return False
            params_ok = all(
                self._is_annotation_subtype(expected_param, actual_param)
                for actual_param, expected_param in zip(actual_params, expected_params)
            )

        return params_ok and self._is_annotation_subtype(actual_return, expected_return)

    def _is_generic_class(self, hint):
        """Check if a hint is a generic class that can be parameterized."""
        # Check if it's a type with __parameters__
        is_parameterized = isinstance(hint, type) and hasattr(hint, '__parameters__')
        
        # Also check for typing.Generic in bases
        if isinstance(hint, type):
            bases = getattr(hint, '__mro__', ())
            has_generic_base = typing.Generic in bases
            return is_parameterized or has_generic_base
        
        return is_parameterized
            
    def _is_protocol(self, hint):
        """
        Comprehensive protocol detection that handles both special form Protocol 
        and concrete protocol classes without relying on _is_special_form.
        """
        # Check for the protocol marker attribute on the hint itself
        is_protocol_class = isinstance(hint, type) and getattr(hint, '_is_protocol', False)
        
        # Check for Protocol special form directly
        name = getattr(hint, '_name', None)
        is_protocol_special_form = name == 'Protocol'
        
        # Check origin for parameterized protocols
        origin = get_origin(hint)
        if origin is not None:
            origin_name = getattr(origin, '_name', None)
            origin_is_protocol = origin_name == 'Protocol' or getattr(origin, '_is_protocol', False)
        else:
            origin_is_protocol = False
        
        return is_protocol_class or is_protocol_special_form or origin_is_protocol
    
    def _is_newtype(self,hint):
        return hasattr(hint, '__supertype__')
    
    def _is_basic_type(self,hint):
        return isinstance(hint,type) and not self._is_protocol(hint) and not self._is_generic_class(hint) and not self._is_newtype(hint)

    def _is_generic_alias(self, hint):
        """
        Check if a hint is a generic alias like List[int], Dict[str, int], etc.
        """
        if self._is_special_form(hint):
            return False
        return (isinstance(hint, self._generic_alias_types)
                or getattr(hint, '__origin__', None) is not None)

    def _is_typeddict(self, hint):
        """Check if a hint is a TypedDict."""
        return hasattr(hint, "__annotations__") and hasattr(hint, "__total__")

    def _is_special_form(self, hint):
        """
        Check if a hint is a special form (Union, Optional, ClassVar, etc.).
        Uses a consistent approach that works across Python versions.
        """
        # Handle PEP 604 union types (Python 3.10+)
        if self._has_union_type and isinstance(hint, self._union_type):
            return True

        origin = get_origin(hint)
        if origin in self._annotated_origins:
            return True

        # Check the name attribute (parameterized or direct)
        name = None
        if origin is not None:
            name = getattr(origin, '_name', None)
        if name is None:
            name = getattr(hint, '_name', None)

        return name in self._special_form_names

    def _get_special_form_name(self, hint):
        """
        Get the name of a special form type hint.
        Works with both direct special forms and parameterized ones.
        
        Args:
            hint: A special form type hint (e.g., Union, Optional)
            
        Returns:
            str or None: The name of the special form, or None if not found
        """
        # For parameterized special forms, get the name from the origin
        origin = get_origin(hint)
        if origin in self._annotated_origins:
            return "Annotated"
        if origin is not None:
            name = getattr(origin, '_name', None)
            if name:
                return name
                    
        # For direct special forms, get the name directly
        return getattr(hint, '_name', None)
    
    def _is_box_like_generic(self, origin, args, value):
        """
        Check if this is a Box-like generic class with a 'value' attribute.
        Used for handling simple generic wrapper classes.
        
        Args:
            origin: The origin type
            args: The type arguments
            value: The value to check
            
        Returns:
            bool: True if this is a Box-like generic with a 'value' attribute
        """
        return (origin is not None and 
                hasattr(value, '__class__') and
                args and 
                len(args) == 1 and 
                hasattr(value, 'value'))

    def _is_parameterized_generic(self, origin, hint):
        """
        Check if this is a generic class with type parameters.
        
        Args:
            origin: The origin type
            hint: The type hint
            
        Returns:
            bool: True if this is a parameterized generic class
        """
        return ((origin is not None and hasattr(origin, '__parameters__')) or 
                (origin is None and hasattr(hint, '__parameters__')))

    def _is_special_origin(self, origin):
        """
        Check if an origin type is a special form.
        
        Args:
            origin: The origin type to check
            
        Returns:
            bool: True if the origin is a special form
        """
        return getattr(origin, '_special', False)

    def _checker_method_to_kind(self, checker_method) -> str | None:
        name = getattr(checker_method, "__name__", None)
        if name and name.startswith("_check_"):
            return name[len("_check_"):]
        return None

    def _get_checker_kind(self, origin):
        return self._maybe_get_cached(
            self._checker_kind_cache,
            origin,
            lambda: self._checker_method_to_kind(self._get_checker(origin)),
        )

    def _get_abc_checker_kind(self, origin):
        return self._maybe_get_cached(
            self._abc_checker_kind_cache,
            origin,
            lambda: self._checker_method_to_kind(self._get_abc_checker(origin)),
        )

    def _compile_hint(self, hint: Any) -> CompiledHint:
        return self._maybe_get_cached(
            self._compiled_hint_cache,
            hint,
            lambda: self._build_hint_plan(hint),
        )

    def _build_hint_plan(self, hint: Any) -> CompiledHint:
        # ── Rare hint wrappers (cached so they're only computed once per hint) ──

        # TypeAliasType (PEP 695)
        if self._type_alias_type is not None and isinstance(hint, self._type_alias_type):
            value = getattr(hint, "__value__", None)
            if value is None:
                raise TypeCheckError(f"Invalid TypeAliasType payload: {hint!r}")
            return CompiledHint(kind="type_alias", args=(value,))

        # ForwardRef object
        if isinstance(hint, typing.ForwardRef):
            arg = getattr(hint, "__forward_arg__", None)
            if not isinstance(arg, str):
                raise TypeCheckError(f"Invalid ForwardRef payload: {hint!r}")
            return CompiledHint(kind="forward_ref", args=(arg,))

        # Self (PEP 673)
        if self._self_type is not None and hint is self._self_type:
            return CompiledHint(kind="self")

        # Compute origin once — reused by several checks below
        origin = get_origin(hint)

        # Runtime-transparent wrappers: Required[T], NotRequired[T], ReadOnly[T]
        if origin is not None and origin in self._runtime_wrapper_origins:
            inner = get_args(hint)
            if len(inner) != 1:
                raise TypeCheckError(f"{origin} requires exactly 1 type argument")
            return CompiledHint(kind="runtime_wrapper", args=(inner[0],))

        # ── Standard hint kinds ──

        if self._is_typeddict(hint):
            return CompiledHint(kind="typeddict")

        if self._is_protocol(hint):
            return CompiledHint(kind="protocol")

        if self._is_special_form(hint):
            return CompiledHint(
                kind="special_form",
                special_form_name=self._get_special_form_name(hint),
            )

        if self._is_generic_alias(hint):
            if origin is None:
                origin = get_origin(hint)
            return CompiledHint(
                kind="generic_alias",
                origin=origin,
                args=get_args(hint),
                checker_kind=self._get_checker_kind(origin),
                parameterized_generic=self._is_parameterized_generic(origin, hint),
                hint_origin=getattr(hint, "__origin__", None),
            )

        if self._is_generic_class(hint):
            return CompiledHint(kind="generic_class")

        if self._is_basic_type(hint):
            return CompiledHint(kind="basic_type")

        if isinstance(hint, TypeVar):
            return CompiledHint(kind="typevar")

        if self._is_newtype(hint):
            return CompiledHint(kind="newtype")

        return CompiledHint(kind="unsupported")

    #endregion

    #region: core logic

    def _check_basic_type(self,hint,value):
        """
        Similar to isinstance check but doesn't accept booleans as int
        """
        if hint is int:
            return isinstance(value, int) and not isinstance(value,bool)
        return isinstance(value,hint)

    def _check_type_fast_path(self, hint: Any, value: Any) -> bool | None:
        """Fast path for the most common non-recursive runtime checks.

        Ordered by realistic frequency: int/str/float first, then bool,
        None, bare containers, Any/object last.
        """
        # Most common types first - single identity check each
        if hint is int:
            return isinstance(value, int) and not isinstance(value, bool)
        if hint is str:
            return isinstance(value, str)
        if hint is float:
            return isinstance(value, float)
        if hint is bool:
            return isinstance(value, bool)
        if hint is None or hint is self._NoneType:
            return value is None
        if hint is Any or hint is object:
            return True
        if hint is list:
            return isinstance(value, list)
        if hint is dict:
            return isinstance(value, dict)
        if hint is tuple:
            return isinstance(value, tuple)
        if hint is set:
            return isinstance(value, set)
        if hint is frozenset:
            return isinstance(value, frozenset)
        if hint is bytes:
            return isinstance(value, bytes)
        if hint is bytearray:
            return isinstance(value, bytearray)
        return None

    def _check_type_internal(self, hint: Any, value: Any) -> bool:
        """Recursive type check — includes fast path, no recursion guard."""
        fast_result = self._check_type_fast_path(hint, value)
        if fast_result is not None:
            return fast_result
        return self._check_type_from_plan(hint, value)

    def _check_type_from_plan(self, hint: Any, value: Any) -> bool:
        """Dispatch based on compiled hint plan.

        Called after the fast path already returned None.  All rare hint
        kinds (type_alias, forward_ref, runtime_wrapper) are now handled
        via the cached plan so they cost nothing on repeated calls.
        """
        plan = self._compile_hint(hint)
        kind = plan.kind

        # Ordered by realistic frequency: basic_type and special_form
        # are the most common destinations in recursive element checks.
        if kind == "basic_type":
            return self._check_basic_type(hint, value)
        if kind == "special_form":
            return self._check_special_form_compiled(hint, value, plan)
        if kind == "generic_alias":
            return self._check_generic_alias_compiled(hint, value, plan)
        if kind == "typeddict":
            return self._check_typeddict(hint, value)
        if kind == "protocol":
            return self._check_protocol(hint, value)

        # ── Rare / wrapper kinds (cached — computed once per hint) ──
        if kind == "type_alias":
            return self.check_type(plan.args[0], value)
        if kind == "runtime_wrapper":
            return self._check_type_internal(plan.args[0], value)
        if kind == "forward_ref":
            return self._check_forward_ref(plan.args[0], value)
        if kind == "self":
            return isinstance(value, value.__class__)
        if kind == "generic_class":
            return self._check_generic_typevar(hint, value)
        if kind == "typevar":
            return self._check_typevar(hint, value)

        # String forward references (bare strings as hints)
        if isinstance(hint, str):
            return self._check_forward_ref(hint, value)

        if kind == "newtype":
            return self._check_type_internal(hint.__supertype__, value)

        raise TypeCheckError(f"Unsupported type hint: {hint}")

    def _check_special_form(self, hint, value):
        return self._check_special_form_compiled(hint, value, self._compile_hint(hint))

    def _check_special_form_compiled(self, hint, value, plan: CompiledHint):
        """
        Handle type checking for all special forms.
        
        Args:
            hint: A special form type hint (e.g., Union[int, str], Optional[int])
            value: The value to check
            
        Returns:
            bool: True if the value matches the special form
            
        Raises:
            TypeCheckError: For unsupported or invalid special forms
        """

        # Handle PEP 604 union types (Python 3.10+)
        if self._has_union_type and isinstance(hint, self._union_type):
            return self._check_union(hint, value)
        
        origin = get_origin(hint)
        form_name = plan.special_form_name
        
        # Union and Optional handling
        if form_name == 'Union' or (origin in (typing.Union, Union)):
            return self._check_union(hint, value)
        
        # Optional is a special case of Union[T, None]
        if form_name == 'Optional':
            return self._check_optional(hint,value)
        
        # ClassVar handling
        if form_name == 'ClassVar':
            return self._check_classvar(hint,value)
        
        # Final handling
        if form_name == 'Final':
            return self._check_final(hint,value)
        
        # Literal handling
        if form_name == 'Literal':
            return self._check_literal(hint,value)
        
        # TypeGuard handling (Python 3.10+)
        if form_name == 'TypeGuard':
            return True  # TypeGuard is a runtime no-op
        
        # ParamSpec handling (Python 3.10+)
        if form_name == 'ParamSpec':
            return True  # ParamSpec is a runtime no-op
        
        # Concatenate handling (Python 3.10+)
        if form_name == 'Concatenate':
            return True  # Concatenate is a runtime no-op
        
        # Annotated handling (Python 3.9+)
        if form_name == 'Annotated':
            return self._check_annotated(hint, value)

        # LiteralString behaves like str at runtime.
        if form_name == 'LiteralString':
            return isinstance(value, str)

        # Never/NoReturn are uninhabited at runtime.
        if form_name in {'Never', 'NoReturn'}:
            return False

        # Unknown special form
        raise TypeCheckError(f"Unsupported special form: {form_name}")

    def _check_generic_alias(self,hint,value):
        return self._check_generic_alias_compiled(hint, value, self._compile_hint(hint))

    def _check_generic_alias_compiled(self, hint, value, plan: CompiledHint):
        origin = plan.origin

        if plan.parameterized_generic:
            return self._check_generic_typevar(hint, value)

        # Direct dict dispatch — avoids getattr + string formatting per call
        if plan.checker_kind is not None:
            checker = self._checker_by_origin.get(origin)
            if checker is not None:
                return checker(hint, value)
            checker = getattr(self, f"_check_{plan.checker_kind}", None)
            if checker is not None:
                return checker(hint, value)

        if isinstance(origin, typing.Generic):
            return self._check_generic_typevar(hint, value)

        if origin is not None:
            if self._is_special_origin(origin):
                return self._check_special_form(hint, value)
            return self._check_basic_type(origin, value)

        if plan.hint_origin is not None:
            if self._is_special_origin(plan.hint_origin):
                return self._check_special_form(hint, value)
            return self._check_basic_type(plan.hint_origin, value)

        raise TypeCheckError(f"Unsupported generic alias: {hint}")

    def _get_checker(self, origin):
        """
        Get the appropriate checker method for a type registered in self.type_checkers.
        Handles both standard typing types and their corresponding collections.abc's.
        
        Args:
            origin: The origin type to find a checker for
            
        Returns:
            function or None: The checker method for the origin, or None if not found
        """
        return self._checker_by_origin.get(origin)

    #endregion

    #region: Generic type checkers

    def _check_typeddict(self, hint, value):
        """
        Check if a value matches a TypedDict type hint.
        
        Args:
            hint: A TypedDict type hint
            value: The value to check
            
        Returns:
            bool: True if the value is a dict with the expected keys and value types
        """
        if not isinstance(value, dict):
            return False
        
        annotations = getattr(hint, "__annotations__", {})
        required_keys = self._typed_dict_required_keys(hint)
        
        # Check if all required keys are present
        for key in required_keys:
            if key not in value:
                return False
        
        # Check that all values match their expected types
        for key, val in value.items():
            if key in annotations:
                expected_type = self._unwrap_runtime_wrapper(annotations[key])
                
                # Check if the value matches the expected type
                if not self._check_type_internal(expected_type, val):
                    return False
        
        return True

    def _check_collection_like(self, hint, value):
        """
        Check if a value matches the Collection protocol.
        Collection = Sized + Iterable + Container.

        Runtime note:
            if a value is both a Collection and an Iterator, element inspection is
            skipped to avoid consuming it.
        
        Args:
            hint: The Collection type hint
            value: The value to check
            
        Returns:
            bool: True if value matches Collection protocol and its elements
        """
        origin=get_origin(hint) or hint
        args = get_args(hint)

        if not isinstance(value, self._origin_to_type(origin)):
            return False
            
        if len(args) != 1:
            raise TypeCheckError("Collection requires exactly 1 type argument")
            
        elem_type = args[0]
        
        # If it's an iterator, we can't safely check elements
        if isinstance(value, collections.abc.Iterator):
            return True
            
        # Check each element
        return all(self._check_type_internal(elem_type, item) for item in value)

    def _check_container_like(self, hint, value):
        """
        Check if a value matches the Container protocol.
        Container just requires ``__contains__``.

        Runtime note:
            the element type argument cannot be validated soundly without probing
            arbitrary candidate values, so this check is intentionally
            interface-only.
        
        Args:
            hint: The Container type hint
            value: The value to check
            
        Returns:
            bool: True if value is a container
        """
        origin=get_origin(hint) or hint
        args = get_args(hint)

        if not isinstance(value, self._origin_to_type(origin)):
            return False
            
        args = get_args(hint)
        if len(args) != 1:
            raise TypeCheckError("Container requires exactly 1 type argument")
        
        # We can't reliably check what the container can contain
        # without trying every possible value, so we just check it's a container
        return True

    def _check_mapping_view(self, hint, value):
        """
        Check if a value matches a mapping view type (KeysView, ItemsView, or ValuesView).

        Runtime note:
            view element types are intentionally not inspected. The checker only
            validates the view interface itself.
        
        Args:
            hint: The mapping view type hint
            value: The value to check
            
        Returns:
            bool: True if value matches the view type and its elements
        """
        
        origin=get_origin(hint) or hint
        args = get_args(hint)

        if not isinstance(value, self._origin_to_type(origin)):
            return False
            
        args = get_args(hint)
        
        # KeysView and ValuesView take one type argument
        if origin in (typing.KeysView, typing.ValuesView):
            if len(args) != 1:
                raise TypeCheckError(f"{origin._name} requires exactly 1 type argument")
                
            # We can't reliably check the elements without consuming the view
            # or accessing the underlying mapping
            return True
            
        # ItemsView takes two type arguments (key type and value type)
        if origin == typing.ItemsView:
            if len(args) != 2:
                raise TypeCheckError("ItemsView requires exactly 2 type arguments")
                
            # Similarly, we can't reliably check the elements
            return True
        
        return True

    def _check_type_type(self, hint, value):
        """
        Check ``type[T]`` / ``Type[T]`` hints.

        A matching value must itself be a class object. When a parameter is
        present, the class must be a subtype of the expected target.
        """
        if not isinstance(value, type):
            return False

        args = get_args(hint)
        if not args:
            return True
        if len(args) != 1:
            raise TypeCheckError(f"Type requires exactly 0 or 1 type arguments, got {len(args)}")

        expected_type = self._unwrap_runtime_wrapper(args[0])
        if expected_type in (Any, object):
            return True

        return self._is_annotation_subtype(value, expected_type)

    def _check_tuple_like(self, hint, value):
        """
        Check if a value matches a generic tuple-like type.
        Tuples are special as they can be either homogeneous (Tuple[int, ...]) 
        or heterogeneous (Tuple[int, str, bool]).
        
        Args:
            hint: A generic tuple-like type
            value: The value to check
            
        Returns:
            bool: True if value matches the tuple type specification
        """

        origin=get_origin(hint) or hint
        args = get_args(hint)

        if not isinstance(value, self._origin_to_type(origin)):
            return False
        
        # Empty tuple - Tuple[()]
        if len(args) == 1 and args[0] == ():
            return len(value) == 0
                
        # Variable length tuple - Tuple[int, ...]
        if len(args) == 2 and args[1] is ...:
            elem_type = args[0]
            return all(self._check_type_internal(elem_type, item) for item in value)
                
        # Fixed length tuple - Tuple[int, str, bool]
        if len(value) != len(args):
            return False
                
        return all(self._check_type_internal(args[i], value[i]) 
                for i in range(len(value)))
    
    def _check_sequence_like(self, hint, value):
        """
        Base method for checking homogeneous sequence-like collections.
        Used for List, Sequence, MutableSequence, etc.
        """
        origin=get_origin(hint) or hint
        args = get_args(hint)

        if not isinstance(value, self._origin_to_type(origin)):
            return False

        if len(args) != 1:
            raise TypeCheckError(f"Sequence type requires exactly 1 type argument")

        elem_type = args[0]

        # Handle iterators specially - don't consume them
        if isinstance(value, collections.abc.Iterator):
            return True

        # Inline fast checks for common element types to avoid per-element
        # function call overhead (_check_type_internal → _check_type_fast_path).
        if elem_type is int:
            return all(isinstance(v, int) and not isinstance(v, bool) for v in value)
        if elem_type is str:
            return all(isinstance(v, str) for v in value)
        if elem_type is float:
            return all(isinstance(v, float) for v in value)
        if elem_type is bool:
            return all(isinstance(v, bool) for v in value)

        return all(self._check_type_internal(elem_type, item) for item in value)

    def _check_set_like(self, hint, value):
        """
        Base method for checking set-like collections (unordered, unique elements).
        Used for Set, MutableSet, FrozenSet, etc.
        """
        origin=get_origin(hint) or hint
        args = get_args(hint)

        if not isinstance(value, self._origin_to_type(origin)):
            return False

        if len(args) != 1:
            raise TypeCheckError(f"Set type requires exactly 1 type argument")

        elem_type = args[0]

        if not value:
            return True

        # Inline fast checks for common element types
        if elem_type is int:
            return all(isinstance(v, int) and not isinstance(v, bool) for v in value)
        if elem_type is str:
            return all(isinstance(v, str) for v in value)

        return all(self._check_type_internal(elem_type, item) for item in value)
    
    def _check_mapping_like(self, hint, value):
        """
        Base method for checking mapping-like collections (key-value pairs).
        Used for Dict, Mapping, MutableMapping, etc.
        """
        origin=get_origin(hint) or hint
        args = get_args(hint)

        if not isinstance(value, self._origin_to_type(origin)):
            return False

        if len(args) != 2:
            raise TypeCheckError(f"Mapping type requires exactly 2 type arguments")

        key_type, value_type = args

        if not value:
            return True

        # Inline fast checks for the most common pattern: dict[str, <basic>]
        if key_type is str:
            if value_type is int:
                return all(
                    isinstance(k, str) and isinstance(v, int) and not isinstance(v, bool)
                    for k, v in value.items()
                )
            if value_type is str:
                return all(isinstance(k, str) and isinstance(v, str) for k, v in value.items())
            if value_type is float:
                return all(isinstance(k, str) and isinstance(v, float) for k, v in value.items())
            # str keys, complex value type
            _check = self._check_type_internal
            return all(isinstance(k, str) and _check(value_type, v) for k, v in value.items())

        return all(
            self._check_type_internal(key_type, k) and
            self._check_type_internal(value_type, v)
            for k, v in value.items()
        )

    def _check_iterable_like(self, hint, value):
        """
        Check if a value matches a generic iterable type.
        For non-iterator iterables (like lists, sets), validates all elements.
        For iterators, only checks the type without validating elements.
        
        Args:
            hint: A generic iterable type (e.g., Iterable[int])
            value: The value to check
            
        Returns:
            bool: True if the value is an iterable with elements matching the element type
                For iterators, only checks that it's an iterator without validating elements
        """
        origin=get_origin(hint) or hint
        args = get_args(hint)

        if not isinstance(value, self._origin_to_type(origin)):
            return False
                
        if len(args) != 1:
            raise TypeCheckError(f"Iterable requires exactly 1 type argument, got {len(args)}")
                
        elem_type = args[0]
        
        # If it's an iterator, we can't safely check elements without consuming it
        if isinstance(value, collections.abc.Iterator):
            return True  # Only check that it's an iterator, not what it yields
        
        # For non-iterator iterables (lists, sets, etc.), check all elements
        try:
            for item in value:
                if not self._check_type_internal(elem_type, item):
                    return False
            return True
        except TypeError:
            # Fall back to just validating it's an iterable
            return True

    def _check_iterator_like(self, hint, value):
        """
        Check if a value matches a generic iterator type.
        Only validates that the object is an iterator, not what it yields.
        
        Args:
            hint: A generic iterator type (e.g., Iterator[int])
            value: The value to check
            
        Returns:
            bool: True if the value is an iterator (element types are not validated)
        """
        origin=get_origin(hint) or hint
        args = get_args(hint)

        if not isinstance(value, self._origin_to_type(origin)):
            return False
                
        if len(args) != 1:
            raise TypeCheckError(f"Iterator requires exactly 1 type argument, got {len(args)}")
        
        # We intentionally don't validate iterator elements to avoid consuming the iterator
        return True

    #endregion

    #region: Special form checkers

    def _check_union(self, hint, value):
        """
        Check if a value matches any type in a Union.
        
        Args:
            hint: A Union type hint (e.g., Union[int, str])
            value: The value to check
            
        Returns:
            bool: True if the value matches any type in the Union
            
        Raises:
            TypeCheckError: If the Union has no type arguments
        """
        args = get_args(hint)
        if not args:
            raise TypeCheckError("Union requires at least one type argument")
        for arg in args:
            if self._check_type_internal(arg, value):
                return True
        return False

    def _check_optional(self, hint, value):
        """
        Check if a value matches an Optional type hint.
        Optional[X] is equivalent to Union[X, None].
        
        Args:
            hint: An Optional type hint
            value: The value to check
            
        Returns:
            bool: True if the value is None or matches the type argument
            
        Raises:
            TypeCheckError: If the Optional has invalid arguments
        """
        args = get_args(hint)
        if len(args) != 1:
            raise TypeCheckError(f"Optional requires exactly 1 type argument, got {len(args)}")
        
        if value is None:
            return True
            
        return self._check_type_internal(args[0], value)

    def _check_classvar(self, hint, value):
        """
        Check if a value matches a ClassVar type hint.
        ClassVar[X] checks against the underlying type X.
        
        Args:
            hint: A ClassVar type hint
            value: The value to check
            
        Returns:
            bool: True if the value matches the type X in ClassVar[X]
            
        Raises:
            TypeCheckError: If the ClassVar has invalid arguments
        """
        args = get_args(hint)
        if len(args) != 1:
            raise TypeCheckError(f"ClassVar requires exactly 1 type argument, got {len(args)}")
        
        # Just check against the contained type - don't try to use isinstance with ClassVar
        return self._check_type_internal(args[0], value)

    def _check_final(self, hint, value):
        """
        Check if a value matches a Final type hint.
        Final without arguments accepts any value, Final[X] checks against type X.
        
        Args:
            hint: A Final type hint
            value: The value to check
            
        Returns:
            bool: True if the value matches the Final type
            
        Raises:
            TypeCheckError: If the Final has invalid arguments
        """
        args = get_args(hint)
        if not args:
            return True  # Final without args accepts any value
            
        if len(args) != 1:
            raise TypeCheckError(f"Final requires exactly 0 or 1 type arguments, got {len(args)}")
            
        return self._check_type_internal(args[0], value)

    def _check_literal(self, hint, value):
        """
        Check if a value matches a Literal type hint.
        Literal[x, y, z] accepts only the exact values x, y, or z.
        
        Args:
            hint: A Literal type hint
            value: The value to check
            
        Returns:
            bool: True if the value is one of the literal values
        """
        args = get_args(hint)
        return any(self._literal_values_equal(value, literal) for literal in args)
    
    def _check_forward_ref(self,hint,value):
        """
        Check if a value matches a forward reference type hint.
        Attempts to resolve the string-based type reference in appropriate scopes.
        
        Args:
            hint: A string representing a forward reference type
            value: The value to check
            
        Returns:
            bool: True if the value matches the resolved type
            
        Raises:
            TypeCheckError: If the forward reference cannot be resolved
        """
        frame = inspect.currentframe()
        try:
            resolved_type = self._resolve_forward_ref(hint, frame.f_back)
            # Re-enter through the guarded public entry point so recursive aliases
            # can short-circuit safely on repeated (hint, value) pairs.
            return self.check_type(resolved_type, value)
        finally:
            del frame  # Avoid reference cycles

    def _check_annotated(self,hint,value):
        """
        Check if a value matches an Annotated type hint.
        Only checks against the first type argument, ignoring metadata.
        
        Args:
            hint: An Annotated type hint
            value: The value to check
            
        Returns:
            bool: True if the value matches the base type
            
        Raises:
            TypeCheckError: If the Annotated has no type arguments
        """
        args = get_args(hint)
        if not args:
            raise TypeCheckError("Annotated requires at least one type argument")
        return self._check_type_internal(args[0], value)

    
    def _check_typevar(self,hint,value):
        """
        Check if a value matches a TypeVar.
        Handles TypeVars with constraints, bounds, or neither.
        
        Args:
            hint: A TypeVar
            value: The value to check
            
        Returns:
            bool: True if the value matches the TypeVar's constraints/bounds
        """
        # If TypeVar has constraints, check against those
        if hint.__constraints__:
            return any(self._check_type_internal(constraint, value) 
                    for constraint in hint.__constraints__)
        # If TypeVar has a bound, check against that
        if hint.__bound__:
            return self._check_type_internal(hint.__bound__, value)
        # Otherwise, accept any value (just like Any)
        return True


    def _get_abc_checker(self,origin):
        """
        Find the appropriate checker method for a type that might inherit from an ABC.
        Walks up the MRO chain to find any registered ABC base classes and returns 
        their corresponding checker method.
        
        Args:
            origin: The origin type to find a checker for
                Could be a custom collection type inheriting from ABC classes
                e.g., MySequence that inherits from collections.abc.Sequence
        
        Returns:
            function or None: The checker method for the ABC base class if found,
                None if no matching ABC base class is found
                
        Examples:
            For a custom sequence class:
            >>> class MySequence(collections.abc.Sequence, Generic[T]): ...
            The method would:
            1. Find Sequence in the MRO
            2. Map it to collections.abc.Sequence in origin_to_type_map
            3. Return the sequence checker method from type_checkers
        """
        if isinstance(origin, type):
            for base in origin.__mro__[1:]:  # Skip self
                checker = self._get_checker(base)
                if checker is not None:
                    return checker
        return None

    def _substitute_typevars(self, hint, typevar_map):
        """
        Substitute TypeVars in a type hint with their concrete types.
        
        Args:
            hint: The type hint that may contain TypeVars
            typevar_map: A mapping from TypeVars to their concrete types
        
        Returns:
            A type hint with TypeVars replaced by their concrete types
        """
        # If hint is a TypeVar directly, substitute it
        if isinstance(hint, TypeVar) and hint in typevar_map:
            return typevar_map[hint]
        
        # If hint is not a generic, return it as is
        origin = get_origin(hint)
        if origin is None:
            return hint
        
        # Get the arguments of the generic
        args = get_args(hint)
        if not args:
            return hint
        
        # Substitute TypeVars in the arguments
        new_args = tuple(self._substitute_typevars(arg, typevar_map) for arg in args)
        
        # Reconstruct the generic with substituted arguments
        try:
            return origin[new_args]
        except (TypeError, IndexError):
            # If reconstruction fails, return the original hint
            return hint

    def _check_generic_class_attributes(self, origin, expected_args, value):
        """
        Check if a generic class instance's attributes match the expected types
        based on the class's type annotations, including inherited annotations.
        
        Args:
            origin: The origin type (the generic class itself)
            expected_args: The expected type arguments for the generic class
            value: The instance to check
        
        Returns:
            bool: True if all annotated attributes match their expected types
        """
        # Get the TypeVars from the class definition
        typevars = getattr(origin, "__parameters__", [])
        
        # If there are no TypeVars, there's nothing to check
        if not typevars:
            return True
        
        # Collect annotations from the class and its bases
        all_annotations = {}
        
        # Start with the class itself
        if hasattr(origin, "__annotations__"):
            all_annotations.update(origin.__annotations__)
        
        # Get annotations from base classes
        for base in getattr(origin, "__mro__", [])[1:]:  # Skip self
            if hasattr(base, "__annotations__"):
                # Only add annotations we don't already have
                for name, type_hint in base.__annotations__.items():
                    if name not in all_annotations:
                        all_annotations[name] = type_hint
        
        # Create a mapping of TypeVars to their concrete types
        typevar_map = {tv: expected_args[i] for i, tv in enumerate(typevars) if i < len(expected_args)}
        
        # For each annotation, check the attribute
        for attr_name, attr_type in all_annotations.items():
            # If the attribute exists, check its type
            if hasattr(value, attr_name):
                attr_value = getattr(value, attr_name)
                
                # Substitute TypeVars with their concrete types in the attribute's type
                concrete_type = self._substitute_typevars(attr_type, typevar_map)
                
                # Check if the attribute's value matches the concrete type
                if not self._check_type_internal(concrete_type, attr_value):
                    return False
        
        # Handle inherited generic classes
        # For example, if SubBox inherits from MultiBox[T, str, bool]
        # we need to map T -> the actual type from expected_args
        
        # Get the bases of the class with type arguments
        for base_with_args in getattr(origin, "__orig_bases__", []):
            base_origin = get_origin(base_with_args)
            if base_origin is None:
                continue
            
            # Get the base class's TypeVars
            base_typevars = getattr(base_origin, "__parameters__", [])
            if not base_typevars:
                continue
                
            # Get the type arguments of the base as used in the class definition
            base_args = get_args(base_with_args)
            if not base_args:
                continue
            
            # Create a mapping from base TypeVars to actual types
            typevar_map = {}
            
            for i, base_arg in enumerate(base_args):
                if isinstance(base_arg, TypeVar):
                    if base_arg in typevars:
                        # This is one of our class's TypeVars (e.g., T in SubBox(MultiBox[T, str, bool]))
                        typevar_index = typevars.index(base_arg)
                        if typevar_index < len(expected_args):
                            # Map this TypeVar to the actual type from expected_args
                            typevar_map[base_arg] = expected_args[typevar_index]
                else:
                    # This is a concrete type (e.g., str, bool)
                    if i < len(base_typevars):
                        # Map the base class's TypeVar to this concrete type
                        typevar_map[base_typevars[i]] = base_arg
            
            # Check base class attributes with the mapped types
            for attr_name, attr_type in getattr(base_origin, "__annotations__", {}).items():
                if isinstance(attr_type, TypeVar) and attr_type in typevar_map:
                    expected_type = typevar_map[attr_type]
                    
                    # Check if the attribute exists
                    if hasattr(value, attr_name):
                        attr_value = getattr(value, attr_name)
                        
                        # Check if the attribute's value matches the expected type
                        if not self._check_type_internal(expected_type, attr_value):
                            return False
        
        return True

    def _check_generic_typevar(self, hint, value):
        """
        Check if a value matches a Generic type with TypeVar parameters.
        Handles both custom collection types and simple generic classes.
        
        The method handles several cases:
        1. Custom collection types inheriting from ABCs (e.g., MySequence[int])
        - Uses ABC checkers to validate both the protocol and element types
        2. Simple generic classes with value attributes (e.g., Box[int])
        - Checks the .value attribute against the type parameter
        3. Generic classes with original type info (e.g., through __orig_class__)
        - Compares actual type args against expected ones
        
        Args:
            hint: A Generic type with optional type parameters
                Examples: Box[int], MySequence[str], Container[float]
            value: The value to check against the generic type
        
        Returns:
            bool: True if the value matches the generic type and its parameters
                For collection types: must match both the protocol and element types
                For simple generics: must match the class and type parameters
        
        Examples:
            >>> class MySequence(Sequence, Generic[T]): ...
            >>> seq = MySequence([1, 2, 3])
            >>> _check_generic_typevar(MySequence[int], seq)  # Uses sequence checker
            True
            
            >>> class Box(Generic[T]):
            ...     def __init__(self, value: T): self.value = value
            >>> box = Box(42)
            >>> _check_generic_typevar(Box[int], box)  # Checks value attribute
            True
        """
        # Get the origin type (e.g., Box from Box[int])
        origin = get_origin(hint)
        
        if origin is None:
            origin = hint
        
        # First, check if the value is an instance of the origin
        is_instance = self._check_basic_type(origin,value)
        
        if not is_instance:
            return False
        
        # Get the expected type arguments
        expected_args = get_args(hint)
        
        if not expected_args:
            return True  # No type arguments to check

        # Check if this is a custom collection type by looking for ABC bases
        if (checker:=self._get_abc_checker(origin)) is not None:
            return checker(hint,value)

        # Get the actual type arguments from the value's class or instance
        actual_args = []
        
        # Try multiple ways to get the type arguments
        if hasattr(value, "__orig_class__"):
            actual_args = get_args(value.__orig_class__)
        
        if not actual_args and hasattr(value.__class__, "__orig_class__"):
            actual_args = get_args(value.__class__.__orig_class__)
        
        # Check the attributes based on annotations
        if not self._check_generic_class_attributes(origin, expected_args, value):
            return False
        
        # If we have actual type arguments, compare them with expected
        if actual_args:
            if len(expected_args) != len(actual_args):
                return False
            
            for expected, actual in zip(expected_args, actual_args):
                if expected != actual:
                    # Allow subclass relationship
                    is_subclass = (isinstance(expected, type) and 
                                isinstance(actual, type) and 
                                issubclass(actual, expected))
                    
                    if not is_subclass:
                        return False
        
        # If we get here, either:
        # 1. We couldn't determine actual args but the value attribute passed
        # 2. We compared actual args and they matched
        return True

    def _check_callable(self,hint,value):
        """
        Check if a value matches a Callable type with specific argument and return types.
        
        Args:
            hint: The Callable hint, without or without signature parameters
            value: The value to check
            
        Returns:
            bool: True if value is callable with the specified signature
        """
        if not callable(value):
            return False
        
        args=get_args(hint)

        # If no arguments provided (plain Callable), accept any callable
        if not args:
            return True

        # Callable should have exactly two arguments: parameter types and return type
        if len(args) != 2:
            raise TypeCheckError(f"Callable requires 2 arguments, got {len(args)}")

        arg_types, return_type = args

        # Handle Callable[..., X] case (ellipsis means any arguments)
        if arg_types is ...:
            # We can't reliably check the signature but can check return annotation
            try:
                sig = inspect.signature(value)
                actual_return = sig.return_annotation
                
                # If function doesn't specify return type, accept it
                if actual_return == inspect.Parameter.empty:
                    return True
                    
                # Otherwise check if return type is compatible
                return self._is_annotation_subtype(actual_return, return_type)
            except (ValueError, TypeError):
                # If we can't get the signature, be lenient
                return True

        # For regular Callable[[arg_types], return_type], check parameters and return
        try:
            sig = inspect.signature(value)
        except (ValueError, TypeError):
            # Can't inspect the function, be lenient
            return True

        # Get relevant parameters (skip *args, **kwargs)
        params = [
            p for p in sig.parameters.values()
            if p.kind in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.KEYWORD_ONLY
            )
        ]

        # Check number of parameters matches
        if len(params) != len(arg_types):
            return False

        # Check each parameter type if annotation is present
        for i, (param, expected_type) in enumerate(zip(params, arg_types)):
            if param.annotation != inspect.Parameter.empty:
                # Callable parameters are contravariant: the implementation must
                # accept at least the expected input domain.
                if not self._is_annotation_subtype(expected_type, param.annotation):
                    return False

        # Check return type if annotation is present
        actual_return = sig.return_annotation
        if actual_return != inspect.Parameter.empty:
            if not self._is_annotation_subtype(actual_return, return_type):
                return False

        return True

    def _compare_type_annotations(self, actual, expected):
        """
        Compare two annotations using the checker subtype relation.
        
        Args:
            actual: The actual type annotation
            expected: The expected type annotation
            
        Returns:
            bool: True if the actual type is compatible with the expected type
        """
        return self._is_annotation_subtype(actual, expected)

    def _check_protocol(self, hint, value):
        """
        Check if a value implements a Protocol.
        
        Args:
            hint: A Protocol type (must be runtime_checkable for isinstance checks)
            value: The value to check
            
        Returns:
            bool: True if value implements the Protocol
        """
        # For runtime_checkable protocols, probe isinstance() only to benefit from
        # the runtime's own fast-paths, but do not trust a positive result as the
        # final answer on older Python versions. Python 3.10/3.11 can accept
        # protocols with non-method members too loosely, so we always validate the
        # declared members structurally below.
        if getattr(hint, "_is_runtime_protocol", False):
            try:
                isinstance(value, hint)
            except TypeError:
                # Python < 3.12 may refuse isinstance() on runtime protocols
                # that declare non-method members. Fall back to explicit member checks.
                pass

        # Then validate the members explicitly declared by the protocol itself.
        protocol_members = self._protocol_members(hint)

        for name, expected in protocol_members.items():
            if not hasattr(value, name):
                return False

            attr_value = value if name == "__call__" and callable(value) else getattr(value, name)

            if callable(expected) and not isinstance(expected, type):
                if not callable(attr_value):
                    return False
                expected_hint = self._callable_hint_from_callable(expected, drop_first_parameter=True)
                if not self._check_type_internal(expected_hint, attr_value):
                    return False
                continue

            if expected is not Any and not self._check_type_internal(expected, attr_value):
                return False

        return True
    #endregion

    #region: Utilities

    def _resolve_forward_ref(self, hint: str, frame) -> Any:
        """
        Resolve a forward reference string to an actual type.
        Searches progressively wider scopes starting from the local frame.
        
        Args:
            hint: A string representing a forward reference type
            frame: The execution frame to start resolution from
            
        Returns:
            The resolved type
            
        Raises:
            TypeCheckError: If the forward reference cannot be resolved
        """
        # Try progressively wider scopes
        while frame:
            try:
                # Try locals first
                if frame.f_locals:
                    return eval(hint, frame.f_globals, frame.f_locals)
                # Then try globals
                return eval(hint, frame.f_globals)
            except (NameError, AttributeError):
                frame = frame.f_back
                
        raise TypeCheckError(f"Could not resolve forward reference: {hint}")

    #endregion

#endregion
