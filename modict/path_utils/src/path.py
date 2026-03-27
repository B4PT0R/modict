from __future__ import annotations

from collections.abc import Mapping, MutableMapping, MutableSequence, Sequence
from typing import Any, Iterable, Iterator

PathKey = int | str


class ResolutionError(LookupError):
    pass


class _Missing:
    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover
        return "MISSING"

    def __bool__(self) -> bool:
        return False


MISSING = _Missing()


def _is_sequence(value: Any) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))


def _get_from_container(container: Any, key: PathKey) -> Any:
    if isinstance(container, Mapping):
        return container[key]
    if isinstance(key, int) and _is_sequence(container):
        return container[key]
    if isinstance(key, str) and hasattr(container, key):
        return getattr(container, key)
    return container[key]  # may raise; supports custom containers


def _set_in_container(container: Any, key: PathKey, value: Any) -> None:
    if isinstance(container, MutableMapping):
        container[key] = value
        return
    if isinstance(key, int) and isinstance(container, MutableSequence):
        container[key] = value
        return
    if isinstance(key, str) and hasattr(container, key):
        setattr(container, key, value)
        return
    container[key] = value  # may raise


def _delete_in_container(container: Any, key: PathKey) -> None:
    if isinstance(container, MutableMapping):
        del container[key]
        return
    if isinstance(key, int) and isinstance(container, MutableSequence):
        del container[key]
        return
    if isinstance(key, str) and hasattr(container, key):
        delattr(container, key)
        return
    del container[key]  # may raise


def is_identifier(text: str) -> bool:
    """Check if a string is a valid Python identifier.

    Args:
        text: String to check

    Returns:
        True if text is a valid identifier that can use dot notation

    Examples:
        >>> is_identifier('name')
        True
        >>> is_identifier('user_id')
        True
        >>> is_identifier('0')
        False
        >>> is_identifier('my-key')
        False
    """
    return text.isidentifier()


def ensure_absolute(jsonpath: str) -> str:
    """Validate that a JSONPath string is absolute (starts with '$').

    Args:
        jsonpath: JSONPath string to validate

    Returns:
        The validated jsonpath string

    Raises:
        ValueError: If jsonpath doesn't start with '$'

    Examples:
        >>> ensure_absolute('$.foo.bar')
        '$.foo.bar'
        >>> ensure_absolute('foo.bar')
        Traceback (most recent call last):
        ...
        ValueError: JSONPath must be absolute (start with '$'), got 'foo.bar'
    """
    if not jsonpath.startswith("$"):
        raise ValueError(f"JSONPath must be absolute (start with '$'), got {jsonpath!r}")
    return jsonpath


def _escape_single_quoted(text: str) -> str:
    return text.replace("\\", "\\\\").replace("'", "\\'")


class PathNode:
    __slots__ = ("key", "container", "parent_node")

    def __init__(self, key: PathKey, container: Any = MISSING, parent_node: PathNode | None = None) -> None:
        self.key = key
        # Validate that if container is provided, it's actually a container or MISSING
        if container is not MISSING:
            has_item_access = hasattr(container, "__getitem__")
            has_attr_access = isinstance(key, str) and hasattr(container, key)
            if not isinstance(container, (Mapping, Sequence)) and not (has_item_access or has_attr_access):
                raise TypeError(f"PathNode container must be a Mapping, Sequence, or object with attribute access, got {type(container).__name__}")
        self.container = container
        self.parent_node = parent_node

    def __eq__(self, other: object) -> bool:
        return isinstance(other, PathNode) and self.key == other.key

    def __hash__(self) -> int:
        return hash(self.key)

    def resolve(self, container: Any = MISSING) -> Any:
        if container is not MISSING:
            if self.container is not MISSING and self.container is not container:
                raise ResolutionError(f"Container mismatch for key {self.key!r}")
            if self.container is MISSING:
                self.container = container
            base_container = container
        else:
            base_container = self.container

        if base_container is MISSING:
            raise ResolutionError(f"Missing container reference for key {self.key!r}")
        try:
            return _get_from_container(base_container, self.key)
        except (KeyError, IndexError, AttributeError, TypeError) as exc:
            raise ResolutionError(f"Failed to resolve key {self.key!r}") from exc

    def set_inplace(self, value: Any) -> None:
        if self.container is MISSING:
            raise ResolutionError(f"Missing container reference for key {self.key!r}")
        _set_in_container(self.container, self.key, value)

    def delete_inplace(self) -> None:
        if self.container is MISSING:
            raise ResolutionError(f"Missing container reference for key {self.key!r}")
        _delete_in_container(self.container, self.key)


class Path:
    __slots__ = ("nodes", "root")

    def __init__(self, path: Any = (), root: Any = MISSING) -> None:
        if isinstance(path, Path):
            if root is MISSING:
                self.nodes = self._clone_nodes(path.nodes)
                self.root = path.root
                return
            keys: tuple[PathKey, ...] = tuple(path)
        elif isinstance(path, str):
            from ._jsonpath import keys_from_expr

            keys = keys_from_expr(path)
        else:
            try:
                from jsonpath_ng.jsonpath import JSONPath as _JSONPath  # type: ignore
            except Exception:  # pragma: no cover
                _JSONPath = ()  # type: ignore
            if _JSONPath and isinstance(path, _JSONPath):
                from ._jsonpath import keys_from_expr

                keys = keys_from_expr(path)
            else:
                if path is None:
                    keys = ()
                else:
                    keys = tuple(path)

        for key in keys:
            if not isinstance(key, (int, str)):
                raise TypeError(f"Path keys must be int or str, got {type(key).__name__}")

        parent_node: PathNode | None = None
        nodes: list[PathNode] = []
        for key in keys:
            node = PathNode(key=key, container=MISSING, parent_node=parent_node)
            nodes.append(node)
            parent_node = node

        if root is not MISSING and nodes:
            nodes[0].container = root

        self.nodes = tuple(nodes)
        self.root = root

    @classmethod
    def _from_nodes(cls, nodes: Iterable[PathNode], root: Any) -> Path:
        obj = cls(())
        obj.nodes = tuple(nodes)
        obj.root = root
        return obj

    @staticmethod
    def _clone_nodes(nodes: Iterable[PathNode]) -> tuple[PathNode, ...]:
        cloned: list[PathNode] = []
        parent_node: PathNode | None = None
        for node in nodes:
            copied = PathNode(key=node.key, container=node.container, parent_node=parent_node)
            cloned.append(copied)
            parent_node = copied
        return tuple(cloned)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Path) and tuple(self) == tuple(other)

    def __hash__(self) -> int:
        return hash(tuple(self))

    def __iter__(self) -> Iterator[PathKey]:
        return (node.key for node in self.nodes)

    def __len__(self) -> int:
        return len(self.nodes)

    def __repr__(self) -> str:
        return f"Path({self})"

    @classmethod
    def walk(cls, root: Any, *, walk_objects: bool = False) -> Iterable[tuple[Path, Any]]:
        start = cls((), root=root)
        seen_container_ids: set[int] = set()

        def _recurse(value: Any, path: Path) -> Iterable[tuple[Path, Any]]:
            if isinstance(value, Mapping) or _is_sequence(value):
                container_id = id(value)
                if container_id in seen_container_ids:
                    return
                seen_container_ids.add(container_id)

                if isinstance(value, Mapping):
                    if not value:
                        yield (path, value)
                        return
                    parent_node = path.nodes[-1] if path.nodes else None
                    for key, child_value in value.items():
                        if not isinstance(key, (int, str)):
                            continue
                        node = PathNode(key=key, container=value, parent_node=parent_node)
                        child_path = Path._from_nodes(path.nodes + (node,), root=path.root)
                        yield from _recurse(child_value, child_path)
                    return

                if not value:
                    yield (path, value)
                    return
                parent_node = path.nodes[-1] if path.nodes else None
                for index, child_value in enumerate(value):
                    node = PathNode(key=index, container=value, parent_node=parent_node)
                    child_path = Path._from_nodes(path.nodes + (node,), root=path.root)
                    yield from _recurse(child_value, child_path)
                return

            if walk_objects and hasattr(value, "__class__") and not isinstance(value, (str, bytes, bytearray)):
                try:
                    object_items: list[tuple[str, Any]] = []

                    try:
                        import dataclasses as _dc  # local import to keep module lightweight
                    except Exception:  # pragma: no cover
                        _dc = None  # type: ignore[assignment]

                    if _dc is not None and _dc.is_dataclass(value):
                        for f in _dc.fields(value):
                            name = f.name
                            if name.startswith("_"):
                                continue
                            try:
                                child_value = getattr(value, name)
                            except Exception:
                                continue
                            if callable(child_value):
                                continue
                            object_items.append((name, child_value))
                    elif hasattr(value, "__dict__") and isinstance(getattr(value, "__dict__", None), dict):
                        for name, child_value in value.__dict__.items():
                            if not isinstance(name, str) or name.startswith("_"):
                                continue
                            if callable(child_value):
                                continue
                            object_items.append((name, child_value))

                    if object_items:
                        container_id = id(value)
                        if container_id in seen_container_ids:
                            return
                        seen_container_ids.add(container_id)

                        parent_node = path.nodes[-1] if path.nodes else None
                        for name, child_value in object_items:
                            node = PathNode(key=name, container=value, parent_node=parent_node)
                            child_path = Path._from_nodes(path.nodes + (node,), root=path.root)
                            yield from _recurse(child_value, child_path)
                        return
                except Exception:  # pragma: no cover
                    pass

            yield (path, value)

        return _recurse(root, start)

    def resolve(self, root: Any = MISSING) -> Any:
        if not self.nodes:
            if root is not MISSING:
                return root
            if self.root is not MISSING:
                return self.root
            raise ResolutionError("Cannot resolve an empty Path without a container/root.")

        start_container = root if root is not MISSING else self.root
        if start_container is MISSING and self.nodes and self.nodes[0].container is not MISSING:
            start_container = self.nodes[0].container
        if start_container is MISSING:
            raise ResolutionError("Cannot resolve Path without a container/root.")

        current_container = start_container
        value: Any = MISSING
        for node in self.nodes:
            value = node.resolve(current_container)
            current_container = value
        return value

    def exists(self, root: Any = MISSING) -> bool:
        old_containers = [node.container for node in self.nodes]
        try:
            self.resolve(root)
            return True
        except ResolutionError:
            return False
        finally:
            for node, container in zip(self.nodes, old_containers, strict=False):
                node.container = container

    def invalidate(self) -> None:
        for node in self.nodes:
            node.container = MISSING

    def set_root(self, root: Any) -> Path:
        self.root = root
        self.invalidate()
        if root is not MISSING and self.nodes:
            self.nodes[0].container = root
        return self

    def with_root(self, root: Any) -> Path:
        return Path(self, root=root)

    def starts_with(self, other: Any) -> bool:
        other_path = other if isinstance(other, Path) else Path(other)
        other_keys = tuple(other_path)
        self_keys = tuple(self)
        return len(other_keys) <= len(self_keys) and self_keys[: len(other_keys)] == other_keys

    def is_ancestor_of(self, other: Any, *, strict: bool = False) -> bool:
        other_path = other if isinstance(other, Path) else Path(other)
        if strict and len(self) >= len(other_path):
            return False
        return other_path.starts_with(self)

    def relative_to(self, other: Any) -> Path:
        other_path = other if isinstance(other, Path) else Path(other)
        if not self.starts_with(other_path):
            raise ValueError(f"{self!r} does not start with {other_path!r}")
        return self[len(other_path):]

    def parent(self, levels: int = 1) -> Path:
        if levels < 0:
            raise ValueError("levels must be >= 0")
        if levels == 0:
            return self
        if levels >= len(self.nodes):
            return Path((), root=self.root)
        return self[:-levels]

    def _slice(self, key: slice) -> Path:
        sliced_nodes = self.nodes[key]
        if not sliced_nodes:
            root = self.root if (key.start in (None, 0)) else MISSING
            return Path((), root=root)

        start = 0 if key.start is None else key.start
        root = self.root if start == 0 else MISSING
        first_container = MISSING
        if start > 0 and self.root is not MISSING:
            first_container = self[:start].resolve()

        nodes: list[PathNode] = []
        parent_node: PathNode | None = None
        for index, original in enumerate(sliced_nodes):
            container = original.container
            if index == 0 and first_container is not MISSING:
                container = first_container
            node = PathNode(key=original.key, container=container, parent_node=parent_node)
            nodes.append(node)
            parent_node = node
        return Path._from_nodes(nodes, root=root)

    def _append(self, key: PathKey, *, container: Any = MISSING) -> Path:
        parent_node = self.nodes[-1] if self.nodes else None
        node = PathNode(key=key, container=container, parent_node=parent_node)
        return Path._from_nodes(self.nodes + (node,), root=self.root)

    def child(self, key: PathKey) -> Path:
        if self.root is MISSING:
            return self._append(key)
        current_value = self.resolve()
        return self._append(key, container=current_value)

    def __add__(self, other: Any) -> Path:
        if isinstance(other, Path):
            other_keys: tuple[PathKey, ...] = tuple(other)
        elif isinstance(other, (str, int)):
            other_keys = (other,)  # type: ignore[assignment]
        else:
            try:
                other_keys = tuple(other)
            except TypeError:
                return NotImplemented

        nodes = list(self.nodes)
        parent_node = nodes[-1] if nodes else None
        for key in other_keys:
            node = PathNode(key=key, container=MISSING, parent_node=parent_node)
            nodes.append(node)
            parent_node = node
        return Path._from_nodes(nodes, root=self.root)

    def __radd__(self, other: Any) -> Path:
        if isinstance(other, Path):
            left_keys: tuple[PathKey, ...] = tuple(other)
        elif isinstance(other, (str, int)):
            left_keys = (other,)  # type: ignore[assignment]
        else:
            try:
                left_keys = tuple(other)
            except TypeError:
                return NotImplemented
        return Path(left_keys + tuple(self), root=self.root)

    def __getitem__(self, key: PathKey | slice) -> Path:
        if isinstance(key, slice):
            return self._slice(key)
        if not isinstance(key, (int, str)):
            raise TypeError(f"Path indices must be int, str, or slice, got {type(key).__name__}")
        return self.child(key)

    def __getattr__(self, name: str) -> Path:
        if name.startswith("_"):
            raise AttributeError(name)
        return self.child(name)

    def set_inplace(self, value: Any) -> None:
        if not self.nodes:
            raise ValueError("Cannot set value on an empty Path.")
        if len(self.nodes) > 1:
            parent_value = self.parent().resolve()
            if self.nodes[-1].container is MISSING:
                self.nodes[-1].container = parent_value
        self.nodes[-1].set_inplace(value)

    def delete_inplace(self) -> None:
        if not self.nodes:
            raise ValueError("Cannot delete value on an empty Path.")
        if len(self.nodes) > 1:
            parent_value = self.parent().resolve()
            if self.nodes[-1].container is MISSING:
                self.nodes[-1].container = parent_value
        self.nodes[-1].delete_inplace()

    def __str__(self) -> str:
        parts: list[str] = ["$"]
        for key in self:
            if isinstance(key, int):
                parts.append(f"[{key}]")
            else:
                if is_identifier(key):
                    parts.append(f".{key}")
                else:
                    parts.append(f"['{_escape_single_quoted(key)}']")
        return "".join(parts)
