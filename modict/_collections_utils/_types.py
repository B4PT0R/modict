"""Shared type aliases and container checking helpers."""

from collections.abc import Collection, Mapping, Sequence, MutableMapping, MutableSequence
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
    from ._path import Path, PathKey

Key: TypeAlias = Union[int, str]
KeyType: TypeAlias = Union[Key, 'PathKey']
Container: TypeAlias = Union[Mapping, Sequence]
MutableContainer: TypeAlias = Union[MutableMapping, MutableSequence]
PathType: TypeAlias = Union[str, Tuple[Key, ...], 'Path']
CallbackFn = Callable[[Any], Any]
FilterFn = Callable[[str, Any], bool]


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


