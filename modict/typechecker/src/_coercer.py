from ._typechecker import TypeChecker, TypeMismatchError, TypeCheckError
from typing import Any, Dict, List, Set, Tuple, Union, Optional, Callable, TypeVar, get_origin, get_args

import collections
import collections.abc

class CoercionError(Exception):
    """Exception raised when coercion is not possible."""
    pass

#region: Coercer Class

class Coercer:
    """
    Système de coercion intelligent basé sur le TypeChecker existant.
    Utilise l'analyse de types pour déterminer les coercions possibles.
    """
    
    def __init__(self, type_checker: TypeChecker):
        self.type_checker = type_checker
        self._coercion_strategies = self._build_coercion_strategies()
        self._canonical_containers = self._build_canonical_containers()
    
    def coerce(self, value: Any, target_hint: Any) -> Any:
        """
        Point d'entrée principal : tente de coercer value vers target_hint.
        """
        # Si déjà compatible, pas de coercion
        try:
            if self.type_checker.check_type(target_hint, value):
                return value
        except (TypeMismatchError, TypeCheckError):
            pass
        
        # Sinon, tentative de coercion intelligente
        return self._attempt_smart_coercion(value, target_hint)
    
    def _attempt_smart_coercion(self, value: Any, target_hint: Any) -> Any:
        """
        🔥 Coercion intelligente basée sur l'analyse du TypeChecker.
        """
        # Utiliser l'intelligence du TypeChecker pour analyser le type cible

        # Forward references (strings) - à résoudre d'abord
        if isinstance(target_hint, str):
            return self._coerce_forward_ref(value, target_hint)
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
            # Fallback vers coercions standards
            return self._fallback_coercion(value, target_hint)
            
    def _coerce_special_form(self, value: Any, target_hint: Any) -> Any:
        """
        Coercion pour Union, Optional, Literal, etc.
        Réutilise la logique d'analyse du TypeChecker !
        """
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
        elif form_name == 'Final':
            args = get_args(target_hint)
            if args:
                return self.coerce(value, args[0])  # Récursion !
            return value
        else:
            raise CoercionError(f"Cannot coerce to special form: {form_name}")
        
    def _coerce_union(self, value: Any, target_hint: Any) -> Any:
        """
        Union: essaie chaque type dans l'ordre, retourne le premier qui marche.
        """
        args = get_args(target_hint)
        
        # Stratégie intelligente : d'abord les types "exacts", puis les coercions
        for union_type in args:
            try:
                # D'abord vérifier si déjà compatible
                if self.type_checker.check_type(union_type, value):
                    return value
            except (TypeMismatchError, TypeCheckError):
                continue
        
        # Sinon, tenter les coercions
        for union_type in args:
            try:
                coerced = self.coerce(value, union_type)  # Récursion intelligente !
                # Valider que la coercion a marché
                if self.type_checker.check_type(union_type, coerced):
                    return coerced
            except (CoercionError, TypeMismatchError):
                continue
        
        raise CoercionError(f"Cannot coerce {type(value)} to any type in {target_hint}")

    def _coerce_optional(self, value: Any, target_hint: Any) -> Any:
        """
        Optional[T] = Union[T, None] - délègue à Union !
        """
        if value is None:
            return None
        
        args = get_args(target_hint)
        if not args:
            raise CoercionError("Optional requires exactly 1 type argument")
        
        return self.coerce(value, args[0])  # Récursion vers T

    def _coerce_newtype(self, value: Any, target_hint: Any) -> Any:
        """
        Coercion pour NewType : coercer vers le supertype puis reconstruire.
        """
        supertype = getattr(target_hint, "__supertype__", None)
        if supertype is None:
            raise CoercionError(f"Cannot coerce {type(value)} to {target_hint}")
        coerced = self.coerce(value, supertype)
        return target_hint(coerced)
    
    def _coerce_literal(self, value: Any, target_hint: Any) -> Any:
        """
        Literal[val1, val2, ...] : la valeur doit être exactement une des valeurs littérales.
        """
        args = get_args(target_hint)
        if value in args:
            return value
        
        # Tentative de coercion intelligente vers chaque valeur littérale
        for literal_val in args:
            try:
                # Si c'est le même type, essayer une conversion directe
                if type(value) != type(literal_val):
                    if isinstance(literal_val, (int, float, str, bool)):
                        coerced = self._coerce_basic_type(value, type(literal_val))
                        if coerced == literal_val:
                            return coerced
            except CoercionError:
                continue
        
        raise CoercionError(f"Cannot coerce {value!r} to any literal value in {args}")
    
    def _coerce_generic_alias(self, value: Any, target_hint: Any) -> Any:
        """
        List[int], Dict[str, float], etc.
        Réutilise la logique des checkers existants !
        """
        origin = get_origin(target_hint)
        args = get_args(target_hint)
        
        # Utiliser l'intelligence du TypeChecker pour identifier le checker approprié
        checker = self.type_checker._get_checker(origin)
        
        if checker == self.type_checker._check_sequence_like:
            return self._coerce_sequence_like(value, target_hint, origin, args)
        elif checker == self.type_checker._check_mapping_like:
            return self._coerce_mapping_like(value, target_hint, origin, args)
        elif checker == self.type_checker._check_set_like:
            return self._coerce_set_like(value, target_hint, origin, args)
        elif checker == self.type_checker._check_tuple_like:
            return self._coerce_tuple_like(value, target_hint, origin, args)
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
            # Utiliser l'ABC checker si disponible
            abc_checker = self.type_checker._get_abc_checker(origin)
            if abc_checker:
                return self._coerce_with_abc_checker(value, target_hint, origin, args)
            
            raise CoercionError(f"No coercion strategy for {target_hint}")

    def _coerce_sequence_like(self, value: Any, target_hint: Any, origin: Any, args: Tuple) -> Any:
        """
        Coercion pour List[T], Sequence[T], etc.
        """
        # D'abord, convertir vers le type de conteneur approprié
        target_type = self.type_checker._origin_to_type(origin)
        canonical_type = self._canonical_containers.get(target_type, target_type)
        preserve_type = isinstance(value, target_type) and not isinstance(value, (str, bytes))
        preferred_type = type(value) if preserve_type else canonical_type
        
        # Convertir la valeur vers le type de séquence cible
        if isinstance(value, str):
            # String -> List : traitement spécial
            if canonical_type in (list, collections.abc.Sequence):
                converted = list(value)  # "abc" -> ['a', 'b', 'c']
            else:
                raise CoercionError(f"Cannot coerce string to {target_type}")
        elif hasattr(value, '__iter__') and not isinstance(value, (str, bytes)):
            # Convertir iterable -> type cible
            if canonical_type == list:
                converted = list(value)
            elif canonical_type == tuple:
                converted = tuple(value)
            elif canonical_type == set:
                converted = set(value)
            else:
                # Pour les ABC, essayer de créer le type canonique ou d'origine
                try:
                    converted = canonical_type(value)
                except Exception:
                    try:
                        converted = origin(value)
                    except Exception:
                        converted = list(value)  # Fallback vers list
        else:
            raise CoercionError(f"Cannot coerce {type(value)} to sequence")
        
        # Si on a un type d'élément spécifié, coercer récursivement
        if args and len(args) == 1:
            elem_type = args[0]
            coerced_elements = []
            for item in converted:
                coerced_item = self.coerce(item, elem_type)  # 🔥 Récursion intelligente !
                coerced_elements.append(coerced_item)
            
            # Reconstruire le bon type
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
        Coercion pour Dict[K, V], Mapping[K, V], etc.
        """
        target_type = self.type_checker._origin_to_type(origin)
        canonical_type = self._canonical_containers.get(target_type, target_type)
        preserve_type = isinstance(value, target_type)
        preferred_type = type(value) if preserve_type else canonical_type
        
        # Convertir vers dict-like
        if hasattr(value, 'items'):
            converted = dict(value.items())
        elif hasattr(value, '__iter__'):
            # Essayer de convertir depuis une séquence de paires
            try:
                converted = dict(value)
            except (ValueError, TypeError):
                raise CoercionError(f"Cannot coerce {type(value)} to mapping")
        else:
            raise CoercionError(f"Cannot coerce {type(value)} to mapping")
        
        # Coercer les clés et valeurs si types spécifiés
        if args and len(args) == 2:
            key_type, value_type = args
            coerced_dict = {}
            
            for k, v in converted.items():
                coerced_key = self.coerce(k, key_type)     # 🔥 Récursion !
                coerced_val = self.coerce(v, value_type)   # 🔥 Récursion !
                coerced_dict[coerced_key] = coerced_val
            
            converted = coerced_dict
        
        # Créer le bon type final
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
        Coercion pour TypedDict : coercer les valeurs annotées, conserver les clés extra.
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
        is_total = getattr(target_hint, "__total__", True)

        # Ensure required keys are present
        if is_total:
            missing = [k for k in annotations.keys() if k not in data]
            if missing:
                raise CoercionError(f"Missing required keys for TypedDict: {missing}")

        # Coerce annotated keys only
        for key, expected_type in annotations.items():
            if key in data:
                data[key] = self.coerce(data[key], expected_type)

        return data

    def _coerce_set_like(self, value: Any, target_hint: Any, origin: Any, args: Tuple) -> Any:
        """
        Coercion pour Set[T], FrozenSet[T], etc.
        """
        target_type = self.type_checker._origin_to_type(origin)
        canonical_type = self._canonical_containers.get(target_type, target_type)
        preserve_type = isinstance(value, target_type)
        preferred_type = type(value) if preserve_type else canonical_type
        
        # Convertir vers set-like
        if isinstance(value, str):
            # String -> Set de chars
            converted = set(value)
        elif hasattr(value, '__iter__'):
            # Convertir iterable -> set
            converted = set(value)
        else:
            raise CoercionError(f"Cannot coerce {type(value)} to set")
        
        # Si on a un type d'élément spécifié, coercer récursivement
        if args and len(args) == 1:
            elem_type = args[0]
            coerced_elements = set()
            for item in converted:
                coerced_item = self.coerce(item, elem_type)  # 🔥 Récursion !
                coerced_elements.add(coerced_item)
            converted = coerced_elements
        
        # Créer le bon type final
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
        Coercion pour Iterable/Collection vers un conteneur canonique (list).
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

        converted = list(value)

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
        Coercion pour Container : on tente une matérialisation simple si possible.
        """
        if not hasattr(value, '__iter__'):
            raise CoercionError(f"Cannot coerce {type(value)} to container")
        return self._coerce_iterable_like(value, target_hint, origin, args)

    def _coerce_iterator_like(self, value: Any, target_hint: Any, origin: Any, args: Tuple) -> Any:
        """
        Coercion pour Iterator/Generator avec matérialisation minimale.
        Renvoie un iterator/generator paresseux et ne consomme que lors de l'itération.
        """
        target_type = self.type_checker._origin_to_type(origin)

        # Si la valeur est déjà le bon type d'iterator/generator, on la retourne telle quelle.
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

        # Iterator (ou variantes) : wrap dans un generator qui coerce éventuellement les items
        def _iter():
            for item in iterable:
                yield self.coerce(item, yield_type) if yield_type is not None else item
        return _iter()

    def _coerce_tuple_like(self, value: Any, target_hint: Any, origin: Any, args: Tuple) -> Any:
        """
        Coercion pour Tuple avec gestion des cas spéciaux.
        Tuple[int, str, bool] vs Tuple[int, ...] vs Tuple[()]
        """
        target_type = self.type_checker._origin_to_type(origin)
        
        # Convertir vers iterable d'abord
        if isinstance(value, str):
            converted = tuple(value)  # "abc" -> ('a', 'b', 'c')
        elif hasattr(value, '__iter__'):
            converted = tuple(value)
        else:
            raise CoercionError(f"Cannot coerce {type(value)} to tuple")
        
        # Gestion des cas spéciaux de tuple
        if not args:
            # Tuple sans args = Tuple[Any, ...]
            return converted
        
        # Tuple vide - Tuple[()]
        if len(args) == 1 and args[0] == ():
            if len(converted) == 0:
                return converted
            else:
                raise CoercionError(f"Expected empty tuple, got {len(converted)} elements")
        
        # Tuple homogène - Tuple[int, ...]
        if len(args) == 2 and args[1] is ...:
            elem_type = args[0]
            coerced_elements = []
            for item in converted:
                coerced_item = self.coerce(item, elem_type)
                coerced_elements.append(coerced_item)
            return tuple(coerced_elements)
        
        # Tuple hétérogène - Tuple[int, str, bool]
        if len(converted) != len(args):
            raise CoercionError(f"Expected tuple of length {len(args)}, got {len(converted)}")
        
        coerced_elements = []
        for i, (item, expected_type) in enumerate(zip(converted, args)):
            coerced_item = self.coerce(item, expected_type)
            coerced_elements.append(coerced_item)
        
        return tuple(coerced_elements)

    def _coerce_with_abc_checker(self, value: Any, target_hint: Any, origin: Any, args: Tuple) -> Any:
        """
        Coercion pour types custom qui héritent d'ABC.
        """
        # Stratégie : utiliser un conteneur canonique si disponible, sinon retomber sur l'origine
        canonical_type = self._canonical_containers.get(origin, origin)
        try:
            if hasattr(value, '__iter__') and not isinstance(value, (str, bytes)):
                return canonical_type(value)
            else:
                return canonical_type([value])  # Wrap en liste si pas iterable
        except Exception:
            try:
                if hasattr(value, '__iter__') and not isinstance(value, (str, bytes)):
                    return origin(value)
                return origin([value])
            except Exception:
                raise CoercionError(f"Cannot coerce {type(value)} to {origin}")

    def _coerce_basic_type(self, value: Any, target_hint: Any) -> Any:
        """
        Coercion rapide pour types basiques avec stratégies optimisées.
        """
        # Utiliser les stratégies pré-calculées
        coercion_key = (type(value), target_hint)
        
        if coercion_key in self._coercion_strategies:
            strategy = self._coercion_strategies[coercion_key]
            try:
                result = strategy(value)
                if result is not None:  # Strategy peut retourner None si impossible
                    return result
            except Exception:
                pass
        
        # Fallback vers stratégies plus génériques
        return self._generic_basic_coercion(value, target_hint)

    def _coerce_typevar(self, value: Any, target_hint: TypeVar) -> Any:
        """
        Coercion pour TypeVar avec contraintes/bounds.
        """
        # Si TypeVar a des contraintes, essayer de coercer vers chacune
        if target_hint.__constraints__:
            for constraint in target_hint.__constraints__:
                try:
                    return self.coerce(value, constraint)
                except CoercionError:
                    continue
            raise CoercionError(f"Cannot coerce {type(value)} to any constraint of {target_hint}")
        
        # Si TypeVar a un bound, coercer vers le bound
        if target_hint.__bound__:
            return self.coerce(value, target_hint.__bound__)
        
        # Sinon, accepter la valeur telle quelle (comme Any)
        return value

    def _coerce_forward_ref(self, value: Any, target_hint: str) -> Any:
        """
        Coercion pour forward references (strings).
        Résout la référence puis relance la coercion récursivement.
        """
        import inspect
        frame = inspect.currentframe()
        try:
            # Résoudre la forward reference en type réel
            resolved_hint = self.type_checker._resolve_forward_ref(target_hint, frame.f_back)
            # Récursion : coercer avec le type résolu
            return self.coerce(value, resolved_hint)
        except TypeCheckError as e:
            # Si on ne peut pas résoudre, on lève une erreur
            raise CoercionError(f"Cannot resolve forward reference '{target_hint}': {e}")
        finally:
            del frame  # Éviter les cycles de référence

    def _fallback_coercion(self, value: Any, target_hint: Any) -> Any:
        """
        Coercion de dernier recours pour types non reconnus.
        """
        # Essayer isinstance comme dernière chance
        if isinstance(target_hint, type):
            try:
                return target_hint(value)
            except Exception:
                pass
        
        raise CoercionError(f"No coercion strategy available for {target_hint}")

    def _build_coercion_strategies(self) -> Dict[Tuple[type, type], Callable]:
        """
        🔥 Stratégies de coercion optimisées pour cas courants.
        """
        return {
            # String vers numerics
            (str, int): self._str_to_int,
            (str, float): self._str_to_float,
            (str, bool): self._str_to_bool,
            
            # Numerics vers string
            (int, str): str,
            (float, str): str,
            (bool, str): str,
            
            # Conversions numeriques
            (int, float): float,
            (float, int): self._float_to_int,
            (bool, int): int,  # True -> 1, False -> 0
            (int, bool): bool, # 0 -> False, else -> True
            
            # Containers basiques
            (tuple, list): list,
            (list, tuple): tuple,
            (set, list): list,
            (list, set): set,
            (frozenset, set): set,
            (set, frozenset): frozenset,
            
            # String vers containers
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
        """Conversion string -> int avec gestion d'erreurs."""
        value = value.strip()
        if not value:
            raise CoercionError("Empty string cannot be converted to int")
        
        # Gérer les cas comme "123.0" -> 123
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
        """Conversion string -> float avec gestion d'erreurs."""
        value = value.strip()
        if not value:
            raise CoercionError("Empty string cannot be converted to float")
        
        try:
            return float(value)
        except ValueError as e:
            raise CoercionError(f"Cannot convert '{value}' to float: {e}")

    def _str_to_bool(self, value: str) -> bool:
        """Conversion string -> bool avec logique intelligente."""
        value = value.strip().lower()
        
        # Valeurs truthy
        if value in ('true', '1', 'yes', 'on', 'y', 't'):
            return True
        # Valeurs falsy
        elif value in ('false', '0', 'no', 'off', 'n', 'f', ''):
            return False
        else:
            raise CoercionError(f"Cannot convert '{value}' to bool")

    def _float_to_int(self, value: float) -> int:
        """Conversion float -> int seulement si pas de partie décimale."""
        if value.is_integer():
            return int(value)
        else:
            raise CoercionError(f"Float {value} has decimal part, cannot convert to int")

    def _generic_basic_coercion(self, value: Any, target_hint: Any) -> Any:
        """
        Coercion générique pour types basiques non couverts par les stratégies.
        """
        if isinstance(target_hint, type):
            try:
                # Tentative de construction directe
                return target_hint(value)
            except Exception:
                raise CoercionError(f"Cannot coerce {type(value)} to {target_hint}")
        
        raise CoercionError(f"Cannot coerce {type(value)} to {target_hint}")

#endregion
