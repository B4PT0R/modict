# modict

`modict` (short for 'model dict' or 'modern dict') is a modern, dict-first data structure.

It's a `dict` subclass with an optional model-like layer (typed fields, factories, validators, computed values).

Where it sits compared to Pydantic:

- `modict` is when you want the mutability of a **real `dict`** (all familiar dict methods, native MutableMapping interface, code expecting dict instances) and only need **lightweight, opt-in modeling** on top.
- Pydantic is best when you want a **pure "model" abstraction** (`BaseModel`), strong tooling/ecosystem, advanced model features, and you don't need `dict` subclass semantics.

In practice, for many basic use cases (a small typed container, a couple of defaults/validators/computed properties, light validation, JSON output), the two are **roughly interchangeable**. The real differences show up in more advanced scenarios: ecosystem/tooling, strict contract modeling, serialization knobs, and whether you want to stay dict-first (`modict`) or model-first (Pydantic).


**Use cases (when to pick what)**

`modict` shines when:
- You want **plasticity while prototyping**: start with free-form data, progressively add hints/validators/computed as your shape stabilizes.
- You need a **dict-first internal representation** for config and data manipulation (configs, JSON-like payloads, ETL/transform pipelines) and you want to keep that surface area.
- You need ergonomic nested manipulation (JSONPath/`Path`, `get_nested`/`set_nested`, `walk`/`unwalk`, deep diffing/comparison) without introducing a separate model layer everywhere.
- You want "some structure" (types/validators/computed) but still allow extra keys and mutable updates during processing.

Pydantic shines when:
- You need a **clear data contract** and rich validation/serialization options for **API communication** (request/response models, SDKs, schemas).
- You want strict model semantics and a large ecosystem of integrations (FastAPI, settings, plugins, community conventions).
- Validation/schema generation is the primary goal and you don't need `dict` subclass behavior.
- You're building an API or SDK where models are a public contract and stability/tooling matter more than dict ergonomics.

## Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Path-Based Tools](#path-based-tools)
- [Core Concepts](#core-concepts)
- [Field Definition](#field-definition)
- [Factories](#factories)
- [Validators](#validators)
- [Computed Fields](#computed-fields)
- [Validation Pipeline](#validation-pipeline)
- [Configuration (Deep Dive)](#configuration-deep-dive)
- [Type Checking & Coercion](#type-checking--coercion)
- [Serialization](#serialization)
- [Deep Conversion & Deep Ops](#deep-conversion--deep-ops)
- [Package Tour (Internal Modules)](#package-tour-internal-modules)
- [Public API Reference](#public-api-reference)
- [Development](#development)
- [Contributing](#contributing)
- [License](#license)

## Installation

```bash
pip install modict
```

Requirements:
- Python 3.10+
- JSONPath support relies on `jsonpath-ng` (the only external dependency)

## Quick Start

### Use it as a dict (default)

```python
from modict import modict

m = modict({"user": {"name": "Alice"}, "count": 1})

assert m["count"] == 1
assert m.user.name == "Alice"       # attribute access for keys

m.extra = 123                       # extra keys are allowed by default
assert isinstance(m, dict)          # True: modict is a real dict
```

### Define a typed modict class with defaults

```python
from modict import modict

class User(modict):
    name: str            # annotation-only: not required, but validated/coerced if provided
    age: int = 25        # default value
    country: str = "FR"  # another default (not passed at init)

u = User({"name": "Alice", "age": "30"})
assert u.age == 30                  # best-effort coercion unless strict=True
assert u.country == "FR"
```

Tip: Annotated fields without defaults are not required by default; they provide type validation/coercion when the key is present. Plain annotations and class defaults are enough for most fields. Use `modict.field(...)` when you need more control (required flag, explicit hint).

## Path-Based Tools

`modict` comes with a consistent path system for reading/writing nested structures (including inside lists), plus a `Path` object for disambiguation and introspection.

### Supported path formats

You can target nested values using:
- **JSONPath strings** (RFC 9535): `$.users[0].name`
- **Tuples** of keys/indices: `("users", 0, "name")`
- **`Path` objects**: `Path("$.users[0].name")`

### The `Path` object

`Path` is a parsed, strongly-typed representation of a nested path.

```python
from modict import Path

p = Path("$.users[0].name")
assert p.keys == ("users", 0, "name")   # .keys is a property
assert str(p) == "$.users[0].name"      # __str__ renders back to JSONPath
```

Internally, a `Path` is a tuple of `PathNode` components. Each node carries:
- the **key/index** (`"users"`, `0`, `"name"`)
- the **origin container class** (`dict`, `list`, …) when it can be inferred (`container_class`), which lets `walk()` → `unwalk()` preserve container types.

All nested helpers accept JSONPath strings, tuples, or `Path` objects interchangeably.

### Nested operations

```python
from modict import modict

m = modict({"user": {"name": "Alice"}})

m.get_nested("$.user.name")           # "Alice"
m.set_nested("$.user.age", 30)
m.has_nested("$.user.age")            # True
m.pop_nested("$.user.age")            # 30
```

### Paths in deep traversal

- `walk()` yields `(Path, value)` leaf pairs.
- `walked()` returns a `{Path: value}` mapping.
- `unwalk(walked)` reconstructs a nested structure from a `{Path: value}` mapping, preserving container classes when possible.

## Core Concepts

- `modict` is a real `dict`: it supports standard dict operations and behaves like a mutable mapping.
- A `modict` *class* can declare fields with type annotations and `modict.field(...)`.
- The model-like behavior is controlled by the `_config` class attribute (a `modictConfig` dataclass):

```python
class User(modict):
    _config = modict.config(extra="allow")  # see "Configuration (Deep Dive)" for full reference
```

## Field Definition

The recommended public entry-point is `modict.field(...)`:

```python
modict.field(
    default=MISSING,
    hint=None,       # None = use class annotation when provided
    required=False,  # only required when explicitly True
    validators=None, # internal: used by the metaclass when collecting @modict.validator(...)
)
```

Example (explicit defaults):

```python
from modict import modict, MISSING

class User(modict):
    name: str = modict.field(default=MISSING, required=True)
    age = modict.field(default=25, hint=int)

u = User({"name": "Alice", "age": "30"})
assert u.age == 30
```

Note: if you pass `hint=...` explicitly in `modict.field(...)`, it takes precedence over the class annotation.

## Factories

Use `modict.factory(callable)` to define **dynamic defaults** (a fresh value per instance), similar to Pydantic's `default_factory`. This is essential for mutable defaults like lists or dicts — without it, all instances would share the same object.

```python
from modict import modict

class User(modict):
    name: str
    tags: list[str] = modict.factory(list)  # new list per instance

u1 = User(name="Alice")
u2 = User(name="Bob")
u1.tags.append("python")
assert u2.tags == []
```

## Validators

### Field validators

Use `@modict.validator(field_name, mode="before"|"after")` to validate and/or transform a single field value.

- `mode="before"` (default): runs before coercion and type checking — receives the raw input value. This is the right place for type-changing transforms.
- `mode="after"`: runs after coercion and type checking — receives the already-typed value. Should return a value of the same type (or raise). The type is not re-checked after this step, so returning a different type silently bypasses the hint.

```python
from modict import modict

class User(modict):
    email: str

    @modict.validator("email")
    def normalize_email(self, value):
        return value.strip().lower()

u = User(email="  ALICE@EXAMPLE.COM ")
assert u.email == "alice@example.com"
```

### Model validators (cross-field invariants)

Use `@modict.model_validator(mode="before"|"after")` for checks that span multiple fields.

In `mode="after"`, the instance is already fully populated and all field validators have run. The method receives `(self, values)` where `values` is the final dict of field values.

```python
from modict import modict

class Range(modict):
    start: int
    end: int

    @modict.model_validator(mode="after")
    def check_order(self, values):
        if values["start"] > values["end"]:
            raise ValueError("start must be <= end")
```

## Computed Fields

Computed fields are virtual values evaluated on access. They are stored as `Computed` objects inside the dict and evaluated via `__getitem__`.

```python
from modict import modict

class Calc(modict):
    a: int
    b: int

    @modict.computed(cache=True, deps=["a", "b"])
    def sum(self) -> int:
        return self.a + self.b

c = Calc(a=1, b=2)
assert c.sum == 3
c.a = 10
assert c.sum == 12  # cache invalidated because "a" changed
```

Inline (non-decorator) form:

```python
class Calc(modict):
    a: int
    b: int
    sum = modict.computed(lambda m: m.a + m.b, cache=True, deps=["a", "b"])
```

Inline "dict value" form (no subclass):

```python
m = modict({"a": 1, "b": 2})
m["sum"] = modict.computed(lambda m: m.a + m.b)
assert m.sum == 3
```

Notes:
- Computed values still go through the validation pipeline (type checks, JSON serializability check, …) when enabled.
- Cache invalidation semantics:
  - `deps=None` (default): invalidate on any key change.
  - `deps=[...]`: invalidate only when one of the listed keys changes (can include other computed names).
  - `deps=[]`: never invalidate automatically.

Manual invalidation:

```python
m = modict({"a": 1, "b": 2})
m["sum"] = modict.computed(lambda m: m.a + m.b, cache=True, deps=[])

_ = m.sum  # cached
m.a = 10   # deps=[] → no auto-invalidation
assert m.sum == 3

m.invalidate_computed("sum")
assert m.sum == 12

# or invalidate all at once:
m.invalidate_computed()
```

## Validation Pipeline

The pipeline is controlled by `_config.check_values`:
- `check_values="auto"` (default): enabled when the class looks model-like (has hints, validators, or relevant config).
- `check_values=True`: always enabled.
- `check_values=False`: bypassed (pure dict behavior).

Related config flags:
- `strict`: when `True`, no coercion is attempted — values must already match the declared type.
- `validate_assignment`: when `True` (default), every assignment goes through the full pipeline (coercion, type check, validators). Set to `False` to only run validation at init time.
- `enforce_json`: when `True`, values must be JSON-serializable after processing.

When enabled, the pipeline runs:
- eagerly at initialization (`__init__` → `validate()`)
- on each assignment when `validate_assignment=True`
- on reads of computed fields (`__getitem__` evaluates and then validates the returned value)

Order of operations for a field value:

1. field validators in `mode="before"` (receive raw input)
2. coercion (only when `strict=False`)
3. type check against hint (if the field has a type annotation)
4. field validators in `mode="after"` (receive coerced, typed value)
5. JSON-serializability check (`enforce_json=True`, with optional encoders)

If any step raises, the whole assignment is rejected.

## Configuration (Deep Dive)

All model-like behavior is controlled by the class attribute `_config`, a `modictConfig` dataclass created via `modict.config(...)`.
Only modict-supported options are accepted — unknown keys raise `TypeError`.

```python
class User(modict):
    _config = modict.config(
        check_values="auto",
        extra="allow",
        strict=False,
        validate_assignment=True,  # default
        auto_convert=True,
    )
```

### Config reference

- `check_values`: `True`/`False`/`"auto"`.
  - `"auto"` enables the pipeline when the class *looks model-like*: it has hints, validators, model validators, or config constraints (e.g. `extra != "allow"`, `enforce_json=True`, `strict=True`, …).
- `check_keys`: `True`/`False`/`"auto"`.
  - Key-level constraints are *structural* checks (presence/allowed-keys/invariants), separate from value validation.
  - `"auto"` enables key constraints when the model declares them (e.g. `extra != "allow"`, `require_all=True`, computed fields, or any field with `required=True`).
  - When `False`, `modict` behaves more like a plain dict regarding keys: `required=True`, `require_all=True`, `extra="forbid"/"ignore"`, and computed overwrite/delete protection are all skipped.
  - `frozen=True` is always enforced regardless of `check_keys`.

Example: keep structure strict but skip value coercion/type checking:

```python
class Msg(modict):
    _config = modict.config(check_values=False, check_keys=True, extra="forbid")
    role: str = modict.field(required=True)
    content: str = modict.field(required=True)
```

- `extra`: `"allow"` (default) / `"forbid"` / `"ignore"`.
  - `"forbid"` raises on unknown keys at init and on assignment.
  - `"ignore"` drops unknown keys silently.
- `strict`: when `True`, disables coercion (type checking still applies when hints exist).
- `validate_assignment`: when `True` (default), every assignment re-runs the full pipeline. Set to `False` to only validate at init.
- `frozen`: when `True`, `__setitem__` / `__delitem__` raise — effectively read-only instances.
- `auto_convert`: when `True` (default), values stored in nested mutable containers are lazily upgraded on access:
  - nested plain `dict` → `modict` (plain `modict`, not your subclass)
  - applies recursively inside lists, tuples, sets, and dicts as you touch them.
- `enforce_json`: when `True`, values must be JSON-serializable after the pipeline runs.
  - `allow_inf_nan`: controls whether `NaN`/`Infinity` pass the JSON check (default: `True`).
  - `json_encoders`: a `{type: callable}` mapping used as fallback encoders by `dumps()`/`dump()`.
- `validate_default`: when `True`, default field values are type-checked at class creation time (skips `Factory`/`Computed`).
- `from_attributes`: when `True`, `MyModict(obj)` can read declared fields from `obj.field` attributes (when `obj` is not a mapping).
- `override_computed`: when `False` (default), computed fields are protected: you cannot overwrite or delete them, and you cannot pass initial values for them at construction. Set to `True` to allow it explicitly.
- `require_all`: when `True`, all declared class fields must be present at initialization; annotation-only fields become required and cannot be deleted.
- `evaluate_computed`: when `True` (default), computed fields are evaluated on access. When `False`, the `Computed` object itself is returned (pure storage mode, no evaluation).

Required vs defaults (dict-first semantics):
- A class default (e.g. `age: int = 25`) is an *initializer*: injected once at construction if missing, but still removable later when `require_all=False`.
- A field is an invariant only when you opt in: set `required=True` on the field (or `require_all=True` on the model) to enforce presence.

### Performance / dict-like mode

If you want `modict` to behave as close as possible to a plain `dict` (minimal overhead), opt out of most advanced features:

```python
class Fast(modict):
    _config = modict.config(
        check_values=False,      # skip validation/coercion pipeline
        check_keys=False,        # skip structural key constraints (required/extra/...)
        auto_convert=False,      # skip lazy conversion of nested containers on access
        evaluate_computed=False  # treat Computed as raw stored objects
    )
```

### Config inheritance / merging

`modict` merges configs across inheritance in a Pydantic-like way:
- config values explicitly set in a subclass override inherited values
- when using multiple inheritance, the left-most base wins (for explicitly-set config keys)

```python
class Base(modict):
    _config = modict.config(extra="forbid")
    x: int

class Child(Base):
    y: int = 0
    # inherits extra="forbid"

class Override(Child):
    _config = modict.config(extra="allow")
    # extra is now "allow", rest inherited from Base/Child
```

## Type Checking & Coercion

`modict` relies on its internal runtime type system (`modict/typechecker/`) for:
- type checking against annotations (`check_type(hint, value)`)
- best-effort coercion (`coerce(value, hint)`) when `strict=False`
- the `@typechecked` decorator for runtime checking of function arguments/return values

This subsystem supports common `typing` constructs (`Union`, `Optional`, `list[str]`, `dict[str, int]`, `tuple[T, ...]`, ABCs from `collections.abc`, …).

When coercion fails, the original value is kept; the subsequent type check then decides whether it's accepted (based on hints and `strict` mode). This means `strict=False` is permissive but not silent — type mismatches still raise if the hint doesn't match.

## Serialization

`modict` uses a JSON-like API backed by `json.dumps`/`json.dump`/`json.loads`/`json.load`.

### `dumps` / `dump` (output)

Serialize a `modict` instance to a JSON string or file. Both methods accept:
- `exclude_none`: drop keys with `None` values
- `encoders`: `{type: callable}` mapping for custom serialization (overrides `json_encoders` from config)

```python
from datetime import datetime
from modict import modict

class Event(modict):
    _config = modict.config(json_encoders={datetime: lambda d: d.isoformat()})
    name: str
    ts: datetime

e = Event(name="launch", ts=datetime(2024, 1, 1))
print(e.dumps())
# {"name": "launch", "ts": "2024-01-01T00:00:00"}
```

`json_encoders` in `_config` serves as the default encoder table for all `dumps()`/`dump()` calls on that class. You can override it per-call by passing `encoders=...` directly.

```python
e.dumps(encoders={datetime: lambda d: d.timestamp()})
# {"name": "launch", "ts": 1704067200.0}
```

`dump()` writes to a file path or file-like object:

```python
e.dump("event.json")
```

### `loads` / `load` (input)

Class-level methods that parse JSON and return a `modict` instance:

```python
m = modict.loads('{"name": "launch", "ts": "2024-01-01T00:00:00"}')
m = modict.load("event.json")
```

These are thin wrappers around `json.loads`/`json.load` — no custom deserialization logic is applied. For typed deserialization with coercion, construct from the parsed dict directly:

```python
data = modict.loads('{"name": "launch", "ts": "2024-01-01T00:00:00"}')
event = Event(**data)  # pipeline runs: coercion, type checks, validators, ...
```

### `to_jsonable`

For serialization beyond JSON (e.g. YAML, MessagePack), `to_jsonable(obj, encoders)` from `modict.collections_utils` recursively converts a structure to plain JSON-safe types (dicts, lists, primitives). This is what `dumps`/`dump` use internally.

## Deep Conversion & Deep Ops

### Deep conversion

`modict` ships with conversion utilities that preserve container identity as much as possible:
- `modict.convert(obj)`: recursively upgrades `dict` nodes to `modict` (and walks into mutable containers).
  - The root dict becomes your class; nested dicts become plain `modict` unless they were already instances.
  - `recurse=False` stops recursion when reaching a `modict` node (used internally for lazy `auto_convert`).
- `m.to_modict()`: deep conversion of an instance in-place (calls `convert(self)`).
- `m.to_dict()`: deep un-conversion back to plain containers.

### Deep operations on nested structures

- `walk()` / `walked()`: flatten a nested structure to `(Path, value)` pairs.
- `unwalk(walked)`: reconstruct a nested structure from a `{Path: value}` mapping, preserving container classes when possible.
- `merge(mapping)`: deep, in-place merge (mappings merge by key; sequences merge by index). Returns `None` — modifies in place.
- `diff(mapping)`: deep diff — returns `{Path: (left, right)}` with `MISSING` for absent values.
- `diffed(mapping)`: minimal nested patch — returns a plain modict containing only the changes needed so that `self.merge(self.diffed(other))` equals `other`. Keys removed in `other` are set to `MISSING`.
- `deep_equals(mapping)`: deep equality by comparing walked representations (container types are ignored — a modict and a plain dict with the same leaves are equal). Use this when cross-type equality is needed; `==` uses the native dict comparison (type-sensitive).

## Package Tour (Internal Modules)

This section is an overview of the main internal modules and what functionality they implement.
If you only need the user-facing API, skip to [Public API Reference](#public-api-reference).

### `modict/core/` (the `modict` class)

Core behaviors implemented here:
- dict subclass with attribute access (`m.key` ↔ `m["key"]`) while keeping Python attributes working
- validation pipeline (`validate()`, assignment validation, extra handling)
- computed fields evaluation and dependency-based cache invalidation
- lazy nested conversion (`auto_convert`) implemented in `__getitem__`
- nested ops (`get_nested`, `set_nested`, `pop_nested`, …) backed by JSONPath/`Path`
- deep ops (`walk`, `walked`, `unwalk`, `merge`, `update`, `diff`, `diffed`, `deep_equals`, `deepcopy`)
- JSON helpers (`loads`, `load`, `dumps`, `dump`)
- `modictMeta`: collects declared fields from `__annotations__` and assigned attributes
  - supports plain defaults, `modict.field(...)` (`Field`), `modict.factory(...)` (`Factory`), and `@modict.computed(...)` (`Computed`)
  - collects `@modict.validator(...)` into per-field validators
  - collects `@modict.model_validator(...)` into model-level validators
- `modictConfig`: configuration object with explicit-key tracking and inheritance merge semantics
- `modictKeysView` / `modictValuesView` / `modictItemsView`: dict views that read through `__getitem__` (so computed fields, lazy conversion, and validation all apply during iteration)

### `modict/collections_utils/` (nested structure utilities)

This package is responsible for paths, nested operations, and deep traversal. See [modict/collections_utils/README.md](modict/collections_utils/README.md) and [modict/path_utils/README.md](modict/path_utils/README.md) for more details.

- `_path.py`: `Path` / `PathNode` — JSONPath (RFC 9535) parsing and formatting via `jsonpath-ng`.
  - Type-aware path components (`PathNode.container_class`) so `walk()` → `unwalk()` can preserve container types.
  - `Path.normalize(...)` to accept JSONPath strings, tuples, or `Path` objects.
- `_basic.py`: container-agnostic `get_key` / `set_key` / `has_key` / `keys` / `unroll`.
- `_advanced.py`: `get_nested` / `set_nested` / `pop_nested` / `del_nested` / `has_nested`, `walk` / `walked` / `unwalk`, `deep_merge` / `diff_nested` / `deep_equals`.
- `_view.py`: `View` — base class for custom collection views over mappings or sequences.
- `_missing.py`: `MISSING` sentinel to distinguish "absent" from `None`.

### `modict/typechecker/` (runtime typing + coercion)

See [modict/typechecker/README.md](modict/typechecker/README.md) for more details.

- `TypeChecker`: checks values against `typing` hints and collection ABCs.
- `Coercer`: best-effort conversions for common hints/containers.
- Convenience API: `check_type`, `coerce`, `can_coerce`, and `typechecked`, `coerced` for decorator-based type checking and coercion on functions.

### `modict/model_api/` (field system)

- `Field`, `Factory`, `Computed`: field descriptor types used by `modictMeta` during class creation.
- `Validator`, `ModelValidator`: signature adapters for common call styles (allow flexible validator signatures).
- `build_fields_and_model_validators`: metaclass helper that collects fields and validators from a class dict.

## Public API Reference

This section lists the public symbols exported by `modict` and the main methods on `modict` instances.

### Exports

From `from modict import ...`:

- Data structure:
  - `modict`
- Field system:
  - `Field` (advanced; most users should prefer `modict.field(...)`)
  - `Factory` (advanced; most users should prefer `modict.factory(...)`)
  - `Computed` (advanced; most users should prefer `@modict.computed(...)`)
  - `Validator`, `ModelValidator` (advanced; decorators are the typical entry-point)
- Config:
  - `modictConfig` (usually created via `modict.config(...)`)
- JSONPath types:
  - `Path`, `PathNode`
- Sentinel:
  - `MISSING`
- Search:
  - `Query(path=MISSING, value=MISSING)` — combined path + value constraint; `.find(root)` returns matching `(Path, value)` pairs. `MISSING` means "no constraint"; `None` as `value` matches leaves whose value is literally `None`
- Type checking / coercion:
  - `check_type(hint, value)`
  - `coerce(value, hint)`
  - `can_coerce(value, hint)`
  - `typechecked` (decorator)
  - `TypeChecker`
  - `Coercer`
  - Exceptions: `TypeCheckError`, `TypeCheckException`, `TypeCheckFailureError`, `TypeMismatchError`, `CoercionError`

### `modict` class methods

- `modict.config(**kwargs) -> modictConfig`
- `modict.field(...) -> Field`
- `modict.factory(callable) -> Factory`
- `@modict.validator(field_name, mode="before"|"after")`
- `@modict.model_validator(mode="before"|"after")`
- `@modict.computed(cache=False, deps=None)`
- JSON helpers:
  - `modict.loads(s, **json_kwargs) -> modict`
  - `modict.load(fp_or_path, **json_kwargs) -> modict`
- Conversion:
  - `modict.convert(obj, seen=None) -> Any`
  - `modict.unconvert(obj, seen=None) -> Any`
  - `modict.unwalk(walked: dict[Path, Any]) -> Any`

### `modict` instance methods

Instance methods keep standard dict behavior, plus:

- Validation:
  - `validate()`
- Conversion:
  - `to_modict() -> modict` (deep conversion)
  - `to_dict() -> dict` (deep unconvert)
- Serialization:
  - `dumps(exclude_none=False, encoders=None, **json_kwargs) -> str`
  - `dump(fp_or_path, exclude_none=False, encoders=None, **json_kwargs) -> None`
- Nested operations (JSONPath / tuple / Path):
  - `get_nested(path, default=MISSING)`
  - `set_nested(path, value)`
  - `del_nested(path)`
  - `pop_nested(path, default=MISSING)`
  - `has_nested(path) -> bool`
- Key operations:
  - `rename(mapping_or_kwargs) -> None` (in-place)
  - `exclude(*keys) -> modict`
  - `extract(*keys) -> modict`
  - `find(query=MISSING, *, path_constraint=MISSING, value_constraint=MISSING) -> Generator` — lazily yields `(Path, value)` pairs matching a `Query` or inline constraints (deep)
  - `found(query=MISSING, *, path_constraint=MISSING, value_constraint=MISSING) -> modict` — same, returned as a `{Path: value}` modict
- Deep operations:
  - `merge(mapping) -> None` (in-place)
  - `update(other=(), /, **kwargs) -> None` — like `dict.update()` but routes through validation
  - `diff(mapping) -> dict[Path, tuple]`
  - `diffed(mapping) -> modict` — minimal nested patch; `self.merge(self.diffed(other))` equals `other`
  - `deep_equals(mapping) -> bool`
  - `deepcopy() -> modict`
- Walking:
  - `walk(callback=None, filter=None, excluded=None) -> Iterable[tuple[Path, Any]]`
  - `walked(callback=None, filter=None) -> dict[Path, Any]`
- Computed cache:
  - `invalidate_computed(*names) -> None` (no args = all)

## Development

```bash
python3 -m pytest -q
```

## Contributing

Contributions are welcome.

- Please open an issue to discuss larger changes.
- For pull requests: add/adjust tests under `tests/` and keep `python3 -m pytest -q` green.
- Local setup: `pip install -e ".[dev]"`.

See `CONTRIBUTING.md` for details.

## License

MIT. See `LICENSE`.
