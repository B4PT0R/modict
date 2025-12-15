# modict

`modict` (short for 'model dict' or 'modern dict') is a modern, dict-first data structure designed to interop nicely with Pydantic models.

It’s a `dict` subclass with an optional model-like layer (typed fields, factories, validators, computed values, JSON Schema export) and easy class-level conversion to/from Pydantic Models.

Core philosophy: keep `dict` ergonomics and compatibility, gradually opt into stronger model semantics when you want them, and eventually convert to an actual Pydantic model where it matters.

Where it sits compared to Pydantic:

- `modict` is best when you want a **real `dict`** (all familiar dict methods, native MutableMapping interface, code expecting dict instances) and only need **lightweight, opt-in modeling** on top.
- Pydantic is best when you want a **pure “model” abstraction** (`BaseModel`), strong tooling/ecosystem, advanced Model features, and you don’t need `dict` subclass semantics.

In practice, for many basic use cases (a small typed container, a couple of defaults/validators/computed properties, light validation, JSON/schema output), the two are **roughly interchangeable**. The real differences tend to show up in more advanced scenarios: ecosystem/tooling, strict contract modeling, serialization knobs, and whether you want to stay dict-first (`modict`) or model-first (Pydantic).

`modict` makes it so that **you don't have to choose**. Start coding with `modict` as a drop-in replacement of `dict`, add hints/validators/computed as you go, and convert to Pydantic at API/SDK boundaries if you need to.

**Pros / cons (high level)**

`modict` pros:
- Drop-in `dict` behavior + attribute access (no wrapper object).
- Incremental adoption: start dict-first, add hints/validators/computed as needed.
- Built-in nested path utilities (`Path`/JSONPath, `get_nested`/`set_nested`, `walk`/`unwalk`) for working with arbitrary nested data.
- clean `modict` -> Pydantic interop for class-level conversion.

`modict` cons:
- Smaller ecosystem than Pydantic (fewer integrations, conventions, docs, plugins).
- Model layer is intentionally minimal; some advanced Pydantic behaviors don’t have 1:1 equivalents.
- Pydantic -> `modict` interop is best-effort (especially for computed/deps and Pydantic-only features).
- Type checking/coercion is implemented in pure Python (no Rust-backed speedups).

Pydantic pros:
- Very mature validation/serialization ecosystem and widespread integration.
- Clear model semantics (`BaseModel`) with strong schema generation and tooling.

Pydantic cons (in a `dict`-centric codebase):
- Not a `dict` subclass; no native `update`, `setdefault`, etc. bridging to/from mappings is explicit.
- Model usage can be heavier than needed when you mainly want “a dict with model-like capabilities”.

**Use cases (when to pick what)**

`modict` shines when:
- You want **plasticity while prototyping**: start with free-form data, progressively add hints/validators/computed as your shape stabilizes.
- You need a **dict-first internal representation** for config and data manipulation (configs, JSON-like payloads, ETL/transform pipelines) and you want to keep that surface area.
- You need ergonomic nested manipulation (JSONPath/`Path`, `get_nested`/`set_nested`, `walk`/`unwalk`, deep `diffing`/`comparison`) without introducing a separate model layer everywhere.
- You want “some structure” (types/validators/computed/schema) but still allow extra keys and mutable updates during processing.
- You want to interop with Pydantic at boundaries (API/SDK layer) but keep a dict-first representation internally.

Pydantic shines when:
- You need a **clear data contract** and rich validation/serialization options for **API communication** (request/response models, SDKs, schemas).
- You want strict-ish model semantics and a large ecosystem of integrations (FastAPI, settings, plugins, community conventions).
- Validation/schema generation is the primary goal and you don’t need `dict` subclass behavior.
- You’re building an API or SDK where models are a public contract and stability/tooling matter more than dict ergonomics.

## Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Use Cases](#use-cases-when-to-pick-what)
- [Path-Based Tools](#path-based-tools)
- [Core Concepts](#core-concepts)
- [Field Definition](#field-definition)
- [Factories](#factories)
- [Validators](#validators)
- [Computed Fields](#computed-fields)
- [Validation Pipeline](#validation-pipeline)
- [Configuration (Deep Dive)](#configuration-deep-dive)
- [Aliases](#aliases)
- [Type Checking & Coercion](#type-checking--coercion)
- [Serialization](#serialization)
- [JSON Schema](#json-schema)
- [Deep Conversion & Deep Ops](#deep-conversion--deep-ops)
- [Pydantic Interop (Optional)](#pydantic-interop-optional)
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
- JSONPath support relies on `jsonpath-ng` (the only dependency of the package!)
- Pydantic interoperability is optional (only needed if you call `from_model()` / `to_model()`)

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

Tip: Annotated fields without defaults are not required; they mainly provide type validation/coercion when the key is present. Annotations and regular class defaults are enough for most fields. Use `modict.field(...)` later when you need more control (constraints, aliases, metadata).

## Path-Based Tools

`modict` comes with a small, consistent path system for reading/writing nested structures (including inside lists), plus a `Path` object for disambiguation and introspection.

### Supported path formats

You can target nested values using:
- **JSONPath strings** (RFC 9535): `$.users[0].name`
- **Tuples** of keys/indices: `("users", 0, "name")`
- **`Path` objects**: `Path.from_jsonpath("$.users[0].name")`

JSONPath strings must start with `$`. Legacy dot-notation (like `"users.0.name"`) is rejected to avoid ambiguity (see `MIGRATION.md`).

### The `Path` object

`Path` is a parsed, strongly-typed representation of a nested path.

```python
from modict import Path

p = Path.from_jsonpath("$.users[0].name")
assert p.to_tuple() == ("users", 0, "name")
assert p.to_jsonpath() == "$.users[0].name"
```

Internally, a `Path` is a tuple of `PathKey` components. Each component carries:
- the **key/index** (`"users"`, `0`, `"name"`)
- the **origin container class** (`dict`, `list`, …) when it can be inferred (`container_class`), which lets `walk()` → `unwalk()` preserve container types.

`Path.normalize(...)` (used by nested helpers) accepts JSONPath strings, tuples, or `Path` objects and returns a `Path`.

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

- `walk()` yields `(Path, value)` leaf pairs (paths are `Path` objects).
- `walked()` returns a `{Path: value}` mapping.
- `unwalk(...)` reconstructs a nested structure from `{Path: value}`, preserving container classes when possible.

## Core Concepts

- `modict` is a real `dict`: it supports standard dict operations and behaves like a mutable mapping.
- A `modict` *class* can declare fields with type annotations + `modict.field(...)`.
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
    hint=None,         # None = use class annotation when provided
    required=False,    # only required when explicitly True
    metadata=None,     # docs / schema metadata (no runtime semantics)
    constraints=None,  # JSON-Schema-like constraints (enforced + exported)
    aliases=None,      # input aliases / serialization alias
    validators=None,   # internal: used by the metaclass when collecting @modict.validator(...)
)
```

Example (explicit defaults + constraints):

```python
from modict import modict, MISSING

class User(modict):
    name: str = modict.field(default=MISSING, required=True)
    age = modict.field(default=25, constraints={"ge": 0}, hint=int)

u = User({"name": "Alice", "age": "30"})
assert u.age == 30
```

Note: if you pass `hint=...` explicitly in `modict.field(...)`, it takes precedence over the class annotation.

### `metadata` (documentation-only)

`metadata` is for documentation/schema hints (not validation). Common keys:
- `title`: str
- `description`: str
- `examples`: any JSON-serializable value (often a list)
- `deprecated`: bool

### `constraints` (validation + JSON Schema)

Constraints are enforced at runtime and exported in `json_schema()`:
- numbers: `gt`, `ge`, `lt`, `le`, `multiple_of`
- strings / sized containers: `min_length`, `max_length`, `pattern`

```python
class Product(modict):
    sku: str = modict.field(constraints={"pattern": r"^[A-Z]{3}-\\d{4}$"})
    price: float = modict.field(constraints={"gt": 0})

Product({"sku": "ABC-0001", "price": 9.99})
```

## Factories

Use `modict.factory(callable)` to define **dynamic defaults** (a new value for every instance), similar to Pydantic’s `default_factory`.

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

Use `@modict.validator(field_name, mode="before"|"after")` to validate and/or transform a single field.

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

Use `@modict.model_validator(mode="before"|"after")` for multi-field checks.
In `mode="after"`, the instance is already populated and validated field-by-field.

```python
from modict import modict

class Range(modict):
    start: int
    end: int

    @modict.model_validator(mode="after")
    def check_order(self):
        if self.start > self.end:
            raise ValueError("start must be <= end")
```

## Computed Fields

Computed fields are virtual values evaluated on access.

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
from modict import modict

class Calc(modict):
    a: int
    b: int
    sum = modict.computed(lambda m: m.a + m.b, cache=True, deps=["a", "b"])
```

Inline “dict value” form (no subclass):

```python
from modict import modict

m = modict({"a": 1, "b": 2})
m["sum"] = modict.computed(lambda m: m.a + m.b)
assert m.sum == 3
```

Notes:
- computed values are stored as `Computed` objects inside the dict and evaluated via `__getitem__`
- returned values still go through the validation pipeline (type checks, constraints, JSON, …) when enabled
- invalidation semantics:
  - `deps=None` (default): invalidate on any key change
  - `deps=[...]`: invalidate only when one of those keys changes (can include other computed names)
  - `deps=[]`: never invalidate automatically

Manual invalidation:

If you use `deps=[]` (or if updates happen outside of `modict` assignment hooks), you can invalidate caches explicitly:

```python
from modict import modict

m = modict({"a": 1, "b": 2})
m["sum"] = modict.computed(lambda m: m.a + m.b, cache=True, deps=[])

_ = m.sum  # cached
m.a = 10   # deps=[] -> no auto invalidation
assert m.sum == 3

m.invalidate_computed("sum")
assert m.sum == 12

# or invalidate everything:
m.invalidate_computed()
```

## Validation Pipeline

The pipeline is controlled by `_config.check_values`:
- `check_values="auto"` (default): enabled when the class looks model-like (hints/validators/config/constraints).
- `check_values=True`: always enabled.
- `check_values=False`: bypassed (pure dict behavior).

Related config flags:
- `strict`: when `True`, no coercion is attempted.
- `validate_assignment`: validate on `__setitem__`/`__setattr__`.
- `use_enum_values`: when `True`, enum values are stored/validated as `.value`.
- `enforce_json`: when `True`, values must be JSON-serializable (encoders can help).

When enabled, validation is applied:
- eagerly at initialization (`__init__` → `validate()`)
- optionally on assignment (`validate_assignment=True`)
- on reads of computed fields (`__getitem__` computes then validates the returned value)

Order of operations for a field value:
1. `use_enum_values`: if enabled and the value is an `Enum`, replace with `value.value`
2. string transforms (optional): `str_strip_whitespace`, `str_to_lower`, `str_to_upper`
3. field validators in `mode="before"`
4. coercion (only when `strict=False`)
5. type check (if the field has a type hint)
6. field validators in `mode="after"`
7. type check again (post-validators can still transform)
8. field constraints (`constraints=...` on the `Field`)
9. JSON-serializability check (`enforce_json=True`, with optional encoders)

## Configuration (Deep Dive)

All model-like behavior is controlled by the class attribute `_config`, a `modictConfig` dataclass created via `modict.config(...)`.

```python
class User(modict):
    _config = modict.config(
        check_values="auto",
        extra="allow",
        strict=False,
        validate_assignment=False,
        auto_convert=True,
    )
```

### Config reference

- `check_values`: `True`/`False`/`"auto"`.
  - `"auto"` enables the pipeline when the class *looks model-like* (has hints/validators/model validators) or when config implies processing (e.g. `extra != "allow"`, `enforce_json=True`, `strict=True`, …).
- `check_keys`: `True`/`False`/`"auto"`.
  - Key-level constraints are *structural* checks (presence/allowed-keys/invariants), independent from value validation.
  - `"auto"` enables key constraints when the model (or instance) declares them (e.g. `extra != "allow"`, `require_all=True`, computed fields, or any field with `required=True`).
  - When `False`, `modict` behaves more like a plain dict regarding keys: it won’t enforce `required=True`, `require_all=True`, `extra="forbid"/"ignore"`, or computed overwrite/delete protection.
  - `frozen=True` is always enforced (it is not controlled by `check_keys`).

Example: keep structure strict but skip value coercion/type checking:

```python
class Msg(modict):
    _config = modict.config(check_values=False, check_keys=True, extra="forbid")
    role: str = modict.field(required=True)
    content: str = modict.field(required=True)
```
- `extra`: `"allow"` (default) / `"forbid"` / `"ignore"`.
  - `"forbid"` raises on unknown keys at init and on assignment.
  - `"ignore"` drops unknown keys at init, and ignores them on assignment.
- `strict`: when `True`, disables coercion (type checking still applies when hints exist).
- `validate_assignment`: when `True`, assignment goes through the full pipeline.
- `frozen`: when `True`, `__setitem__` / `__delitem__` raise (read-only instances).
- `auto_convert`: when `True`, values stored inside nested mutable containers are lazily upgraded on access:
  - `dict` → `modict` (plain `modict`, not your subclass)
  - nested containers inside lists/tuples/sets/dicts are upgraded as you touch them
- `enforce_json`: when `True`, values must be JSON-serializable.
  - `allow_inf_nan` controls whether `NaN`/`Infinity` are allowed when encoding (default: `True`).
  - `json_encoders` lets you provide `type -> callable` encoders for serialization and `enforce_json=True`.
- `use_enum_values`: when `True`, enums are normalized to `.value` during validation and serialization.
- `str_strip_whitespace`, `str_to_lower`, `str_to_upper`: optional Pydantic-like string transformations.
  - if both `str_to_lower` and `str_to_upper` are `True`, lower takes precedence.
- `populate_by_name`: when `False` and a field has an alias, input must use the alias (field name is rejected).
  - `alias_generator`: callable `(field_name: str) -> str` applied at class creation time to fields without explicit aliases.
  - `validate_default`: when `True`, defaults are type-checked at class creation (skips `Factory`/`Computed`).
  - `from_attributes`: when `True`, `MyModict(obj)` can read declared fields from `obj.field` attributes (when `obj` is not a mapping).
- `override_computed`: when `False` (default), prevents overriding/deleting computed fields (and passing initial values for computed fields). Set to `True` to allow it explicitly.
- `require_all`: when `True`, requires all declared class fields (including computed) to be present at initialization; declared fields cannot be deleted (annotation-only fields become required).
- `evaluate_computed`: when `True` (default), computed fields are evaluated on access; when `False`, computed fields are treated as raw stored objects (no evaluation).

Required vs defaults (dict-first semantics):
- A class default (e.g. `age: int = 25`) is an *initializer*: it is injected once at construction if missing, but the key is still removable later when `require_all=False`.
- A field is an invariant only when you opt in to it: set `required=True` on the field (or `require_all=True` on the model) to enforce presence.

### Performance / dict-like mode

If you want `modict` to behave as close as possible to a plain `dict` (minimal overhead), you can opt out of most advanced features:

```python
class Fast(modict):
    _config = modict.config(
        check_values=False,     # skip validation/coercion pipeline
        check_keys=False,       # skip structural key constraints (required/extra/...)
        auto_convert=False,     # skip lazy conversion of nested containers on access
        evaluate_computed=False # treat Computed as raw stored objects
    )
```

### Config inheritance / merging

`modict` merges configs across inheritance in a Pydantic-like way:
- config values explicitly set in a subclass override inherited values
- when using multiple inheritance, the left-most base wins (for explicitly-set config keys)

## Aliases

Aliases live in `Field.aliases` (not in `metadata`).

Supported keys:
- `alias`: single alias (common case)
- `validation_alias`: string or list of strings (accepted input keys)
- `serialization_alias`: string (used by `model_dump(by_alias=True)`)

Input behavior is controlled by `_config.populate_by_name`:
- `populate_by_name=False`: if a field has aliases, only aliases are accepted (field name is rejected).
- `populate_by_name=True`: accept both alias and field name (but never both at once).

```python
class User(modict):
    _config = modict.config(populate_by_name=False)
    name: str = modict.field(aliases={"alias": "full_name"})

User({"full_name": "Alice"})        # OK
```

### `alias_generator`

Generate aliases automatically for fields that do not define any explicit alias:

```python
class User(modict):
    _config = modict.config(alias_generator=str.upper, populate_by_name=False)
    name: str

User({"NAME": "Alice"})
```

## Type Checking & Coercion

`modict` relies on its internal runtime type system (in `modict/_typechecker/`) for:
- type checking against annotations (`check_type(hint, value)`)
- best-effort coercion (`coerce(value, hint)`) when `strict=False`
- the `@typechecked` decorator for runtime checking of function arguments/return values

This subsystem supports common `typing` constructs (e.g. `Union`, `Optional`, `list[str]`, `dict[str, int]`, `tuple[T, ...]`, ABCs from `collections.abc`, …).
If coercion fails, the original value is kept; the subsequent type check decides whether it’s accepted (depending on hints and `strict`).

## Serialization

`modict` provides lightweight Pydantic-like serialization helpers.

### `model_dump` / `model_dump_json`

```python
data = u.model_dump(by_alias=True, exclude_none=True)
json_str = u.model_dump_json(by_alias=True)
```

Supported options:
- `by_alias`: use `serialization_alias` then `alias`
- `exclude_none`: drop keys with `None`
- `include` / `exclude`: sets of *field names* (not aliases)
- `encoders`: mapping `type -> callable` (see below)

### JSON encoders

Use encoders to serialize custom types and to satisfy `enforce_json=True`:

```python
from datetime import datetime

class Event(modict):
    _config = modict.config(json_encoders={datetime: lambda d: d.isoformat()})
    ts: datetime
```

### `dumps` / `dump`

`dumps()` / `dump()` are thin wrappers around `json.dumps` / `json.dump`, and support:
- `by_alias`
- `exclude_none`
- `encoders`

## JSON Schema

`json_schema()` exports a Draft 2020-12 JSON Schema from a modict class:

```python
schema = User.json_schema()
```

Notes:
- `$schema` is always `https://json-schema.org/draft/2020-12/schema`
- `constraints` are mapped to standard JSON Schema keywords (`minimum`, `multipleOf`, `pattern`, …)
- `additionalProperties` is emitted only when `extra="forbid"` (diff vs JSON Schema default)

## Deep Conversion & Deep Ops

### Deep conversion

`modict` ships with conversion utilities designed to preserve container identity as much as possible:
- `modict.convert(obj)`: recursively upgrades `dict` nodes to `modict` (and walks into mutable containers).
  - root dict becomes your class; nested dicts become plain `modict` unless they were already instances.
  - `recurse=False` stops recursion when reaching a modict node (used internally for lazy `auto_convert`).
- `m.to_modict()`: deep conversion of an instance in-place (calls `convert(self)`).
- `m.to_dict()`: deep un-conversion back to plain containers.

### Deep operations on nested structures

These operations are implemented on top of the `modict._collections_utils` package:
- `walk()` / `walked()`: flatten a nested structure to `(Path, value)` pairs.
- `unwalk(walked)`: reconstruct a nested structure from a `{Path: value}` mapping, preserving container classes when possible.
- `merge(mapping)`: deep, in-place merge (mappings merge by key; sequences merge by index).
- `diff(mapping)`: deep diff that returns `{Path: (left, right)}` with `MISSING` for absent values.
- `deep_equals(mapping)`: deep equality by comparing walked representations.

## Pydantic Interop (Optional)

Pydantic interoperability is an **optional feature** that operates at the **class level** (it converts *model classes*, not just instances).

When Pydantic is installed:
- `modict.from_model(PydanticModel)` converts a Pydantic `BaseModel` class into a new `modict` subclass.
- `MyModict.to_model()` converts a `modict` subclass into a new Pydantic `BaseModel` class.

This is designed for **bidirectional, best-effort round-trips** (Pydantic v1 and v2 supported).

In practice:
- `modict → Pydantic` is the “clean” direction: since `modict` is the source of truth, the generated Pydantic model is deterministic for the features `modict` supports.
- `Pydantic → modict` is inherently **best-effort**: Pydantic has a larger feature surface, and some semantics (especially advanced validation/serialization behaviors) don’t have 1:1 equivalents in a dict-first model.

### What gets converted (best-effort)

- Fields: annotations, defaults, and default factories (`Field(default_factory=...)` ↔ `modict.factory(...)`).
- Config: common Pydantic-aligned options (`extra`, `strict`, `frozen`, `validate_assignment`, string transforms, aliases-related settings, …).
- Aliases: `alias`, `validation_alias`, `serialization_alias` where representable.
- Validators:
  - field validators (before/after when possible)
  - model/root validators (before/after when possible)
- Computed fields:
  - Pydantic v2 computed fields ↔ `modict` computed fields (best-effort for `cache`/`deps`)
- Nested models:
  - referenced `BaseModel` types inside annotations are recursively converted to nested `modict` subclasses (cached to preserve sharing)

Pydantic-only metadata that can’t be expressed directly in `modict` is preserved under `Field._pydantic` so it can be re-emitted when converting back.

### Quick example (class-level conversion)

```python
from pydantic import BaseModel, Field
from modict import modict

class UserModel(BaseModel):
    name: str
    tags: list[str] = Field(default_factory=list)

User = modict.from_model(UserModel)        # Pydantic class -> modict class
UserModel2 = User.to_model(name="UserV2")  # modict class -> Pydantic class
```

## Package Tour (Internal Modules)

This section is an overview of the main internal modules and what functionality they implement.
If you only need the user-facing API, you can skip to [Public API Reference](#public-api-reference).

### `modict/_modict.py` (the `modict` class)

Core behaviors implemented here:
- dict subclass with attribute access (`m.key` ↔ `m["key"]`) while keeping Python attributes working
- validation pipeline (`validate()`, assignment validation, extra handling, constraints)
- computed fields evaluation and dependency-based cache invalidation
- lazy nested conversion (`auto_convert`) implemented in `__getitem__`
- nested ops (`get_nested`, `set_nested`, `pop_nested`, …) backed by JSONPath/`Path`
- deep ops (`walk`, `walked`, `unwalk`, `merge`, `diff`, `deep_equals`, `deepcopy`)
- JSON helpers (`loads`, `load`, `dumps`, `dump`, plus `model_dump*`)

### `modict/_modict_meta.py` (metaclass + field system)

Defines the "model-like layer" that turns a `dict` subclass into something schema/validation aware:
- `modictMeta`: collects declared fields from `__annotations__` and assigned attributes
  - supports plain defaults, `modict.field(...)` (`Field`), `modict.factory(...)` (`Factory`), and `@modict.computed(...)` (`Computed`)
  - collects `@modict.validator(...)` into per-field validators
  - collects `@modict.model_validator(...)` into model-level validators
- `modictConfig`: configuration object with explicit-key tracking and inheritance merge semantics
- `Field`: stores `hint`, `default`, `metadata`, `constraints`, `aliases` (plus an internal `_pydantic` bucket)
- `Validator` / `ModelValidator`: best-effort signature adapters (modict-style and Pydantic-style callables)
- `modictKeysView` / `modictValuesView` / `modictItemsView`: dict views that read through `__getitem__` (so computed + lazy conversion + validation happen during iteration)

### `modict/_collections_utils/` (nested structure utilities)

This package is responsible for paths, nested operations, and deep traversal.

- `modict/_collections_utils/_path.py`
  - `Path` / `PathKey`: JSONPath (RFC 9535) parsing and formatting via `jsonpath-ng`
  - type-aware path components (`PathKey.container_class`) so `walk()` → `unwalk()` can preserve container types
  - `Path.normalize(...)` to accept JSONPath strings, tuples, or `Path` objects
- `modict/_collections_utils/_basic.py`
  - container-agnostic `get_key` / `set_key` / `has_key` / `keys` / `unroll`
- `modict/_collections_utils/_advanced.py`
  - `get_nested` / `set_nested` / `pop_nested` / `del_nested` / `has_nested`
  - `walk` / `walked` / `unwalk`
  - `deep_merge` / `diff_nested` / `deep_equals`
- `modict/_collections_utils/_view.py`
  - `View`: base class to build custom collection views over mappings or sequences
- `modict/_collections_utils/_missing.py`
  - `MISSING`: sentinel to distinguish "missing" from `None`

### `modict/_typechecker/` (runtime typing + coercion)

This subpackage backs the runtime typing API exported by `modict`:
- `TypeChecker`: checks values against `typing` hints and collection ABCs
- `Coercer`: best-effort conversions for common hints/containers
- convenience API: `check_type`, `coerce`, `can_coerce`, `typechecked`

### `modict/_pydantic_interop.py` (optional Pydantic conversion)

Class-level conversions, with Pydantic v1 and v2 support:
- `from_pydantic_model(...)`: Pydantic → modict
  - converts nested `BaseModel` types to nested modict subclasses (with a global cache)
  - maps a conservative subset of Pydantic Field/Config metadata into `Field.metadata` / `Field.constraints` / `Field.aliases` and preserves extra info under `Field._pydantic`
  - imports field validators and model validators when possible (mode `before`/`after`)
  - extracts computed fields (Pydantic v2) and maps them to `Computed` fields (best-effort for `cache`/`deps`)
- `to_pydantic_model(...)`: modict → Pydantic
  - recreates `Field(...)` declarations, validators, model validators, and (v2) computed fields
  - maps modict config back to a Pydantic config, only emitting non-default values
- `TypeCache`: weak-reference cache for modict ↔ Pydantic class conversions (to preserve sharing and break cycles)

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
  - `Path`, `PathKey`
- Sentinel:
  - `MISSING`
- Pydantic interop cache:
  - `TypeCache`
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
- `modict.json_schema(excluded: set[str] | None = None) -> dict`
- JSON helpers:
  - `modict.loads(s, **json_kwargs) -> modict`
  - `modict.load(fp_or_path, **json_kwargs) -> modict`
- Pydantic interop (optional dependency):
  - `modict.from_model(PydanticModel, *, name=None, **config_kwargs) -> type[modict]`
  - `MyModict.to_model(*, name=None, **config_kwargs) -> type[pydantic.BaseModel]`
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
  - `model_dump(by_alias=False, exclude_none=False, include=None, exclude=None, encoders=None) -> dict`
  - `model_dump_json(...) -> str`
  - `dumps(..., by_alias=False, exclude_none=False, encoders=None) -> str`
  - `dump(fp_or_path, ..., by_alias=False, exclude_none=False, encoders=None) -> None`
- Nested operations (JSONPath / tuple / Path):
  - `get_nested(path, default=MISSING)`
  - `set_nested(path, value)`
  - `del_nested(path)`
  - `pop_nested(path, default=MISSING)`
  - `has_nested(path) -> bool`
- Key operations:
  - `rename(mapping_or_kwargs) -> modict`
  - `exclude(*keys) -> modict`
  - `extract(*keys) -> modict`
- Deep operations:
  - `merge(mapping) -> modict`
  - `diff(mapping) -> dict`
  - `deep_equals(mapping) -> bool`
  - `deepcopy() -> modict`
- Walking:
  - `walk(callback=None, filter=None, excluded=None) -> Iterable[tuple[Path, Any]]`
  - `walked(callback=None, filter=None) -> dict[Path, Any]`
- Computed cache:
  - `invalidate_computed(*names) -> None` (no args = all)
  - `invalidate_all_computed() -> None`

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
