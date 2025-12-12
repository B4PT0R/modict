from ._types import Container,MutableContainer, Key, Collection, Mapping, Sequence, is_container
from typing import Generic, Iterator, Any, TypeVar
from itertools import islice
from ._basic import keys

E = TypeVar("T")
C = TypeVar("C", bound=Container)
MC = TypeVar("MC", bound=MutableContainer)

class View(Collection[E], Generic[C, E]):

    """Base View class for creating custom views over any Mapping or Sequence.
    
    Provides a read-only view over container data with custom element access logic.
    Subclasses must implement _get_element(key) to determine how elements are accessed.
    
    Type Parameters:
        C: The container type (must be Mapping or Sequence)
        T: The type of elements in the view
    
    Args:
        data: The container to create a view over
        
    Raises:
        TypeError: If data is not a Mapping or Sequence
        
    Examples:
        >>> class Keys(View[Mapping, Key]):
        ...     def _get_element(self, key: Key) -> Key:
        ...         return key
        >>> class Values(View[Mapping, T]):
        ...     def _get_element(self, key: Key) -> T:
        ...         return self.data[key]
    """

    def __init__(self, data:C) -> None:
        if not is_container(data):
            raise TypeError(f"The data on which a View is defined is expected to be a Mapping or Sequence. Got {type(data)}")
        self._data:C = data
        self._nmax: int = 10 # max number of elements to show in repr

    @property
    def data(self) -> C:
        return self._data

    def _get_element(self, key: Key) -> E:
        """Take a key and return the corresponding view element.

        Args:
            key: The key to get the element for

        Returns:
            The view element corresponding to the key

        Raises:
            NotImplementedError: This method must be implemented by subclasses
        """
        raise NotImplementedError()

    def __iter__(self) -> Iterator[E]:
        """Return an iterator over view elements.

        Returns:
            Iterator over the view elements
        """
        return iter(self._get_element(key) for key in keys(self.data))

    def __len__(self) -> int:
        """Return the number of elements in the view.

        Returns:
            The number of elements
        """
        return len(self.data)

    def __repr__(self) -> str:
        """String representation of the view.

        Returns:
            A string representation showing up to _nmax elements
        """
        content = ', '.join(repr(self._get_element(key)) for key in islice(keys(self.data), self._nmax))
        if len(self.data) > self._nmax:
            content += ", ..."
        return f"{self.__class__.__name__}({content})"

    def __contains__(self, item: Any) -> bool:
        """Check if an element is in the view.

        Args:
            item: The item to check for

        Returns:
            True if the item is in the view, False otherwise
        """
        return any(item == self._get_element(key) for key in keys(self.data))