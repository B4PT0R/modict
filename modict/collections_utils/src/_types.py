"""Shared type aliases and container checking helpers."""

from collections.abc import Collection, Mapping, Sequence, MutableMapping, MutableSequence
from abc import ABC, abstractmethod
from typing import (
    TypeAlias,
    Union,
    Tuple,
    Optional,
    Type,
    Any,
    TypeVar,
    Callable,
    TYPE_CHECKING,
)

if TYPE_CHECKING:  # pragma: no cover
    from path_utils import Path, PathKey

Key: TypeAlias = Union[int, str]
KeyType: TypeAlias = Union[Key, 'PathKey']
Container: TypeAlias = Union[Mapping, Sequence]
MutableContainer: TypeAlias = Union[MutableMapping, MutableSequence]
PathType: TypeAlias = Union[str, Tuple[Key, ...], 'Path']
CallbackFn = Callable[[Any], Any]
FilterFn = Callable[[str, Any], bool]

class Namespace(MutableMapping):
    """MutableMapping view over a class namespace.

    Useful when you need to treat `cls` as a mapping while still writing back
    attributes (since `cls.__dict__` is a read-only mappingproxy).
    """

    def __init__(self, cls: type):
        self.cls = cls

    def __getitem__(self, key):
        if key in self:
            return getattr(self.cls, key)
        raise KeyError(f"Key {key!r} not found in class namespace.")

    def __setitem__(self, key, value):
        setattr(self.cls, key, value)

    def __delitem__(self, key):
        if key in self:
            delattr(self.cls, key)
            return
        raise KeyError(f"Key {key!r} not found in class namespace.")

    def __contains__(self, key):
        return key in self.cls.__dict__

    def __iter__(self):
        return iter(self.cls.__dict__)

    def __len__(self):
        return len(self.cls.__dict__)


class MutableCollection(Collection, ABC):
    """Abstract base class for a mutable collection.

    Combines the immutable Collection interface (contains, len, iter)
    with mutable operations (getitem, setitem, delitem).
    """

    @abstractmethod
    def __getitem__(self, key):
        raise NotImplementedError

    @abstractmethod
    def __setitem__(self, key, value):
        raise NotImplementedError

    @abstractmethod
    def __delitem__(self, key):
        raise NotImplementedError


def is_container(obj:Any, excluded:Optional[Tuple[Type,...]]=None)->bool:
    """Test if an object is a container (but not an excluded type).
    
    Args:
        obj: Object to test
        excluded: Types to not consider as containers (default: str, bytes, bytearray)
        
    Returns:
        True if obj is a non-excluded container
    """
    excluded= excluded if excluded is not None else (str,bytes,bytearray)
    return (isinstance(obj,Mapping) or isinstance(obj,Sequence)) and not isinstance(obj,excluded)

def is_mutable_container(obj:Any)->bool:
    """Test if an object is a mutable container.

    Args:
        obj: Object to test

    Returns:
        True if obj is MutableMapping or MutableSequence
    """
    return isinstance(obj,MutableMapping) or isinstance(obj,MutableSequence)


def is_dict_like(obj: Any) -> bool:
    """Test if an object is dict-like (implements MutableMapping).

    Alias for checking MutableMapping interface, for backward compatibility
    with reactive_data/collections_utils.py

    Args:
        obj: Object to test

    Returns:
        True if obj implements MutableMapping
    """
    return isinstance(obj, MutableMapping)


def is_list_like(obj: Any) -> bool:
    """Test if an object is list-like (implements MutableSequence).

    Alias for checking MutableSequence interface, for backward compatibility
    with reactive_data/collections_utils.py

    Args:
        obj: Object to test

    Returns:
        True if obj implements MutableSequence
    """
    return isinstance(obj, MutableSequence)

