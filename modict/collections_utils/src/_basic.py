"""Shared container utilities and type aliases for collection helpers."""

from collections.abc import Mapping, Sequence, MutableMapping, MutableSequence
from typing import Any, Optional, Tuple, Type, Iterator
from ._types import (
    Key,
    Container,
    MutableContainer,
    is_container,
    is_mutable_container,
)
from ._missing import MISSING

def get_key(obj: Container, key: Key, default: Any = MISSING) -> Any:
    """Get a value by key/index from a container.

    This is a unified interface for accessing both Mapping keys and Sequence indices.
    Unlike direct subscripting (obj[key]), this function:
    - Provides consistent error handling across container types
    - Supports default values for missing keys
    - Validates key types for sequences (must be int)

    Args:
        obj: Container to get value from (Mapping or Sequence)
        key: Key (for Mapping) or index (for Sequence)
        default: Value to return if key doesn't exist (default: MISSING)

    Returns:
        Value at the given key/index, or default if provided and key doesn't exist

    Raises:
        TypeError: If obj is not a Mapping or Sequence
        KeyError: If key doesn't exist and no default provided (Mapping)
        IndexError: If index is out of range and no default provided (Sequence)
        TypeError: If key is not an int for Sequence containers

    Examples:
        >>> # Mapping
        >>> data = {"a": 1, "b": 2}
        >>> get_key(data, "a")
        1
        >>> get_key(data, "c", default=None)
        None

        >>> # Sequence
        >>> items = [10, 20, 30]
        >>> get_key(items, 1)
        20
        >>> get_key(items, 5, default=-1)
        -1
    """
    if isinstance(obj, Mapping):
        if default is not MISSING:
            return obj.get(key, default)
        return obj[key]
    elif isinstance(obj, Sequence):
        if not isinstance(key, int):
            raise TypeError(f"Sequence indices must be int, got {type(key).__name__}")
        if default is not MISSING:
            if 0 <= key < len(obj):
                return obj[key]
            return default
        return obj[key]  # Will raise IndexError if out of range
    else:
        raise TypeError(f"Expected a Mapping or Sequence container, got {type(obj).__name__}")


def set_key(obj: MutableContainer, key: Key, value: Any, expand: bool = True, filler: Any = MISSING) -> None:
    """Set a key/index in a mutable container.

    This is a unified interface for setting values in both MutableMapping and MutableSequence.
    Unlike direct assignment (obj[key] = value), this function:
    - Optionally auto-expands sequences to accommodate out-of-range indices
    - Fills gaps with a customizable filler value (default: MISSING)
    - Provides consistent error messages across container types
    - Validates key types for sequences (must be int)

    For MutableMapping:
        Simply sets obj[key] = value (expand and filler parameters are ignored)

    For MutableSequence:
        - If key is within bounds: sets obj[key] = value
        - If key is beyond bounds and expand=True: appends filler values to fill gaps, then sets value
        - If key is beyond bounds and expand=False: raises IndexError
        - This allows sparse assignment: set_key([], 5, 'x') creates [MISSING]*5 + ['x']

    Args:
        obj: Mutable container to modify (MutableMapping or MutableSequence)
        key: Key (for Mapping) or index (for Sequence)
        value: Value to set at the given key/index
        expand: Whether to auto-expand sequences for out-of-range indices (default: True)
        filler: Value to use when filling gaps in sequences (default: MISSING)

    Raises:
        TypeError: If obj is not a MutableMapping or MutableSequence
        TypeError: If key is not an int for MutableSequence containers
        IndexError: If expand=False and index is out of range for MutableSequence

    Examples:
        >>> # MutableMapping
        >>> data = {"a": 1}
        >>> set_key(data, "b", 2)
        >>> data
        {'a': 1, 'b': 2}

        >>> # MutableSequence - within bounds
        >>> items = [10, 20, 30]
        >>> set_key(items, 1, 99)
        >>> items
        [10, 99, 30]

        >>> # MutableSequence - auto-expansion with MISSING
        >>> items = [1, 2]
        >>> set_key(items, 5, 'x')
        >>> items
        [1, 2, MISSING, MISSING, MISSING, 'x']

        >>> # MutableSequence - auto-expansion with custom filler
        >>> items = [1, 2]
        >>> set_key(items, 5, 'x', filler=None)
        >>> items
        [1, 2, None, None, None, 'x']

        >>> # MutableSequence - no expansion (raises IndexError)
        >>> items = [1, 2]
        >>> set_key(items, 5, 'x', expand=False)
        Traceback (most recent call last):
            ...
        IndexError: Index 5 out of range for sequence of length 2 (expand=False)
    """
    if isinstance(obj, MutableMapping):
        obj[key] = value
    elif isinstance(obj, MutableSequence):
        if not isinstance(key, int):
            raise TypeError(f"Sequence indices must be int, got {type(key).__name__}")

        if key < len(obj):
            # Within bounds
            obj[key] = value
        elif expand:
            # Auto-expand sequence with filler
            while len(obj) <= key:
                obj.append(filler)
            obj[key] = value
        else:
            # Out of bounds and expand=False
            raise IndexError(f"Index {key} out of range for sequence of length {len(obj)} (expand=False)")
    else:
        raise TypeError(f"Expected a MutableMapping or MutableSequence container, got {type(obj).__name__}")


def keys(obj:Container)-> Iterator[Key]:
    """Yield possible keys or indices of a container.
    
    Args:
        obj: Mapping or Sequence to get keys from
        
    Yields:
        Keys for Mapping, indices for Sequence
        
    Raises:
        TypeError: If obj is neither Mapping nor Sequence
    """
    if isinstance(obj,Mapping):
        yield from obj.keys()
    elif isinstance(obj,Sequence):
        yield from range(len(obj))
    else:
        raise TypeError(f"Expected a Mapping or Sequence container, got {type(obj)}")


def has_key(obj:Container,key:Key)->bool:
    """Check if a key/index exists in a container.
    
    Args:
        obj: Container to check
        key: Key (for Mapping) or index (for Sequence) to look for
        
    Returns:
        True if key exists, False otherwise
        
    Raises:
        TypeError: If obj is neither Mapping nor Sequence
    """        
    if isinstance(obj,Mapping):
        return key in obj
    elif isinstance(obj,Sequence):
        return isinstance(key,int) and 0<=key<len(obj)
    else:
        raise TypeError(f"Expected a Mapping or Sequence container, got {type(obj)}")
    
def unroll(obj: Container) -> Iterator[Tuple[Key, Any]]:
    """Yield (key, value) pairs from a container.
    
    Args:
        obj: Container to unroll
        
    Yields:
        Tuple of (key, value) for each element
        
    Raises:
        TypeError: If obj is not a container
    """
    if not is_container(obj):
        raise TypeError(f"Expected a Mapping or Sequence container, got {type(obj)}")
    for key in keys(obj):
        yield key,obj[key]
