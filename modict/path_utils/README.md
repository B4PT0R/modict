# path_utils

Immutable, hashable path objects for navigating nested data (dicts, lists, or objects), built on `jsonpath_ng`.

Used internally by modict. The user-facing entry point is `from modict import Path`.

## Concepts

- `PathNode`: a single step — a key (`int` or `str`) plus an optional reference to the container at that level.
- `Path`: an immutable sequence of `PathNode` instances with helpers for resolution, manipulation, and JSONPath conversion.

## Construction

`Path` accepts a JSONPath string, a tuple/list of keys, or another `Path`:

```python
from modict import Path

p = Path("$.users[0].name")
p = Path(("users", 0, "name"))
p = Path(["users", 0, "name"])
```

With a root bound at construction:

```python
data = {"users": [{"name": "Ada"}]}
p = Path("$.users[0].name", root=data)
assert p.resolve() == "Ada"
```

## Resolution

```python
data = {"users": [{"name": "Ada"}]}
p = Path("$.users[0].name")

# Pass root explicitly
assert p.resolve(data) == "Ada"

# Or bind root first, then resolve without argument
p.set_root(data)
assert p.resolve() == "Ada"
```

Note: `resolve(data)` caches container references in each node, enabling subsequent `resolve()` calls without re-passing the root. If you later try to resolve the same cached `Path` from a different root, a `ResolutionError` is raised. Use `invalidate()` or `set_root()` to reset.

```python
p.invalidate()        # clears all cached container references
p.set_root(other)     # invalidates + binds a new root
```

`exists()` does *not* permanently cache — it restores the prior container state after the check:

```python
p.exists(data)  # True/False, no side effects on the path's internal state
```

## Attribute-style path building

Once a root is bound, paths can be built via attribute/item access on an empty path:

```python
root = Path(root=data)

root.users[0].name.resolve()   # "Ada" — via __getattr__ + __getitem__
root["a-b"]["c d"].resolve()   # for non-identifier keys
```

## Path concatenation

```python
base = Path(("users", 0))
full = base + "name"           # Path(("users", 0, "name"))
full = base + ("name",)        # same
full = base.child("name")      # same
```

`+` also accepts another `Path` on the right-hand side.

## Mutation

Both methods require the relevant container reference to be cached (either from a prior `resolve()` or a bound root):

```python
p = Path("$.users[0].name", root=data)
p.set_inplace("Grace")
p.delete_inplace()
```

## Key access and string representation

```python
p = Path("$.users[0].name")
p.keys          # ("users", 0, "name") — tuple of raw keys
str(p)          # "$.users[0].name" — JSONPath string
p.parent()      # Path(("users", 0))
p.parent(2)     # Path(("users",))
```

## Existence check

```python
p.exists(data)       # True/False, non-destructive
```

## Leaf traversal

```python
for path, value in Path.walk(data):
    print(str(path), value)

# Also walk object attributes (e.g. dataclasses, plain objects)
for path, value in Path.walk(data, walk_objects=True):
    print(str(path), value)
```

## JSONPath queries

`find_paths()` evaluates a JSONPath expression and returns concrete `Path` objects for each match:

```python
from modict.path_utils import find_paths

data = {"users": [{"name": "Ada"}, {"name": "Grace"}]}
paths = find_paths(data, "$.users[*].name")

assert [p.keys for p in paths] == [("users", 0, "name"), ("users", 1, "name")]
assert [p.resolve() for p in paths] == ["Ada", "Grace"]
```

## Notes

- `Path` and `PathNode` are hashable; container references do not affect equality or hash (only the key sequence matters).
- `PathKey` is a legacy alias for `PathNode`.
