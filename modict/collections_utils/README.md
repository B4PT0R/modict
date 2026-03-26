# collections_utils

Infrastructure subpackage for managing collections, paths, and nested data structures in modict.
Provides utilities based on JSONPath (RFC 9535) for navigating and manipulating nested data.

## Modules

### `_types.py` — Type aliases and predicates

```python
from modict.collections_utils import (
    is_container,
    is_mutable_container,
    is_dict_like,
    is_list_like,
)

is_dict_like({'a': 1})     # True  (MutableMapping)
is_list_like([1, 2, 3])    # True  (MutableSequence)
is_container({'a': 1})     # True  (excludes str/bytes/bytearray)
```

Type aliases: `Key`, `Container`, `MutableContainer`, `PathType`, `Namespace`, `MutableCollection`.

- `Namespace`: `MutableMapping` view over a class namespace (`cls.__dict__`); used internally by the metaclass.
- `MutableCollection`: abstract base combining `Collection` + mutable item access (`__getitem__`, `__setitem__`, `__delitem__`).

### `_basic.py` — Container-agnostic key operations

Uniform `get`/`set`/`has`/`keys` that work on both `Mapping` and `Sequence`:

```python
from modict.collections_utils import get_key, set_key, has_key, keys, unroll

has_key(data, 'name')
value = get_key(data, 'name', default='Unknown')
set_key(data, 'name', 'Alice')

for key in keys(data):
    print(key, get_key(data, key))
```

`set_key` on a `MutableSequence` will auto-expand the list for out-of-range indices (filling gaps with `MISSING`) unless `expand=False` is passed. A custom `filler` value can be specified:

```python
items = [1, 2]
set_key(items, 5, 'x', filler=None)
# items == [1, 2, None, None, None, 'x']
```

`unroll(obj)` yields `(key, value)` pairs from any container (equivalent to `.items()` for dicts, `enumerate` for sequences).

### `_advanced.py` — Nested operations

#### Nested access

```python
from modict.collections_utils import (
    get_nested, set_nested, pop_nested, del_nested, has_nested,
)

# All accept JSONPath strings, tuples, or Path objects
value = get_nested(data, 'users[0].name', default=None)
set_nested(data, 'users[0].email', 'alice@example.com')  # creates intermediate containers as needed
has_nested(data, 'users[0].name')   # True/False
val = pop_nested(data, 'users[0].name')   # removes and returns
del_nested(data, 'users[0].name')         # removes (delegates to pop_nested)
```

#### Traversal

```python
from modict.collections_utils import walk, walked, unwalk

# walk yields (Path, value) for every leaf
for path, value in walk(data):
    print(f"{path}: {value}")

# Optional parameters:
# - callback: transform each leaf value
# - filter: predicate(Path, value) -> bool to skip leaves
# - excluded: tuple of types to treat as leaves (default: str, bytes, bytearray)
for path, value in walk(data, callback=str, filter=lambda p, v: v is not None):
    print(path, value)

# walked returns a dict instead of an iterator
snapshot = walked(data)

# unwalk reconstructs from a {Path: value} dict
restored = unwalk(snapshot)
# ignore_types=True forces plain dict/list instead of preserving original container types
restored = unwalk(snapshot, ignore_types=True)
```

#### Deep operations

```python
from modict.collections_utils import deep_merge, deep_equals, diff_nested

# deep_merge: modifies target in-place, returns None
# Mappings merge by key (recursive), sequences merge by index
deep_merge(base_config, overrides)

# conflict_resolver(target_value, src_value) -> merged_value for scalar conflicts
deep_merge(base, patch, conflict_resolver=lambda old, new: new)

# Setting a value to MISSING in src deletes that key from target
from modict.collections_utils import MISSING
deep_merge(target, {'key_to_remove': MISSING})

# diff: returns {Path: (left_value, right_value)}; MISSING means absent on that side
differences = diff_nested(config_a, config_b)

# deep_equals compares by walking both structures — only leaf values and their paths
# matter, not container types (a modict and a plain dict with the same contents are equal)
assert deep_equals(config_a, config_a_copy)
```

### `_view.py` — Collection views

`View` is an abstract base class for read-only views over containers. Subclass it and implement `_get_element(key)`:

```python
from modict.collections_utils import View

class ValuesView(View):
    def _get_element(self, key):
        return self.data[key]

view = ValuesView(my_dict)
list(view)          # all values
len(view)           # same as len(my_dict)
'x' in view         # membership test
```

### `_missing.py` — MISSING sentinel

```python
from modict.collections_utils import MISSING

def func(arg=MISSING):
    if arg is MISSING:
        # not provided
        ...
```

`MISSING` is also used by `deep_merge` as a deletion signal and by `diff_nested` to indicate an absent value on one side.

### `_json.py` — JSON serialization helpers

```python
from modict.collections_utils import to_jsonable, json_dumps
from datetime import datetime

# to_jsonable: recursively converts to JSON-safe types
# - Mapping → dict
# - tuple/set/Sequence → list
# - leaves are passed through as-is (json.dumps raises if non-serializable and no encoder matches)
payload = to_jsonable(
    {"ts": datetime(2020, 1, 1), "tags": {"a", "b"}},
    encoders={datetime: lambda dt: dt.isoformat()},
    exclude_none=True,      # drop keys with None values
    use_enum_values=False,  # if True, Enum → .value
)

# json_dumps: to_jsonable + json.dumps in one call
text = json_dumps(payload, encoders={...}, exclude_none=True, indent=2, sort_keys=True)
```

### `_query.py` — Query

`Query` combines a path constraint and a value constraint into a single searchable object.

```python
from modict import Query, MISSING

# path : MISSING (any — default), JSONPath str (wildcards ok), Path/tuple (exact), callable(Path)->bool
# value: MISSING (any — default), callable(value)->bool, or any literal including None (equality check)

# All users with age > 30
Query("$.users[*].age", lambda v: v > 30).find(data)

# Any leaf whose last key is "email"
Query(lambda p: p.keys[-1] == "email").find(data)

# Exact path, exact value
Query(("users", 0, "name"), "Alice").find(data)

# Find all leaves whose value is None (not "no constraint" — that would be MISSING)
Query(value=None).find(data)

# Value predicate only — walks everything
Query(value=lambda v: isinstance(v, str) and "@" in v).find(data)
```

`find(root)` returns a `list[tuple[Path, Any]]` — consistent with `walk`.

When `path` is a JSONPath string the JSONPath engine is used (supports `*`, `..`, filters, etc.). Otherwise the full structure is walked with the predicates.

`matches(path, value)` tests a single pair. Note: wildcard JSONPath strings fall back to exact `str(path)` comparison in `matches` — use `find` when wildcard matching is needed.

## Path support

`Path` and `PathNode` are re-exported from `modict.path_utils`. See [../path_utils/README.md](../path_utils/README.md) for full documentation.

```python
from modict.collections_utils import Path, PathNode

p = Path("$.users[0].name")
value = p.resolve(data)
```
