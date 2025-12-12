"""Collections utilities for nested data structures.

This module provides a comprehensive set of tools for working with nested data structures
in Python, particularly focusing on Mappings (like dictionaries) and Sequences (like lists).
It enables deep traversal, comparison, merging, and manipulation of nested structures
while maintaining type safety and providing clear error handling.

Key Features:
    - JSONPath support: Access nested values using JSONPath strings (RFC 9535)
    - Path objects: Strongly-typed Path objects that preserve container type information
    - Deep operations: Compare, merge, and modify nested structures
    - Type-safe: Comprehensive type hints and runtime type checking
    - Container views: Create custom views over container data
    - Structure traversal: Walk through nested structures with custom callbacks and filters

Main Components:
    - Path: JSONPath-based path representation with container type metadata
    - MISSING: Sentinel value for distinguishing missing values from None
    - Container operations: get_nested(), set_nested(), del_nested(), has_nested()
    - Deep operations: deep_merge(), deep_equals(), diff_nested()
    - Traversal: walk(), walked() for recursive container traversal

Typical Usage:
    >>> from collections_utils import get_nested, set_nested, walk, Path

    # Access nested values with JSONPath strings
    >>> data = {"users": [{"name": "Alice", "age": 30}]}
    >>> get_nested(data, "$.users[0].name")
    'Alice'

    # Modify nested structures
    >>> set_nested(data, "$.users[0].email", "alice@example.com")
    >>> data
    {"users": [{"name": "Alice", "age": 30, "email": "alice@example.com"}]}

    # Walk through nested structures (returns Path objects)
    >>> for path, value in walk(data):
    ...     print(f"{path}: {value}")
    $.users[0].name: Alice
    $.users[0].age: 30
    $.users[0].email: alice@example.com

Type Definitions:
    - Key: Union[int, str] - Valid container keys/indices
    - PathType: Union[str, Tuple[Key, ...], Path] - Path to nested values
    - Container: Union[Mapping, Sequence] - Any container type
    - MutableContainer: Union[MutableMapping, MutableSequence] - Mutable containers

Notes:
    - JSONPath strings must start with '$' (e.g., "$.a.b[0].c")
    - Tuple paths are ambiguous for integer keys and converted to Path objects
    - Path objects preserve container type information (mapping vs sequence)
    - Container operations maintain the original container types
    - The MISSING sentinel distinguishes missing values from None values
"""

from collections.abc import Collection,Mapping,Sequence,MutableMapping,MutableSequence
from typing import Any, Union, Dict, Tuple, Type, Optional, Set, Generic, Iterator, Callable, TypeVar
from itertools import islice
from ._basic import  set_key, MISSING, keys, has_key, unroll

from ._types import (
    Key,
    Container,
    MutableContainer,
    PathType,
    CallbackFn,
    is_container,
    is_mutable_container,
)

# TypeVars for generic container functions
C = TypeVar('C', bound=Container)

from ._path import Path, PathKey

def get_nested(obj: Container, path: PathType, default: Any = MISSING) -> Any:
    """Retrieve a nested value using a path.

    Args:
        obj: Nested structure to traverse
        path: Either JSONPath string ("$.a[0].b"), tuple of keys, or Path object
        default: Value to return if path doesn't exist

    Returns:
        Value at path or default if provided

    Raises:
        TypeError: If obj is not a container
        KeyError: If path doesn't exist and no default provided

    Examples:
        >>> data = {"a": {"b": [1, 2, {"c": 3}]}}
        >>> get_nested(data, "$.a.b[2].c")
        3
        >>> get_nested(data, ("a", "b", 2, "c"))
        3
        >>> get_nested(data, "$.x.y.z", default=None)
        None
    """
    if not is_container(obj):
        raise TypeError(f"Expected a Mapping or Sequence container, got {type(obj)}")

    path_obj = Path.normalize(path)

    if default is not MISSING:
        return path_obj.try_resolve(obj, default=default)
    else:
        try:
            return path_obj.resolve(obj)
        except (KeyError, IndexError, TypeError) as e:
            raise KeyError(f"Path {path!r} not found in container") from e

def set_nested(obj:Container, path: PathType, value):
    """Set a nested value, creating intermediate containers as needed.

    Creates missing containers (dict for string keys, list for integer keys)
    along the path if they don't exist.

    Args:
        obj: Container to modify
        path: Either JSONPath string ("$.a[0].b"), tuple of keys, or Path object
        value: Value to set

    Raises:
        TypeError: If obj is not a container or if any container we attempt to write in is immutable

    Examples:
        >>> data = {}
        >>> set_nested(data, "$.a.b[0].c", 42)
        >>> data
        {'a': {'b': [{'c': 42}]}}
    """
    if not is_container(obj):
        raise TypeError(f"Expected a Mapping or Sequence container, got {type(obj)}")

    path_obj = Path.normalize(path)
    components = path_obj.components

    current = obj
    for i, component in enumerate(components):
        if i == len(components) - 1:
            # Terminal key reached, we set the value and return
            set_key(current, component.value, value)
            return
        elif not has_key(current, component.value) or current[component.value] is MISSING:
            # Need to create intermediate container
            # Look at next component to decide what type to create
            next_component = components[i + 1]
            if next_component.container_type == "sequence" or (next_component.container_type == "unknown" and isinstance(next_component.value, int)):
                set_key(current, component.value, [])
            else:  # mapping
                set_key(current, component.value, {})
            current = current[component.value]
        else:
            current = current[component.value]

def pop_nested(obj:Container, path:PathType, default=MISSING):
    """deletes a nested key/index and returns the value (if found).
    If not found, returns default if provided, otherwise raises an error.
    If provided, default will be returned in ANY case of failure.
    This includes these cases:
        - the path doesn't exist or doesn't make sense in the structure
        - the path actually exists but ends in an immutable container in which we can't pop

    Args:
        obj: Container to modify
        path: Either JSONPath string ("$.a[0].b"), tuple of keys, or Path object

    Raises:
        TypeError: If obj is not a container, or we attempt to modify an immutable container
        KeyError: If path doesn't exist
    """
    if not is_container(obj):
        raise TypeError(f"Expected a Mapping or Sequence container, got {type(obj)}")

    path_obj = Path.normalize(path)
    components = path_obj.components

    current = obj
    try:
        for i, component in enumerate(components):
            if is_container(current) and has_key(current, component.value):
                if i == len(components) - 1:
                    if is_mutable_container(current):
                        value = current[component.value]
                        del current[component.value]
                        return value
                    else:
                        raise TypeError(f"Can't delete in an immutable container. Attempt to delete key={component.value!r} in {current} of immutable type {type(current)} caused this error.")
                current = current[component.value]
            else:
                raise KeyError(f"Path {path!r} not found in container")

    except (KeyError, TypeError):
        if default is not MISSING:
            return default
        else:
            raise

def del_nested(obj:Container, path:PathType):
    """deletes a nested key/index (if found).
    
    Args:
        obj: Container to modify
        path: Path to the value to delete
        
    Raises:
        TypeError: If obj is not a container, or we attempt to modify an immutable container
        KeyError: If path doesn't exist
    
    
    """
    # delegate the logic to pop_nested, we just don't return the output
    pop_nested(obj,path)

def has_nested(obj:Container, path: PathType):
    """Check if a nested path exists.

    Args:
        obj: Container to check
        path: Either JSONPath string ("$.a[0].b"), tuple of keys, or Path object

    Returns:
        True if path exists, False otherwise
    """
    if not is_container(obj):
        raise TypeError(f"Expected a Mapping or Sequence container, got {type(obj)}")

    path_obj = Path.normalize(path)
    return path_obj.try_resolve(obj, default=MISSING) is not MISSING


def extract(obj: C, *extracted_keys: Key) -> Iterator[Tuple[Key, Any]]:
    """
    Extract specified keys from a container, preserving the original order.
    
    Args:
        obj (Mapping or Sequence): The source container.
        *extracted_keys (str): Keys to extract.

    Returns:
        Iterator[Tuple[Key, Any]]: A generator of (key, value) pairs.
    """
    if not is_container(obj):
        raise TypeError(f"Expected a Mapping or Sequence container, got {type(obj)}")

    ek = set(extracted_keys)
    return ((key, obj[key]) for key in keys(obj) if key in ek)


def exclude(obj: C, *excluded_keys: Key) -> Iterator[Tuple[Key, Any]]:
    """
    Exclude specified keys from a container, preserving the original order.
    
    Args:
        obj (Mapping or Sequence): The source container.
        *excluded_keys (str): Keys to exclude.

    Returns:
        Iterator[Tuple[Key, Any]]: A generator of (key, value) pairs.
    """
    if not is_container(obj):
        raise TypeError(f"Expected a Mapping or Sequence container, got {type(obj)}")

    ek = set(excluded_keys)
    return ((key, obj[key]) for key in keys(obj) if key not in ek)

def walk(
    obj: Container,
    callback: Optional[CallbackFn] = None,
    filter: Optional[Callable[[Path, Any], bool]] = None,
    excluded: Optional[Tuple[Type, ...]] = None
) -> Iterator[Tuple[Path, Any]]:
    """Walk through a nested container yielding (path, value) pairs.

    Recursively traverses the container, yielding paths and values for leaf nodes.
    Leaves can be transformed by callback and filtered by the filter predicate.

    Args:
        obj: Container to traverse
        callback: Optional function to transform leaf values
        filter: Optional predicate to filter paths/values (receives Path and value)
        excluded: Container types to treat as leaves (default: str, bytes, bytearray)

    Yields:
        Tuples of (Path, value) for each leaf node
        If callback provided, value is transformed by callback
        If filter provided, only yields pairs that pass filter(path, value)

    Examples:
        >>> data = {"a": [1, {"b": 2}], "c": 3}
        >>> list(walk(data))
        [(Path($.a[0]), 1), (Path($.a[1].b), 2), (Path($.c), 3)]
        >>> list(walk(data, callback=str))
        [(Path($.a[0]), '1'), (Path($.a[1].b), '2'), (Path($.c), '3')]
    """

    def _walk(obj: Any, path: Path) -> Iterator[Tuple[Path, Any]]:
        if is_container(obj, excluded=excluded):
            for k, v in unroll(obj):
                # Create PathKey with container type information
                component = PathKey.from_key(k, container=obj)
                new_path = path.add_component(component)
                yield from _walk(v, new_path)
        else:
            if filter is None or filter(path, obj):
                yield path, callback(obj) if callback is not None else obj

    yield from _walk(obj, Path())
    
def walked(
    obj: Container,
    callback: Optional[CallbackFn] = None,
    filter: Optional[Callable[[Path, Any], bool]] = None,
    excluded: Optional[Tuple[Type, ...]] = None
) -> Dict[Path, Any]:
    """Return a flattened dictionary of path:value pairs from a nested container.

    Similar to walk(), but returns a dictionary instead of an iterator.

    Args:
        obj: Container to traverse
        callback: Optional function to transform leaf values
        filter: Optional predicate to filter paths/values
        excluded: Container types to treat as leaves

    Returns:
        Dictionary mapping Path objects to leaf values

    Examples:
        >>> data = {"a": [1, {"b": 2}], "c": 3}
        >>> walked(data)
        {Path($.a[0]): 1, Path($.a[1].b): 2, Path($.c): 3}
    """
    return dict(walk(obj, callback=callback, filter=filter, excluded=excluded))
 

def first_keys(walked: Dict[Path, Any]) -> Set[Key]:
    """Return all the first keys encountered in walked paths.

    Args:
        walked: A flattened dictionary with Path objects as keys

    Returns:
        A set of all first-level keys found in the paths

    Examples:
        >>> walked = {Path($.a[0].b): 1, Path($.a[1].c): 2, Path($.x.y): 3}
        >>> first_keys(walked)
        {'a', 'x'}
    """
    return set(p.components[0].value for p in walked if len(p.components) > 0)

def is_seq_based(walked: Dict[Path, Any]) -> bool:
    """Determine if the walked structure was initially a Sequence.

    Args:
        walked: A flattened dictionary with Path objects as keys

    Returns:
        True if the structure was a sequence (first keys are 0, 1, 2, ...)

    Examples:
        >>> is_seq_based({Path($[0].a): 1, Path($[1].b): 2})
        True
        >>> is_seq_based({Path($.a[0]): 1, Path($.b[1]): 2})
        False
    """
    fk = first_keys(walked)
    return fk == set(range(len(fk)))

def unwalk(walked: Dict[Path, Any]) -> MutableContainer:
    """Reconstruct a nested structure from a flattened dict.

    Args:
        walked: A Path:value flattened dictionary

    Returns:
        Reconstructed nested list or dict structure

    Examples:
        >>> walked = {Path($.a[0]): 1, Path($.a[1].b): 2, Path($.c): 3}
        >>> unwalk(walked)
        {'a': [1, {'b': 2}], 'c': 3}
        >>> walked = {Path($[0]): 'a', Path($[1]): 'b', Path($[2]): 'c'}
        >>> unwalk(walked)
        ['a', 'b', 'c']
    """
    # Determine root container type
    # Strategy 1 (preferred): Check the first Path's first component's container_type
    #   - If 'sequence': root was definitely a list/sequence (e.g., from walk() or JSONPath "$[0]")
    #   - If 'mapping': root was definitely a dict/mapping (e.g., from walk() or JSONPath "$.key")
    # Strategy 2 (fallback): If container_type is 'unknown' (e.g., from tuple paths),
    #   use the is_seq_based() heuristic to check if first keys are sequential integers (0,1,2...)
    #
    # This approach leverages the metadata preserved by Path objects to avoid relying on
    # heuristics when possible, making reconstruction more reliable and efficient.

    if walked:
        # Get first path
        first_path = next(iter(walked.keys()))

        # If path has components, check the first component's container_type
        if first_path.components:
            first_component = first_path.components[0]
            # Direct detection via container_type metadata
            if first_component.container_type == 'sequence':
                base = []
            elif first_component.container_type == 'mapping':
                base = {}
            else:
                # container_type is 'unknown' - fallback to heuristic
                base = [] if is_seq_based(walked) else {}
        else:
            # Empty path (root only) - shouldn't happen in practice
            base = {}
    else:
        # Empty walked dict
        base = {}

    for path, value in walked.items():
        set_nested(base, path, value)

    return base

def deep_equals(obj1: Container, obj2: Container, excluded: Optional[Tuple[Type, ...]] = None) -> bool:
    """Compare two nested structures deeply by comparing their walked dicts.

    Args:
        obj1: First container to compare
        obj2: Second container to compare
        excluded: Container types to treat as leaves

    Returns:
        True if the structures are deeply equal, False otherwise

    Examples:
        >>> deep_equals({'a': [1, 2]}, {'a': [1, 2]})
        True
        >>> deep_equals({'a': [1, 2]}, {'a': [1, 3]})
        False
    """
    return walked(obj1, excluded=excluded) == walked(obj2, excluded=excluded)

def diff_nested(
    obj1: Container,
    obj2: Container,
    path: Path = Path()
) -> Dict[Path, Tuple[Any, Any]]:
    """Compare two nested structures and return their differences.

    Recursively compares two containers and returns a dictionary of differences.
    Keys are Path objects where values differ, values are tuples of (obj1_value, obj2_value).

    Args:
        obj1: First container to compare
        obj2: Second container to compare
        path: Current path in recursion (used internally)

    Returns:
        Dictionary mapping Path objects to value pairs that differ
        MISSING is used when a key exists in one container but not the other

    Examples:
        >>> a = {"x": 1, "y": {"z": 2}}
        >>> b = {"x": 1, "y": {"z": 3}, "w": 4}
        >>> diff_nested(a, b)
        {Path($.y.z): (2, 3), Path($.w): (MISSING, 4)}
    """
    diffs: Dict[Path, Tuple[Any, Any]] = {}

    if is_container(obj1) and is_container(obj2):
        keys1 = set(keys(obj1))
        keys2 = set(keys(obj2))
        all_keys = keys1.union(keys2)

        # Determine container type for path components
        container = obj1 if keys1 else obj2

        for key in all_keys:
            component = PathKey.from_key(key, container=container)
            new_path = path.add_component(component)
            in_obj1 = has_key(obj1, key)
            in_obj2 = has_key(obj2, key)
            if in_obj1 and in_obj2:
                val1, val2 = obj1[key], obj2[key]
                if is_container(val1) and is_container(val2):
                    diffs.update(diff_nested(val1, val2, new_path))
                else:
                    if val1 != val2:
                        diffs[new_path] = (val1, val2)
            elif in_obj1:
                diffs[new_path] = (obj1[key], MISSING)
            elif in_obj2:
                diffs[new_path] = (MISSING, obj2[key])
    else:
        if obj1 != obj2:
            diffs[path] = (obj1, obj2)

    return diffs

def deep_merge(
    target: MutableContainer,
    src: Container,
    conflict_resolver: Optional[Callable[[Any, Any], Any]] = None
) -> None:
    """Deeply merge source container into target, modifying target in-place.
    
    For mappings:
    - If a key exists in both and both values are containers, merge recursively
    - Otherwise, src value overwrites target value (or uses conflict_resolver)
    
    For sequences:
    - Elements are merged by index
    - If src has more elements, they are appended to target
    
    Args:
        target: Mutable container to merge into
        src: Container to merge from
        conflict_resolver: Optional function to resolve value conflicts
            Takes (target_value, src_value), returns resolved value
        
    Raises:
        TypeError: If target and src are incompatible container types
        
    Examples:
        >>> target = {"a": 1, "b": {"x": 1}}
        >>> src = {"b": {"y": 2}, "c": 3}
        >>> deep_merge(target, src)
        >>> target
        {'a': 1, 'b': {'x': 1, 'y': 2}, 'c': 3}
    """
    if isinstance(target, MutableMapping) and isinstance(src, Mapping):
        for key, src_value in src.items():
            if has_key(target, key):
                target_value = target[key]
                if is_container(target_value) and is_container(src_value):
                    deep_merge(target_value, src_value, conflict_resolver)
                else:
                    target[key] = conflict_resolver(target_value, src_value) if conflict_resolver else src_value
            else:
                target[key] = src_value

    elif isinstance(target, MutableSequence) and isinstance(src, Sequence):
        for idx, src_value in enumerate(src):
            if idx < len(target):
                target_value = target[idx]
                if is_container(target_value) and is_container(src_value):
                    deep_merge(target_value, src_value, conflict_resolver)
                else:
                    target[idx] = conflict_resolver(target_value, src_value) if conflict_resolver else src_value
            else:
                target.append(src_value)
    else:
        raise TypeError("Types of 'target' and 'src' aren't compatibles for deep merging.")
