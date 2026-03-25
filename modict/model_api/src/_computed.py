from __future__ import annotations

from typing import Any, Mapping, Set, Callable, List, Optional

from ...collections_utils import MISSING

class Computed:
    """Computed value placeholder stored in the container and evaluated on read."""

    def __init__(self, func: Callable, cache: bool = False, deps: Optional[List[str]] = None):
        self.func = func
        self.cache = cache
        if deps is None and hasattr(func, "_computed_deps"):
            deps = func._computed_deps
        self.deps = deps
        self._cached_value = MISSING
        self._cache_valid = False

    def copy(self) -> "Computed":
        return Computed(self.func, self.cache, deps=self.deps)

    def __call__(self, instance):
        if self.cache and self._cache_valid:
            return self._cached_value
        value = self.func(instance)
        if self.cache:
            self._cached_value = value
            self._cache_valid = True
        return value

    def invalidate_cache(self) -> None:
        self._cache_valid = False
        self._cached_value = MISSING

    def should_invalidate_for_keys(self, keys: set) -> bool:
        if not self.cache:
            return False
        if self.deps is None:
            return True
        if len(self.deps) == 0:
            return False
        return bool(set(self.deps) & keys)


def invalidate_dependants(values: Mapping[str, Any], changed_keys: Set[str]) -> None:
    if not changed_keys:
        return

    newly_invalidated: set[str] = set()

    # For dict subclasses (e.g. `modict`), prefer `dict.items()` to avoid any
    # overridden `items()` implementation that might evaluate computed values.
    try:
        items = dict.items(values)  # type: ignore[arg-type]
    except TypeError:
        items = values.items()

    for name, raw in items:
        if not isinstance(raw, Computed):
            continue
        if raw.should_invalidate_for_keys(changed_keys):
            if raw.cache and raw._cache_valid:
                raw.invalidate_cache()
                newly_invalidated.add(name)

    if newly_invalidated:
        invalidate_dependants(values, newly_invalidated)
