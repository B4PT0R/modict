from ._typechecker import TypeChecker, TypeMismatchError, TypeCheckError
from typing import Any, Dict, List, Set, Tuple, Union, Optional, Callable, TypeVar, get_origin, get_args

import collections
import collections.abc
import types

class CoercionError(Exception):
    """Exception raised when coercion is not possible."""
    pass

#region: Coercer Class

class Coercer:
    """
    Smart coercion system built on top of the existing TypeChecker.
    Uses type analysis to determine possible coercions.
    """
    
    def __init__(self, type_checker: TypeChecker):
        self.type_checker = type_checker
        self._active_coercions: set[tuple[int, int]] = set()
        self._coercion_strategies = self._build_coercion_strategies()
        self._canonical_containers = self._build_canonical_containers()
    
    def coerce(self, value: Any, target_hint: Any) -> Any:
        """
        Main entry point: attempts to coerce value to target_hint.
        """
        guard_key = (id(value), id(target_hint))
        if guard_key in self._active_coercions:
            raise CoercionError(f"Recursive coercion detected for {target_hint!r}")
        try:
            self._active_coercions.add(guard_key)
            # If already compatible, no coercion needed
            try:
                if self.type_checker.check_type(target_hint, value):
                    return value
            except (TypeMismatchError, TypeCheckError):
                pass

            # Otherwise, attempt smart coercion
            return self._attempt_smart_coercion(value, target_hint)
        finally:
            self._active_coercions.discard(guard_key)
    
    def _attempt_smart_coercion(self, value: Any, target_hint: Any) -> Any:
        """
        Smart coercion based on TypeChecker analysis.
        """
        # Use TypeChecker analysis to identify the target type

        # Forward references (strings) — resolve first
        if isinstance(target_hint, str):
            return self._coerce_forward_ref(value, target_hint)
        elif self.type_checker._is_forward_ref_hint(target_hint):
            return self._coerce_forward_ref(value, self.type_checker._unwrap_forward_ref_hint(target_hint))
        elif self.type_checker._is_type_alias_hint(target_hint):
            return self.coerce(value, self.type_checker._unwrap_type_alias_hint(target_hint))
        elif self.type_checker._is_runtime_wrapper(target_hint):
            return self.coerce(value, self.type_checker._unwrap_runtime_wrapper(target_hint))
        elif self.type_checker._is_protocol(target_hint):
            raise CoercionError(f"Cannot coerce {type(value)} to protocol {target_hint}")
        elif self.type_checker._is_typeddict(target_hint):
            return self._coerce_typeddict(value, target_hint)
        elif self.type_checker._is_newtype(target_hint):
            return self._coerce_newtype(value, target_hint)
        elif self.type_checker._is_special_form(target_hint):
            return self._coerce_special_form(value, target_hint)
        elif self.type_checker._is_generic_alias(target_hint):
            return self._coerce_generic_alias(value, target_hint)
        elif self.type_checker._is_basic_type(target_hint):
            return self._coerce_basic_type(value, target_hint)
        elif isinstance(target_hint, TypeVar):
            return self._coerce_typevar(value, target_hint)
        else:
            # Fall back to standard coercions
            return self._fallback_coercion(value, target_hint)
            
    def _coerce_special_form(self, value: Any, target_hint: Any) -> Any:
        """
        Coercion for Union, Optional, Literal, etc.
        Reuses TypeChecker analysis logic.
        """
        if hasattr(types, "UnionType") and isinstance(target_hint, types.UnionType):
            return self._coerce_union(value, target_hint)

        form_name = self.type_checker._get_special_form_name(target_hint)
        
        if form_name == 'Union':
            return self._coerce_union(value, target_hint)
        elif form_name == 'Optional':
            return self._coerce_optional(value, target_hint)
        elif form_name == 'Literal':
            return self._coerce_literal(value, target_hint)
        elif form_name == 'Annotated':
            args = get_args(target_hint)
            if not args:
                raise CoercionError("Annotated requires at least one type argument")
            return self.coerce(value, args[0])
        elif form_name == 'LiteralString':
            return self._coerce_basic_type(value, str)
        elif form_name in {'Never', 'NoReturn'}:
            raise CoercionError(f"Cannot coerce values to {form_name}")
        elif form_name == 'Final':
            args = get_args(target_hint)
            if args:
                return self.coerce(value, args[0])  # Recurse
            return value
        else:
            raise CoercionError(f"Cannot coerce to special form: {form_name}")
        
    def _coerce_union(self, value: Any, target_hint: Any) -> Any:
        """
        Union: tries each type in order, returns the first that succeeds.
        """
        args = get_args(target_hint)

        # Smart strategy: try exact matches first, then coercions
        for union_type in args:
            try:
                # Check if already compatible
                if self.type_checker.check_type(union_type, value):
                    return value
            except (TypeMismatchError, TypeCheckError):
                continue
        
        # Otherwise, attempt coercions
        for union_type in args:
            try:
                coerced = self.coerce(value, union_type)  # Recursive smart coercion
                # Validate that coercion succeeded
                if self.type_checker.check_type(union_type, coerced):
                    return coerced
            except (CoercionError, TypeMismatchError):
                continue
        
        raise CoercionError(f"Cannot coerce {type(value)} to any type in {target_hint}")

    def _coerce_optional(self, value: Any, target_hint: Any) -> Any:
        """
        Optional[T] = Union[T, None] — delegates to Union.
        """
        if value is None:
            return None
        
        args = get_args(target_hint)
        if not args:
            raise CoercionError("Optional requires exactly 1 type argument")
        
        return self.coerce(value, args[0])  # Recurse toward T

    def _coerce_newtype(self, value: Any, target_hint: Any) -> Any:
        """
        Coercion for NewType: coerce to the supertype then reconstruct.
        """
        supertype = getattr(target_hint, "__supertype__", None)
        if supertype is None:
            raise CoercionError(f"Cannot coerce {type(value)} to {target_hint}")
        coerced = self.coerce(value, supertype)
        return target_hint(coerced)
    
    def _coerce_literal(self, value: Any, target_hint: Any) -> Any:
        """
        Literal[val1, val2, ...]: the value must be exactly one of the literal values.
        """
        args = get_args(target_hint)
        for literal_val in args:
            if self.type_checker._literal_values_equal(value, literal_val):
                return value
        
        # Attempt smart coercion toward each literal value
        for literal_val in args:
            try:
                if isinstance(value, bool) != isinstance(literal_val, bool):
                    continue
                if isinstance(literal_val, (int, float, str, bool)):
                    coerced = self._coerce_basic_type(value, type(literal_val))
                    if self.type_checker._literal_values_equal(coerced, literal_val):
                        return coerced
            except CoercionError:
                continue
        
        raise CoercionError(f"Cannot coerce {value!r} to any literal value in {args}")
    
    def _coerce_generic_alias(self, value: Any, target_hint: Any) -> Any:
        """
        List[int], Dict[str, float], etc.
        Reuses existing checker logic.
        """
        origin = get_origin(target_hint)
        args = get_args(target_hint)
        
        # Use TypeChecker analysis to identify the appropriate checker
        checker = self.type_checker._get_checker(origin)
        
        if checker == self.type_checker._check_sequence_like:
            return self._coerce_sequence_like(value, target_hint, origin, args)
        elif checker == self.type_checker._check_mapping_like:
            return self._coerce_mapping_like(value, target_hint, origin, args)
        elif checker == self.type_checker._check_set_like:
            return self._coerce_set_like(value, target_hint, origin, args)
        elif checker == self.type_checker._check_tuple_like:
            return self._coerce_tuple_like(value, target_hint, origin, args)
        elif checker == self.type_checker._check_type_type:
            return self._coerce_type_type(value, target_hint, origin, args)
        elif checker == self.type_checker._check_iterable_like:
            return self._coerce_iterable_like(value, target_hint, origin, args)
        elif checker == self.type_checker._check_collection_like:
            return self._coerce_iterable_like(value, target_hint, origin, args)
        elif checker == self.type_checker._check_container_like:
            return self._coerce_container_like(value, target_hint, origin, args)
        elif checker == self.type_checker._check_iterator_like:
            return self._coerce_iterator_like(value, target_hint, origin, args)
        elif checker == self.type_checker._check_callable:
            raise CoercionError(f"Cannot coerce {type(value)} to callable {target_hint}")
        else:
            # Use the ABC checker if available
            abc_checker = self.type_checker._get_abc_checker(origin)
            if abc_checker:
                return self._coerce_with_abc_checker(value, target_hint, origin, args)
            
            raise CoercionError(f"No coercion strategy for {target_hint}")

    def _coerce_sequence_like(self, value: Any, target_hint: Any, origin: Any, args: Tuple) -> Any:
        """
        Coercion for List[T], Sequence[T], etc.
        """
        # First, convert to the appropriate container type
        target_type = self.type_checker._origin_to_type(origin)
        canonical_type = self._canonical_containers.get(target_type, target_type)
        preserve_type = isinstance(value, target_type) and not isinstance(value, (str, bytes))
        preferred_type = type(value) if preserve_type else canonical_type
        
        # Convert value to the target sequence type
        if isinstance(value, str):
            # String -> List: special handling
            if canonical_type in (list, collections.abc.Sequence):
                converted = list(value)  # "abc" -> ['a', 'b', 'c']
            else:
                raise CoercionError(f"Cannot coerce string to {target_type}")
        elif hasattr(value, '__iter__') and not isinstance(value, (str, bytes)):
            # Convert iterable -> target type
            try:
                if canonical_type == list:
                    converted = list(value)
                elif canonical_type == tuple:
                    converted = tuple(value)
                elif canonical_type == set:
                    converted = set(value)
                else:
                    # For ABCs, try creating the canonical or origin type
                    try:
                        converted = canonical_type(value)
                    except Exception:
                        try:
                            converted = origin(value)
                        except Exception:
                            converted = list(value)  # Fallback to list
            except Exception as exc:
                raise CoercionError(f"Cannot coerce {type(value)} to sequence") from exc
        else:
            raise CoercionError(f"Cannot coerce {type(value)} to sequence")
        
        # If an element type is specified, coerce recursively
        if args and len(args) == 1:
            elem_type = args[0]
            coerced_elements = []
            for item in converted:
                coerced_item = self.coerce(item, elem_type)  # Recursive coercion
                coerced_elements.append(coerced_item)

            # Reconstruct the correct type
            if preferred_type == list:
                return coerced_elements
            elif preferred_type == tuple:
                return tuple(coerced_elements)
            elif preferred_type == set:
                return set(coerced_elements)
            elif preferred_type is collections.deque and preserve_type:
                return collections.deque(coerced_elements, maxlen=value.maxlen)
            else:
                try:
                    return preferred_type(coerced_elements)
                except Exception:
                    try:
                        return origin(coerced_elements)
                    except Exception:
                        return coerced_elements
        
        return converted

    def _coerce_mapping_like(self, value: Any, target_hint: Any, origin: Any, args: Tuple) -> Any:
        """
        Coercion for Dict[K, V], Mapping[K, V], etc.
        """
        target_type = self.type_checker._origin_to_type(origin)
        canonical_type = self._canonical_containers.get(target_type, target_type)
        preserve_type = isinstance(value, target_type)
        preferred_type = type(value) if preserve_type else canonical_type
        
        # Convert to a dict-like structure
        if hasattr(value, 'items'):
            try:
                converted = dict(value.items())
            except Exception as exc:
                raise CoercionError(f"Cannot coerce {type(value)} to mapping") from exc
        elif hasattr(value, '__iter__'):
            # Try to convert from a sequence of pairs
            try:
                converted = dict(value)
            except Exception as exc:
                raise CoercionError(f"Cannot coerce {type(value)} to mapping") from exc
        else:
            raise CoercionError(f"Cannot coerce {type(value)} to mapping")
        
        # Coerce keys and values if types are specified
        if args and len(args) == 2:
            key_type, value_type = args
            coerced_dict = {}

            for k, v in converted.items():
                coerced_key = self.coerce(k, key_type)     # Recurse
                coerced_val = self.coerce(v, value_type)   # Recurse
                coerced_dict[coerced_key] = coerced_val
            
            converted = coerced_dict
        
        # Build the correct final type
        if preferred_type == dict:
            return converted
        if preferred_type is collections.defaultdict and preserve_type:
            rebuilt = collections.defaultdict(value.default_factory)
            rebuilt.update(converted)
            return rebuilt
        try:
            return preferred_type(converted)
        except Exception:
            try:
                return origin(converted)
            except Exception:
                return converted

    def _coerce_typeddict(self, value: Any, target_hint: Any) -> Any:
        """
        Coercion for TypedDict: coerce annotated values, preserve extra keys.
        """
        if hasattr(value, "items"):
            data = dict(value.items())
        elif hasattr(value, "__iter__"):
            try:
                data = dict(value)
            except (TypeError, ValueError):
                raise CoercionError(f"Cannot coerce {type(value)} to TypedDict")
        else:
            raise CoercionError(f"Cannot coerce {type(value)} to TypedDict")

        annotations = getattr(target_hint, "__annotations__", {}) or {}
        required_keys = self.type_checker._typed_dict_required_keys(target_hint)

        # Ensure required keys are present
        missing = [k for k in required_keys if k not in data]
        if missing:
            raise CoercionError(f"Missing required keys for TypedDict: {missing}")

        # Coerce annotated keys only
        for key, expected_type in annotations.items():
            if key in data:
                data[key] = self.coerce(
                    data[key],
                    self.type_checker._unwrap_runtime_wrapper(expected_type),
                )

        return data

    def _coerce_set_like(self, value: Any, target_hint: Any, origin: Any, args: Tuple) -> Any:
        """
        Coercion for Set[T], FrozenSet[T], etc.
        """
        target_type = self.type_checker._origin_to_type(origin)
        canonical_type = self._canonical_containers.get(target_type, target_type)
        preserve_type = isinstance(value, target_type)
        preferred_type = type(value) if preserve_type else canonical_type
        
        # Convert to set-like
        if isinstance(value, str):
            # String -> Set of chars
            converted = set(value)
        elif hasattr(value, '__iter__'):
            # Convert iterable -> set
            try:
                converted = set(value)
            except Exception as exc:
                raise CoercionError(f"Cannot coerce {type(value)} to set") from exc
        else:
            raise CoercionError(f"Cannot coerce {type(value)} to set")
        
        # If an element type is specified, coerce recursively
        if args and len(args) == 1:
            elem_type = args[0]
            coerced_elements = set()
            for item in converted:
                coerced_item = self.coerce(item, elem_type)  # Recurse
                coerced_elements.add(coerced_item)
            converted = coerced_elements
        
        # Build the correct final type
        if preferred_type == set:
            return converted
        elif preferred_type == frozenset:
            return frozenset(converted)
        try:
            return preferred_type(converted)
        except Exception:
            try:
                return origin(converted)
            except Exception:
                return converted

    def _coerce_iterable_like(self, value: Any, target_hint: Any, origin: Any, args: Tuple) -> Any:
        """
        Coercion for Iterable/Collection to a canonical container (list).
        """
        target_type = self.type_checker._origin_to_type(origin)
        canonical_type = self._canonical_containers.get(target_type, target_type)

        if not hasattr(value, '__iter__'):
            raise CoercionError(f"Cannot coerce {type(value)} to iterable")

        # If it's an iterator, keep laziness by wrapping it.
        if isinstance(value, collections.abc.Iterator):
            yield_type = args[0] if args else None
            def _iter():
                for item in value:
                    yield self.coerce(item, yield_type) if yield_type is not None else item
            return _iter()

        try:
            converted = list(value)
        except Exception as exc:
            raise CoercionError(f"Cannot coerce {type(value)} to iterable") from exc

        if args and len(args) == 1:
            elem_type = args[0]
            converted = [self.coerce(item, elem_type) for item in converted]

        # If the value already matches the target interface, try to preserve its concrete type.
        if isinstance(value, target_type):
            value_type = type(value)
            try:
                return value_type(converted)
            except Exception:
                pass

        if canonical_type == list:
            return converted
        try:
            return canonical_type(converted)
        except Exception:
            try:
                return origin(converted)
            except Exception:
                return converted

    def _coerce_container_like(self, value: Any, target_hint: Any, origin: Any, args: Tuple) -> Any:
        """
        Coercion for Container: attempts simple materialization when possible.
        """
        if not hasattr(value, '__iter__'):
            raise CoercionError(f"Cannot coerce {type(value)} to container")
        return self._coerce_iterable_like(value, target_hint, origin, args)

    def _coerce_iterator_like(self, value: Any, target_hint: Any, origin: Any, args: Tuple) -> Any:
        """
        Coercion for Iterator/Generator with minimal materialization.
        Returns a lazy iterator/generator that only consumes items during iteration.
        """
        target_type = self.type_checker._origin_to_type(origin)

        # If the value is already the correct iterator/generator type, return it as-is.
        if isinstance(value, target_type):
            return value

        if not hasattr(value, '__iter__'):
            raise CoercionError(f"Cannot coerce {type(value)} to iterator")

        yield_type = args[0] if args else None
        iterable = value

        if target_type is collections.abc.Generator:
            def _gen():
                for item in iterable:
                    yield self.coerce(item, yield_type) if yield_type is not None else item
            return _gen()

        # Iterator (or variants): wrap in a generator that optionally coerces items
        def _iter():
            for item in iterable:
                yield self.coerce(item, yield_type) if yield_type is not None else item
        return _iter()

    def _coerce_tuple_like(self, value: Any, target_hint: Any, origin: Any, args: Tuple) -> Any:
        """
        Coercion for Tuple with special-case handling.
        Tuple[int, str, bool] vs Tuple[int, ...] vs Tuple[()]
        """
        target_type = self.type_checker._origin_to_type(origin)
        
        # Materialize to a tuple-friendly iterable first
        if isinstance(value, str):
            converted = tuple(value)  # "abc" -> ('a', 'b', 'c')
        elif hasattr(value, '__iter__'):
            try:
                converted = tuple(value)
            except Exception as exc:
                raise CoercionError(f"Cannot coerce {type(value)} to tuple") from exc
        else:
            raise CoercionError(f"Cannot coerce {type(value)} to tuple")
        
        # Handle tuple special cases
        if not args:
            # Tuple without args = Tuple[Any, ...]
            return converted

        # Empty tuple — Tuple[()]
        if len(args) == 1 and args[0] == ():
            if len(converted) == 0:
                return converted
            else:
                raise CoercionError(f"Expected empty tuple, got {len(converted)} elements")
        
        # Homogeneous tuple — Tuple[int, ...]
        if len(args) == 2 and args[1] is ...:
            elem_type = args[0]
            coerced_elements = []
            for item in converted:
                coerced_item = self.coerce(item, elem_type)
                coerced_elements.append(coerced_item)
            return tuple(coerced_elements)
        
        # Heterogeneous tuple — Tuple[int, str, bool]
        if len(converted) != len(args):
            raise CoercionError(f"Expected tuple of length {len(args)}, got {len(converted)}")
        
        coerced_elements = []
        for i, (item, expected_type) in enumerate(zip(converted, args)):
            coerced_item = self.coerce(item, expected_type)
            coerced_elements.append(coerced_item)
        
        return tuple(coerced_elements)

    def _coerce_type_type(self, value: Any, target_hint: Any, origin: Any, args: Tuple) -> Any:
        """
        Coercion for ``type[T]`` / ``Type[T]``.

        This is intentionally conservative: runtime coercion cannot synthesize a
        class object safely, so only already-compatible class objects are accepted.
        """
        if not isinstance(value, type):
            raise CoercionError(f"Cannot coerce {type(value)} to {target_hint}")

        try:
            if self.type_checker.check_type(target_hint, value):
                return value
        except (TypeMismatchError, TypeCheckError) as e:
            raise CoercionError(f"Cannot coerce {value!r} to {target_hint}") from e

        raise CoercionError(f"Cannot coerce {value!r} to {target_hint}")

    def _coerce_with_abc_checker(self, value: Any, target_hint: Any, origin: Any, args: Tuple) -> Any:
        """
        Coercion for custom types that inherit from ABC.
        """
        # Strategy: use canonical container if available, otherwise fall back to origin
        canonical_type = self._canonical_containers.get(origin, origin)
        try:
            if hasattr(value, '__iter__') and not isinstance(value, (str, bytes)):
                return canonical_type(value)
            else:
                return canonical_type([value])  # Wrap in list if not iterable
        except Exception:
            try:
                if hasattr(value, '__iter__') and not isinstance(value, (str, bytes)):
                    return origin(value)
                return origin([value])
            except Exception:
                raise CoercionError(f"Cannot coerce {type(value)} to {origin}")

    def _coerce_basic_type(self, value: Any, target_hint: Any) -> Any:
        """
        Fast coercion for basic types using pre-built strategies.
        """
        # Use pre-calculated strategies
        coercion_key = (type(value), target_hint)
        
        if coercion_key in self._coercion_strategies:
            strategy = self._coercion_strategies[coercion_key]
            try:
                result = strategy(value)
                if result is not None:  # Strategy may return None if impossible
                    return result
            except Exception:
                pass
        
        # Fall back to more generic strategies
        return self._generic_basic_coercion(value, target_hint)

    def _coerce_typevar(self, value: Any, target_hint: TypeVar) -> Any:
        """
        Coercion for TypeVar with constraints/bounds.
        """
        # If TypeVar has constraints, try coercing to each one
        if target_hint.__constraints__:
            for constraint in target_hint.__constraints__:
                try:
                    return self.coerce(value, constraint)
                except CoercionError:
                    continue
            raise CoercionError(f"Cannot coerce {type(value)} to any constraint of {target_hint}")
        
        # If TypeVar has a bound, coerce to the bound
        if target_hint.__bound__:
            return self.coerce(value, target_hint.__bound__)
        
        # Otherwise, accept the value as-is (like Any)
        return value

    def _coerce_forward_ref(self, value: Any, target_hint: str) -> Any:
        """
        Coercion for forward references (strings).
        Resolves the reference then reruns coercion recursively.
        """
        import inspect
        frame = inspect.currentframe()
        try:
            # Resolve the forward reference to a real type
            resolved_hint = self.type_checker._resolve_forward_ref(target_hint, frame.f_back)
            # Recurse: coerce with the resolved type
            return self.coerce(value, resolved_hint)
        except TypeCheckError as e:
            # If we cannot resolve, raise an error
            raise CoercionError(f"Cannot resolve forward reference '{target_hint}': {e}")
        finally:
            del frame  # Avoid reference cycles

    def _fallback_coercion(self, value: Any, target_hint: Any) -> Any:
        """
        Last-resort coercion for unrecognised types.
        """
        # Try isinstance as a last chance
        if isinstance(target_hint, type):
            try:
                return target_hint(value)
            except Exception:
                pass
        
        raise CoercionError(f"No coercion strategy available for {target_hint}")

    def _build_coercion_strategies(self) -> Dict[Tuple[type, type], Callable]:
        """
        Optimised coercion strategies for common cases.
        """
        return {
            # String to numerics
            (str, int): self._str_to_int,
            (str, float): self._str_to_float,
            (str, bool): self._str_to_bool,
            
            # Numerics to string
            (int, str): str,
            (float, str): str,
            (bool, str): str,
            
            # Numeric conversions
            (int, float): float,
            (float, int): self._float_to_int,
            (bool, int): int,  # True -> 1, False -> 0
            (int, bool): bool, # 0 -> False, else -> True

            # Basic containers
            (tuple, list): list,
            (list, tuple): tuple,
            (set, list): list,
            (list, set): set,
            (frozenset, set): set,
            (set, frozenset): frozenset,
            
            # String to containers
            (str, list): list,  # "abc" -> ['a', 'b', 'c']
            (str, tuple): tuple,
            (str, set): set,
        }

    def _build_canonical_containers(self) -> Dict[type, type]:
        """
        Build a mapping from container/ABC types (as seen by TypeChecker) to their
        least-demanding concrete representative. This is used to materialize
        MutableSequence/Mapping/Set hints into concrete list/dict/set when the
        provided value is a more general iterable/mapping.
        """
        containers: Dict[type, type] = {}
        # Start from every "concrete" type the TypeChecker uses internally
        for concrete in set(self.type_checker.origin_to_type_map.values()):
            containers[concrete] = concrete

        preferred = {
            collections.abc.Sequence: list,
            collections.abc.MutableSequence: list,
            collections.abc.Collection: list,
            collections.abc.Iterable: list,
            collections.abc.Mapping: dict,
            collections.abc.MutableMapping: dict,
            collections.abc.Set: set,
            collections.abc.MutableSet: set,
        }
        containers.update(preferred)
        return containers

    def _str_to_int(self, value: str) -> int:
        """Convert string -> int with error handling."""
        value = value.strip()
        if not value:
            raise CoercionError("Empty string cannot be converted to int")
        
        # Handle cases like "123.0" -> 123
        try:
            if '.' in value:
                float_val = float(value)
                if float_val.is_integer():
                    return int(float_val)
                else:
                    raise CoercionError(f"String '{value}' represents a non-integer float")
            return int(value)
        except ValueError as e:
            raise CoercionError(f"Cannot convert '{value}' to int: {e}")

    def _str_to_float(self, value: str) -> float:
        """Convert string -> float with error handling."""
        value = value.strip()
        if not value:
            raise CoercionError("Empty string cannot be converted to float")
        
        try:
            return float(value)
        except ValueError as e:
            raise CoercionError(f"Cannot convert '{value}' to float: {e}")

    def _str_to_bool(self, value: str) -> bool:
        """Convert string -> bool with smart logic."""
        value = value.strip().lower()

        # Truthy values
        if value in ('true', '1', 'yes', 'on', 'y', 't'):
            return True
        # Falsy values
        elif value in ('false', '0', 'no', 'off', 'n', 'f', ''):
            return False
        else:
            raise CoercionError(f"Cannot convert '{value}' to bool")

    def _float_to_int(self, value: float) -> int:
        """Convert float -> int only if there is no fractional part."""
        if value.is_integer():
            return int(value)
        else:
            raise CoercionError(f"Float {value} has decimal part, cannot convert to int")

    def _generic_basic_coercion(self, value: Any, target_hint: Any) -> Any:
        """
        Generic coercion for basic types not covered by the strategy table.
        """
        if isinstance(target_hint, type):
            try:
                # Attempt direct construction
                return target_hint(value)
            except Exception:
                raise CoercionError(f"Cannot coerce {type(value)} to {target_hint}")
        
        raise CoercionError(f"Cannot coerce {type(value)} to {target_hint}")

#endregion
