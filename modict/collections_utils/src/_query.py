from __future__ import annotations

from typing import Any, Callable

from ...path_utils import Path, find_paths
from ._missing import MISSING


class Query:
    """A combined path + value constraint for searching nested structures.

    Args:
        path: What to match against each path:
            - ``MISSING`` (default): match any path.
            - ``str``: JSONPath expression evaluated by the JSONPath engine
              (supports wildcards, filters, ``..`` descent, etc.).
            - ``Path``, ``tuple``, or ``list``: exact path match.
            - ``callable(Path) -> bool``: custom path predicate.

        value: What to match against each leaf value:
            - ``MISSING`` (default): match any value.
            - ``callable(value) -> bool``: custom value predicate.
            - any other object, including ``None``: equality check (``==``).

    Examples::

        # Any leaf whose key is "email"
        Query(lambda p: tuple(p)[-1] == "email")

        # JSONPath wildcard + value predicate
        Query("$.users[*].age", lambda v: v > 30)

        # Exact path + exact value
        Query(("users", 0, "name"), "Alice")

        # Find all leaves that are None
        Query(value=None)

        # Value predicate only
        Query(value=lambda v: isinstance(v, str) and "@" in v)
    """

    def __init__(
        self,
        path: str | Path | tuple | list | Callable[[Path], bool] | None = MISSING,
        value: Any = MISSING,
    ) -> None:
        self._path = path
        self._value = value

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _value_matches(self, value: Any) -> bool:
        if self._value is MISSING:
            return True
        if callable(self._value):
            return bool(self._value(value))
        return value == self._value

    def _path_predicate(self) -> Callable[[Path], bool] | None:
        """Return a callable(Path)->bool for non-JSONPath path constraints, or None."""
        if self._path is MISSING:
            return lambda _: True
        if callable(self._path):
            return self._path
        if not isinstance(self._path, str):
            target = Path(self._path)
            return lambda p: p == target
        return None  # JSONPath string — handled separately in find()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def find(self, root: Any) -> list[tuple[Path, Any]]:
        """Return all ``(Path, value)`` pairs in *root* that satisfy this query.

        When *path* is a JSONPath string the JSONPath engine is used, which
        supports wildcards (``*``), recursive descent (``..``), and filters.
        Otherwise the full structure is walked with the path/value predicates.
        """
        from ._advanced import walk

        if isinstance(self._path, str):
            results: list[tuple[Path, Any]] = []
            for p in find_paths(root, self._path):
                v = p.resolve()
                if self._value_matches(v):
                    results.append((p, v))
            return results

        path_pred = self._path_predicate()
        assert path_pred is not None  # unreachable; satisfies type checkers

        return [
            (path, value)
            for path, value in walk(root)
            if path_pred(path) and self._value_matches(value)
        ]

    def matches(self, path: Path, value: Any) -> bool:
        """Test whether a single ``(path, value)`` pair satisfies this query.

        Note: when *path* was specified as a JSONPath string with wildcards,
        this method falls back to an exact path comparison (``str(path)``
        equality) because structural pattern-matching a single pair against a
        wildcard expression requires the full root context. Use :meth:`find`
        when wildcard JSONPath matching is needed.
        """
        path_ok: bool
        if self._path is MISSING:
            path_ok = True
        elif isinstance(self._path, str):
            path_ok = str(path) == self._path
        elif callable(self._path):
            path_ok = bool(self._path(path))
        else:
            path_ok = path == Path(self._path)

        return path_ok and self._value_matches(value)

    def __repr__(self) -> str:
        return f"Query(path={self._path!r}, value={self._value!r})"
