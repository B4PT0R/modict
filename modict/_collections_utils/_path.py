"""JSONPath (RFC 9535) parsing and formatting utilities for modict.

This module provides JSONPath support for unambiguous path representation
in nested data structures, solving the disambiguation problem between:
- Array indices: $.a[0].b
- Integer keys: Direct assignment required (limitation)
- Digit string keys: $.a['0'].b

See RFC 9535: https://datatracker.ietf.org/doc/html/rfc9535
"""

from dataclasses import dataclass
from typing import Tuple, Union, Optional, Any, Iterator, Iterable, List, Callable, Type, Dict
from jsonpath_ng import parse as jsonpath_parse
from jsonpath_ng.jsonpath import Index, Fields, Root, Child
from ._types import (
    Container,
    Mapping,
    Sequence,
    MutableMapping,
    MutableSequence,
    is_container,
    is_mutable_container,
    Key,
    KeyType,
    PathType
)
from ._basic import set_key, has_key, keys


@dataclass(frozen=True)
class PathKey:
    """Single component in a JSONPath.

    Attributes:
        value: The key (str) or index (int)
        container_class: Origin container class (e.g., dict, list, UserDict). None when ambiguous.

    Examples:
        >>> PathKey(0, list)  # $.a[0]
        PathKey(value=0, container_class=<class 'list'>)
        >>> PathKey('0', dict)  # $.a['0']
        PathKey(value='0', container_class=<class 'dict'>)
        >>> PathKey('name', dict)  # $.a.name
        PathKey(value='name', container_class=<class 'dict'>)
    """
    value: Key
    container_class: Optional[Type[Container]] = None

    def __post_init__(self):
        """Validate component type consistency."""
        if not isinstance(self.value, (str, int)):
            raise ValueError(f"Component value must be str or int, got {type(self.value).__name__}")
        if self.container_class is not None:
            # Validate that it's a type and implements Mapping or Sequence
            if not isinstance(self.container_class, type):
                raise ValueError(f"container_class must be a type, got {type(self.container_class).__name__}")
            # Check if it's a Sequence type and value is not int
            if issubclass(self.container_class, Sequence) and not isinstance(self.value, int):
                raise ValueError(f"Sequence container requires int index, got {type(self.value).__name__}")
        
    @classmethod
    def from_key(cls, key: Key, container:Optional[Container]=None) -> "PathKey":
        """Create PathKey from key and container instance.

        Args:
           key: The key/index value
           container: Optional container instance used to capture the exact container class
        Returns:
           PathKey instance with container_class set to type(container) if provided
        """
        if not isinstance(key, (str, int)):
            raise ValueError(f"Component value must be str or int, got {type(key).__name__}")
        if container is not None and not isinstance(container, (Mapping, Sequence)):
            raise ValueError(f"Container must implement the Mapping or Sequence protocol (see collections.abc), got {type(container).__name__}")

        # Validate key/container coherence
        if isinstance(key, str):
            if container is not None and not isinstance(container, Mapping):
                raise ValueError(f"Incoherent container type {type(container)} for string key {key}")
        elif isinstance(key, int) and key < 0:
            # Negative indices only work with sequences
            if container is not None and not isinstance(container, Sequence):
                raise ValueError(f"Incoherent container type {type(container)} for negative index {key}")

        # Capture the exact container class if provided
        container_class = type(container) if container is not None else None

        return cls(value=key, container_class=container_class)
    
    def resolve(self,container:Container)->Any:
        """Resolve the key in the container."""
        if not isinstance(container,(Mapping,Sequence)):
            raise TypeError(f"Cannot resolve path in {type(container).__name__}\nContainer must be a Mapping or Sequence, got {type(container).__name__}")

        if isinstance(container, Mapping):
            # Check type mismatch only if container_class is known and it's a Sequence type
            if self.container_class is not None and issubclass(self.container_class, Sequence):
                raise TypeError(f"Cannot resolve path in {type(container).__name__}. Container type mismatch. Expected Sequence, got Mapping.")
            if not has_key(container, self.value):
                raise KeyError(f"Cannot resolve path in {type(container).__name__}. Key {self.value!r} not found in container.")
            return container[self.value]

        # Sequence case
        if self.container_class is not None and issubclass(self.container_class, Mapping):
            raise TypeError(f"Cannot resolve path in {type(container).__name__}. Container type mismatch. Expected Mapping, got Sequence.")
        if not isinstance(self.value, int):
            raise TypeError(f"Cannot resolve path in {type(container).__name__}. Sequence indices must be int, got {type(self.value).__name__}")
        try:
            return container[self.value]
        except IndexError as e:
            raise IndexError(f"Cannot resolve path in {type(container).__name__}. Index {self.value!r} out of range for container of length {len(container)}.") from e

    def __repr__(self):
        class_name = self.container_class.__name__ if self.container_class is not None else None
        return f"PathKey({self.value!r}, container_class={class_name})"

    def __str__(self):
        return f"{self.value!r}"

    def is_compatible(self, obj: Any) -> bool:
        """Return True if this PathKey can be resolved in obj without errors."""
        if not isinstance(obj, (Mapping, Sequence)):
            return False

        # If container_class is specified, check compatibility
        if self.container_class is not None:
            if issubclass(self.container_class, Mapping):
                return isinstance(obj, Mapping) and has_key(obj, self.value)
            elif issubclass(self.container_class, Sequence):
                return isinstance(obj, Sequence) and isinstance(self.value, int) and 0 <= self.value < len(obj)

        # No container_class (ambiguous) → allow either, but the key/index must exist
        if isinstance(obj, Mapping) and has_key(obj, self.value):
            return True
        if isinstance(obj, Sequence) and isinstance(self.value, int) and 0 <= self.value < len(obj):
            return True
        return False

@dataclass(frozen=True)
class Path:
    """Parsed JSONPath with metadata.

    Attributes:
        components: Tuple of PathKey objects representing the path

    Examples:
        >>> spec = Path(
        ...     components=(
        ...         PathKey('a', dict),
        ...         PathKey(0, list),
        ...         PathKey('b', dict)
        ...     ),
        ... )
        >>> spec.to_tuple()
        ('a',0,'b')
        >>> spec.components[0].container_class
        <class 'dict'>
    """

    components:Tuple[PathKey, ...]=()

    @property
    def is_root(self) -> bool:
        """Return True if the path is a root path. (no components)"""
        return not self.components

    @property
    def is_ambiguous(self):
        """Return True if the path is ambiguous (contains components with unknown container class)."""
        return any(c.container_class is None for c in self.components)

    def to_jsonpath(self) -> str:
        """Convert the Path to a JSONPath string."""
        components=self.components

        if not components:
            return '$'
        
        parts=['$']

        for component in components:
            if isinstance(component.value, int):
                parts.append(f'[{component.value}]')
            elif isinstance(component.value, str):
                if component.value.isdigit() or not is_identifier(component.value):
                    parts.append(f"['{component.value}']")
                else:
                    parts.append(f'.{component.value}')
            else:
                raise TypeError(f"Path components values must be str or int, got {type(component.value).__name__}")
        
        return ''.join(parts)
    
    @classmethod
    def from_jsonpath(cls, jsonpath: str) -> 'Path':
        """Parse a JSONPath string into a Path with metadata.

        Args:
            path: JSONPath string (must start with '$')

        Returns:
            Path with parsed components and type metadata

        Raises:
            ValueError: If path uses legacy dot-notation or has invalid syntax
            Exception: If jsonpath-ng parsing fails

        Examples:
            >>> spec = parse_jsonpath('$.a.b.c')
            >>> spec.to_tuple()
            ('a', 'b', 'c')

            >>> spec = parse_jsonpath('$.users[0].name')
            >>> spec.to_tuple()
            ('users', 0, 'name')
            >>> spec.components[1].container_class
            <class 'list'>

            >>> spec = parse_jsonpath("$.config['0'].value")
            >>> spec.to_tuple()
            ('config', '0', 'value')
            >>> spec.components[1].container_class
            <class 'dict'>

        Note:
            Legacy dot-notation paths (e.g., 'a.0.b') will raise a ValueError
            with migration guidance.
        """
        # Legacy detection
        if not jsonpath.startswith("$"):
            raise ValueError(
                f"Legacy dot-notation detected: {jsonpath!r}\n"
                f"modict 0.2.0+ requires JSONPath (RFC 9535).\n"
                f"Examples:\n"
                f"  'a.0.b'   → '$.a[0].b'\n"
                f"  'a.b.c'   → '$.a.b.c'\n"
                f"See: https://github.com/B4PT0R/modict/blob/main/MIGRATION.md"
            )

        # Parse using jsonpath-ng
        try:
            parsed = jsonpath_parse(jsonpath)
        except Exception as e:
            raise ValueError(f"Invalid JSONPath syntax: {jsonpath!r}\n{e}")

        # Extract components from parsed JSONPath
        components = []

        # Walk the JSONPath tree to extract components
        def extract_components(node, components_list):
            """Recursively extract components from jsonpath-ng AST."""
            if isinstance(node, Root):
                # Root node ($), skip
                return
            elif isinstance(node, Child):
                # Child node (e.g., $.a.b), recurse on left, then process right
                extract_components(node.left, components_list)
                extract_components(node.right, components_list)
            elif isinstance(node, Fields):
                # Field access (e.g., 'name' in $.name)
                # Use dict as the default mapping type when parsing JSONPath
                for field in node.fields:
                    components_list.append(PathKey(field, dict))
            elif isinstance(node, Index):
                # Array index (e.g., [0] or [-1])
                # Use list as the default sequence type when parsing JSONPath
                components_list.append(PathKey(node.index, list))
            else:
                # Other node types - attempt to extract fields/index if available
                if hasattr(node, 'fields'):
                    for field in node.fields:
                        components_list.append(PathKey(field, dict))
                elif hasattr(node, 'index'):
                    components_list.append(PathKey(node.index, list))
                else:
                    raise ValueError(f"Unsupported JSONPath component: {node!r}")

        extract_components(parsed, components)

        return Path(
            components=tuple(components)
        )

    @classmethod
    def normalize(cls, path: 'PathType') -> 'Path':
        """Normalize a path input to a Path object.

        This is a convenience method that accepts multiple path representations
        and normalizes them to a Path object.

        Args:
            path: Either a JSONPath string ("$.a[0].b"), tuple of keys, or Path object

        Returns:
            Path object

        Examples:
            >>> Path.normalize("$.a[0].b")
            Path($.a[0].b)
            >>> Path.normalize(('a', 0, 'b'))
            Path($.a[0].b)
            >>> Path.normalize(Path(...))
            Path(...)
        """
        if isinstance(path, cls):
            return path
        elif isinstance(path, str):
            return cls.from_jsonpath(path)
        elif isinstance(path, tuple):
            return cls.from_tuple(path)
        else:
            raise TypeError(f"Path must be a str, tuple, or Path object, got {type(path)}")

    def __str__(self):
        return self.to_jsonpath()
    
    def __repr__(self):
        return f"Path({self.to_jsonpath()})"

    def __iter__(self):
        return iter(self.components)
    
    def __add__(self,other):
        if not isinstance(other,Path):
            raise TypeError(f"Cannot concatenate Path with {type(other).__name__}")
        return Path.concatenate(self,other)
    
    def common_prefix(self,other:'Path')->'Path':
        """Return the longest common prefix of this path and another."""
        common_components=[]
        for s,o in zip(self.components,other.components):
            if s==o:
                common_components.append(s)
            else:
                break
        return Path(components=common_components)
    
    def starts_with(self, other: 'Path') -> bool:
        """Return True if this path has the same prefix as ``other``."""
        if len(other) > len(self):
            return False
        return all(
            self._component_compatible(s, o)
            for s, o in zip(self.components, other.components)
        )

    def relative_to(self, prefix: 'Path') -> 'Path':
        """Return the subpath after removing a given prefix."""
        if not self.starts_with(prefix):
            raise ValueError(f"Path {self} does not start with prefix {prefix}")
        return Path(components=self.components[len(prefix.components):])

    def resolve(self,root:Container)->Any:
        """Resolve the path in the given root container."""
        current=root
        for component in self.components:
            current=component.resolve(current)
        return current

    def try_resolve(self, root: Container, default: Any = None) -> Any:
        """Resolve, returning default instead of raising on failure."""
        try:
            return self.resolve(root)
        except (KeyError, IndexError, TypeError):
            return default

    def __eq__(self, other):
        if not isinstance(other, Path):
            return NotImplemented
        return self.to_jsonpath()==other.to_jsonpath()

    def __hash__(self) -> int:
        # Hash based on JSONPath representation (container_class info is lost, but that's OK for hashing)
        return hash(self.to_jsonpath())

    def __lt__(self, other: 'Path') -> bool:
        if not isinstance(other, Path):
            return NotImplemented
        # Compare based on values and container class names
        return tuple((c.value, c.container_class.__name__ if c.container_class else None) for c in self.components) < tuple(
            (c.value, c.container_class.__name__ if c.container_class else None) for c in other.components
        )

    def to_tuple(self) -> Tuple[Key, ...]:
        """Extract just keys/indices for legacy compatibility.
        Note: a path tuple is ambiguous as soon a it contains an int key
        Disambiguation depends on the container this path walks 

        Returns:
            Tuple of keys/indices without type metadata

        Examples:
            >>> spec = Path(
            ...     components=(PathKey('users', 'mapping'), PathKey(0, 'sequence'))
            ... )
            >>> spec.to_tuple()
            ('users', 0)
        """
        return tuple(c.value for c in self.components)

    def to_list(self) -> List[Key]:
        """JSON-friendly list representation of the path components."""
        return list(self.to_tuple())

    def __len__(self) -> int:
        """Return the number of components in the path."""
        return len(self.components)

    def __getitem__(self, index: int) -> PathKey:
        """Get a component by index."""
        return self.components[index]

    def parent(self) -> 'Path':
        """Return the parent path (all but the last component)."""
        if not self.components:
            raise ValueError("Root path has no parent")
        return Path(components=self.components[:-1])

    def pop(self) -> Tuple['Path', PathKey]:
        """Return (parent_path, last_component)."""
        if not self.components:
            raise ValueError("Root path cannot be popped")
        return Path(components=self.components[:-1]), self.components[-1]

    def prepend_key(self, key: Key, container: Optional[Container] = None) -> 'Path':
        """Prepend a key to the path."""
        component = PathKey.from_key(key, container=container)
        return self.prepend_component(component)

    def prepend_component(self, component: PathKey) -> 'Path':
        """Prepend a component to the path."""
        return Path(components=(component,) + self.components)

    def add_key(self, key: Key, container:Optional[Container]=None) -> 'Path':
        """Add a key to the path."""
        component=PathKey.from_key(key,container=container)
        return self.add_component(component)
    
    def add_component(self, component: PathKey) -> 'Path':
        """Add a component to the path."""
        return Path(components=self.components + (component,))
    
    @classmethod
    def concatenate(cls, *paths: Union['Path',PathKey]) -> 'Path':
        """Concatenate two Paths."""
        components=[]
        for path in paths:
            if not isinstance(path,(Path,PathKey)):
                raise ValueError(f"Invalid type: {type(path)}")
            if isinstance(path,PathKey):
                components.append(path)
            elif isinstance(path,Path):
                components.extend(path.components)
        return Path(components=tuple(components))
    
    @classmethod
    def common_prefix(cls, *paths: 'Path') -> 'Path':
        """Return the shared leading components of given paths."""
        if not paths:
            return Path()
        min_len = min(len(p) for p in paths)
        prefix_components = []
        for i in range(min_len):
            candidate = paths[0].components[i]
            if all(cls._component_compatible(candidate, p.components[i]) for p in paths[1:]):
                # Keep the most specific container_class if any path provides it
                # If multiple paths have different classes, prefer candidate's class
                classes = {p.components[i].container_class for p in paths if p.components[i].container_class is not None}
                if len(classes) == 1:
                    chosen_class = classes.pop()
                elif candidate.container_class is not None:
                    chosen_class = candidate.container_class
                else:
                    chosen_class = None
                prefix_components.append(PathKey(candidate.value, chosen_class))
            else:
                break
        return Path(components=tuple(prefix_components))

    @classmethod
    def from_tuple(cls, keys: Tuple[Key, ...]) -> 'Path':
        """Create Path from legacy tuple of keys/indices.

        Note: When creating from tuple, container classes are ambiguous.
        String keys default to dict, integer keys have no default (None).
        """
        components=[]
        for key in keys:
            if not isinstance(key, (str, int)):
                raise ValueError(f"Invalid key type: {type(key)}")
            if isinstance(key, str):
                # String keys → must be a dict-like mapping
                components.append(PathKey(key, dict))
            elif isinstance(key, int):
                # Integer keys are ambiguous (could be list index or dict key)
                # Set container_class to None
                components.append(PathKey(key, None))
        return cls(components=tuple(components))

    @classmethod
    def from_list(cls, keys: List[Key]) -> 'Path':
        """Create Path from a list of keys/indices."""
        return cls.from_tuple(tuple(keys))

    def with_container_types(self, root: Container) -> 'Path':
        """Return a new Path with container_class filled from actual container instances.

        Walks the path through the root container and captures the exact type of each container.
        """
        current = root
        components: list[PathKey] = []
        for component in self.components:
            if isinstance(current, Mapping):
                if not has_key(current, component.value):
                    raise KeyError(f"Key {component.value!r} not found while walking {self}")
                next_value = current[component.value]
                # Capture the exact type of the current container
                components.append(PathKey(component.value, type(current)))
                current = next_value
            elif isinstance(current, Sequence):
                if not isinstance(component.value, int):
                    raise TypeError(f"Expected integer index on sequence while walking {self}")
                try:
                    next_value = current[component.value]
                except IndexError as e:
                    raise IndexError(f"Index {component.value} out of range while walking {self}") from e
                # Capture the exact type of the current container
                components.append(PathKey(component.value, type(current)))
                current = next_value
            else:
                raise TypeError(f"Cannot walk non-container object of type {type(current).__name__}")
        return Path(components=tuple(components))

    @staticmethod
    def _component_compatible(left: PathKey, right: PathKey) -> bool:
        """Return True if components match, treating None container_class as a wildcard."""
        if left.value != right.value:
            return False
        # If either has None container_class, treat as compatible
        if left.container_class is None or right.container_class is None:
            return True
        # Both have container_class specified - they must match
        return left.container_class == right.container_class


def ensure_absolute(jsonpath: str) -> str:
    """Validate that a JSONPath string is absolute (starts with '$')."""
    if not jsonpath.startswith("$"):
        raise ValueError(f"JSONPath must be absolute (start with '$'), got {jsonpath!r}")
    return jsonpath


def is_identifier(s: str) -> bool:
    """Check if a string is a simple identifier (alphanumeric + underscore, not starting with digit).

    Args:
        s: String to check

    Returns:
        True if s is a simple identifier that can use dot notation

    Examples:
        >>> is_identifier('name')
        True
        >>> is_identifier('user_id')
        True
        >>> is_identifier('0')
        False
        >>> is_identifier('my-key')
        False
        >>> is_identifier('123abc')
        False
    """
    if not s:
        return False
    if s[0].isdigit():
        return False
    return all(c.isalnum() or c == '_' for c in s)
