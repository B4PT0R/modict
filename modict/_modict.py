from collections.abc import Mapping
from typing import Optional,Union, Tuple, Set, Dict, List, Any, Callable
from ._typechecker import check_type, TypeMismatchError, coerce
from ._modict_meta import modictMeta, Factory, Computed, modictItemsView,modictKeysView,modictValuesView, modictConfig
from ._collections_utils import (
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
    Path,
)
import copy
import json


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
        - Rename method to rename keys without changing values
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
                _config = modict.config(enforce_json=True, allow_extra=False)
                name: str
                age: int

        Args:
            allow_extra: Allow keys not defined in __fields__
            strict: Enable runtime type checking
            enforce_json: Ensure all values are JSON-serializable
            coerce: Enable automatic type coercion

        Returns:
            modictConfig instance
        """
        return modictConfig(**kwargs)

    @classmethod
    def check(cls, field_name):
        """Decorator to create field validators/transformers.

        Args:
            field_name: The name of the field to validate/transform

        Returns:
            A decorator function that marks methods as field checkers

        Examples:
            >>> class User(modict):
            ...     email: str
            ...
            ...     @modict.check('email')
            ...     def validate_email(self, value):
            ...         return value.lower().strip()
        """
        def decorator(f):
            f._is_check = True
            f._check_field = field_name
            return f
        return decorator

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

        self._config = type(self)._config.copy()

        super().__init__(*args,**kwargs)

        # Inject defaults and computed
        for key, field in self.__fields__.items():
            value=field.get_default()
            if value is not MISSING:
                if isinstance(value,Computed) or key not in self:
                    dict.__setitem__(self, key, value)

        self.validate()

    def validate(self):
        for key, value in dict.items(self):
            # 1. Clé interdite ? → on coupe court
            if not self._config.allow_extra and key not in self.__fields__:
                raise KeyError(
                    f"Key {key!r} is not allowed. Only the following keys are permitted: "
                    f"{list(self.__fields__.keys())}"
                )

            # 2. On ne valide pas les Computed (leurs valeurs ne sont pas stockées)
            if isinstance(value, Computed):
                continue

            # 3. Validation du contenu
            dict.__setitem__(self, key, self._check_value(key, value))

    def _check_value(self, key, value, hint=None):
        """Consolidate all validation: checkers + type checking.

        Used for incoming, outgoing, and computed property values.

        Args:
            key: The field name
            value: The value to check/transform
            hint: Optional type hint (if None, taken from Field)

        Returns:
            The checked and potentially transformed value
        """

        # 1. Appliquer les checkers custom d'abord (transformation permissive)
        value = self._apply_checks(key, value)

        # 2. Tenter la coercion
        if self._config.coerce:
            value = self._coerce_value(key, value, hint)
        
        # 3. Type checking ensuite (validation stricte du résultat)
        if hint is None:
            # Récupérer le hint du Field si pas fourni
            field = self.__fields__.get(key)
            if field and field.hint is not None:
                hint = field.hint
        
        # Vérifier le type si on a un hint et que le mode strict est activé
        if hint is not None:
            self._check_type(key, value, hint)

        if self._config.enforce_json:
            self._check_json_serializable(key, value)
        
        return value

    def _apply_checks(self, key, value):
        """Apply all field checkers in order (parent → child).

        Args:
            key: The field name
            value: The value to check

        Returns:
            The transformed value after all checkers
        """
        field = self.__fields__.get(key)
        if field and field.checkers:
            for checker in field.checkers:
                value = checker(self, value)
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
        
        # Si la valeur correspond déjà au type, pas de coercion
        try:
            check_type(hint, value)
            return value
        except:
            pass  # Type check a échoué, on tente la coercion
        
        # Tentative de coercion
        try:
            return coerce(value, hint)
        except:
            return value
    
    def _check_json_serializable(self, key: str, value: Any) -> None:
        """Check that a value is JSON serializable.

        Args:
            key: The field name (for error messages)
            value: The value to check

        Raises:
            ValueError: If the value is not JSON serializable
        """
        try:
            # Test de sérialisation rapide
            json.dumps(value)
        except (TypeError, ValueError, OverflowError) as e:
            # Types problématiques courants
            if isinstance(value, (set, frozenset)):
                suggestion = f" (convert to list: {list(value)!r})"
            elif callable(value):
                suggestion = " (functions are not JSON serializable)"
            elif hasattr(value, '__dict__'):
                suggestion = f" (convert to dict: {vars(value)!r})"
            else:
                suggestion = ""
                
            raise ValueError(
                f"Field '{key}' contains non-JSON-serializable value: {type(value).__name__}{suggestion}"
            ) from e

    def _check_type(self,key,value,hint):
        # basic isinstance check for now
        if self._config.strict:
            try:
                check_type(hint,value)
                return True
            except TypeMismatchError:
                raise TypeError(f"Key {key!r} expected an instance of {hint}, got {type(value)}")
            
    def _invalidate_dependants(self, changed_keys: set):
        """Recursively invalidate computed properties that depend on the given keys.

        Handles cascading dependencies automatically in a single method.

        Args:
            changed_keys: Set of keys that have changed (initially the modified key,
                then computed names that got invalidated)
        """
        if not changed_keys:
            return
            
        newly_invalidated = set()
        
        # Trouver tous les computed qui dépendent des clés modifiées
        for field_name, value in dict.items(self):
            if isinstance(value, Computed):
                if value.should_invalidate_for_keys(changed_keys):
                    if value.cache and value._cache_valid:  # Seulement si effectivement en cache
                        value.invalidate_cache()
                        newly_invalidated.add(field_name)
        
        # Récursion : propager aux computed qui dépendent des computed qu'on vient d'invalider
        if newly_invalidated:
            self._invalidate_dependants(newly_invalidated)

    def _invalidate_all(self):
        for value in dict.values(self):
            if isinstance(value, Computed):
                value.invalidate_cache()

    def _auto_convert_value(self, value):
        if not self._config.auto_convert:
            return value
        # Ici on reste data-structure agnostique
        if is_mutable_container(value):
            # Important : on retourne un modict "pur", pas une sous-classe
            return modict.convert(value)
        return value

    def _auto_convert_and_store(self, key, value):
        new = self._auto_convert_value(value)
        if new is not value:
            # On écrit brut pour ne pas relancer toute la validation
            dict.__setitem__(self, key, new)
            return new
        return value

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
            computed_value = value(self)
            checked = self._check_value(key, computed_value)
            # Pour les computed, on NE stocke pas le résultat dans le dict,
            # on fait juste l'auto-convert sur la valeur de retour.
            return self._auto_convert_value(checked)

        # Pour les valeurs stockées : on convertit ET on remplace dans le dict
        return self._auto_convert_and_store(key, value)

    def __setitem__(self, key, value):
        if not self._config.allow_extra and key not in self.__fields__:
            raise KeyError(
                f"Key {key!r} is not allowed. Only the following keys are permitted: "
                f"{list(self.__fields__.keys())}"
            )

        # Cas particulier : on stocke les Computed bruts, sans validation/invalidation
        if isinstance(value, Computed):
            dict.__setitem__(self, key, value)
            return

        # Cas normal : validation / coercion / JSON / type
        value = self._check_value(key, value)
        dict.__setitem__(self, key, value)
        self._invalidate_dependants({key})

    def __delitem__(self, key):
        # On laisse remonter le KeyError si pas de clé
        dict.__delitem__(self, key)
        self._invalidate_dependants({key})

    def __repr__(self):
        content=', '.join(f"{k!r}: {v!r}" for k,v in self.items())
        template=f"{{{content}}}"
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
        key = next(iter(self))
        return key, self.pop(key)

    def copy(self):
        """Create a shallow copy with validation.

        Returns:
            modict: A new modict with the same items
        """
        return type(self)(self)

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
        result.update(other)
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
            self[key] = default
            return default

    def clear(self):
        dict.clear(self)
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

    def __setattr__(self, key, value):
        """Allow attribute-style setting of dictionary keys.

        Intelligent routing: existing class attribute → Python protocol,
        new key → dictionary behavior.

        Args:
            key: The attribute/key name
            value: The value to set
        """
        if hasattr(type(self), key):
            object.__setattr__(self, key, value)
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
        elif key in self:
            del self[key]
        else:
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{key}'")

    @classmethod
    def convert(cls, obj: Any, seen: Optional[Dict] = None, root: bool = True) -> 'modict':
        """Convert dicts to modicts recursively.

        Takes any object as input and converts nested dictionaries to modicts.
        Handles circular references gracefully.

        Args:
            obj: The object to convert
            seen: Internal dict for tracking circular references (used in recursion)
            root: Whether this is the root call (affects which class is used)

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

        # then we recursively convert the values
        if is_mutable_container(obj):
            # We convert in situ to preserve references of original containers as much as possible
            for k, v in unroll(obj):
                if isinstance(obj, modict):
                    dict.__setitem__(obj, k, cls.convert(v, seen, root=False))
                else:
                    obj[k] = cls.convert(v, seen, root=False)

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
            for k, v in unroll(obj):
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

    def set_nested(self, path: str | tuple | Path, value):
        """Set a nested value, creating intermediate containers as needed.

        Creates missing containers (modict for string keys, list for integer keys)
        along the path if they don't exist.

        Supports multiple path formats:
        - JSONPath string (RFC 9535): "$.a[0].b"
        - Tuple of keys: ("a", 0, "b")
        - Path object: Path.from_jsonpath("$.a[0].b")

        Args:
            path: JSONPath string, tuple of keys, or Path object
            value: Value to set

        Raises:
            TypeError: If any container in the path is immutable

        Examples:
            >>> m = modict()
            >>> m.set_nested("$.a.b[0].c", 42)  # JSONPath
            >>> m
            modict({'a': {'b': [{'c': 42}]}})
        """
        set_nested(self,path,value)
            
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

    def rename(self, *args, **kwargs):
        """Rename keys without altering values (order is preserved).

        Uses an internal mapping created by dict(*args, **kwargs) where
        the keys represent the old keys and the values represent the new keys.
        Keys not present in the mapping remain unchanged.

        Args:
            *args: Positional arguments passed to dict() to create the mapping
            **kwargs: Keyword arguments passed to dict() to create the mapping

        Note:
            If two different keys are renamed to the same new key,
            the last one encountered will overwrite the previous one.

        Examples:
            >>> m = modict(a=1, b=2, c=3)
            >>> m.rename(a='x', b='y')
            >>> m
            modict({'x': 1, 'y': 2, 'c': 3})
            >>> m.rename({'x': 'alpha', 'y': 'beta'})
            >>> m
            modict({'alpha': 1, 'beta': 2, 'c': 3})
        """
        mapping = dict(*args, **kwargs)
        # Create a new dictionary preserving the order of the original items
        new_dict = type(self)()
        for key, value in self.items():
            new_key = mapping.get(key, key)
            new_dict[new_key] = value
        # Update self in place to maintain the original reference
        self.clear()
        self.update(new_dict)
        
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
    def unwalk(cls, walked):
        """Reconstruct a nested structure from a flattened dict.

        Args:
            walked: A path:value flattened dictionary (e.g., {'a.0.b': 1, 'a.1.c': 2})

        Returns:
            Reconstructed nested modict or list structure

        Examples:
            >>> walked_data = modict({'a.0': 1, 'a.1.b': 2, 'c': 3})
            >>> modict.unwalk(walked_data)
            modict({'a': [1, {'b': 2}], 'c': 3})
        """
        unwalked=unwalk(walked)
        if isinstance(unwalked,Mapping):
            return cls(unwalked)
        return unwalked

    def merge(self, other: Mapping):
        """Deeply merge another mapping into this modict, modifying it in-place.

        For mappings:
        - If a key exists in both and both values are containers, merge recursively
        - Otherwise, other's value overwrites this modict's value

        For sequences:
        - Elements are merged by index
        - If other has more elements, they are appended

        Args:
            other: Mapping to merge from

        Raises:
            TypeError: If attempting to merge incompatible container types

        Examples:
            >>> m = modict(a=1, b=modict(x=1))
            >>> m.merge({'b': {'y': 2}, 'c': 3})
            >>> m
            modict({'a': 1, 'b': {'x': 1, 'y': 2}, 'c': 3})
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
        return type(self)(copy.deepcopy(dict(self)))
    
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
              default=None, sort_keys=False, **kw):
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
        return json.dumps(self, skipkeys=skipkeys, ensure_ascii=ensure_ascii,
                         check_circular=check_circular, allow_nan=allow_nan,
                         cls=cls, indent=indent, separators=separators,
                         default=default, sort_keys=sort_keys, **kw)
    
    def dump(self, fp, *, skipkeys=False, ensure_ascii=True, check_circular=True,
             allow_nan=True, cls=None, indent=None, separators=None,
             default=None, sort_keys=False, **kw):
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
            json.dump(self, fp, skipkeys=skipkeys, ensure_ascii=ensure_ascii,
                     check_circular=check_circular, allow_nan=allow_nan,
                     cls=cls, indent=indent, separators=separators,
                     default=default, sort_keys=sort_keys, **kw)
        else:
            # Path-like object  
            with open(fp, 'w') as f:
                self.dump(f, skipkeys=skipkeys, ensure_ascii=ensure_ascii,
                         check_circular=check_circular, allow_nan=allow_nan,
                         cls=cls, indent=indent, separators=separators,
                         default=default, sort_keys=sort_keys, **kw)
