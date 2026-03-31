# modict

A Python `dict` subclass with an optional model layer — typed fields, validators, computed values, and deep nested operations — that stays a real `dict` throughout.

```python
from modict import modict

# start free-form ...
u = modict(name="Alice", age=30)

# ... then consolidate the data model progressively
class User(modict):
    name: str
    age: int = 0

    @modict.computed(deps=["name"])
    def greeting(self):
        return f"Hello, {self.name}!"

u = User(name="Alice", age=30)
u.greeting          # "Hello, Alice!"
isinstance(u, dict) # True — always
```

## Quickstart

New to modict? **[QUICKSTART.md](QUICKSTART.md)** walks you through the full feature set step by step, from a plain dict to a fully typed model with validators and computed fields.

## Why modict

Python gives you `dict` for flexible data and `dataclass` / Pydantic `BaseModel` for structured data — but not both at once. `dict` is universally accepted, is a regular mapping and serializes directly, but has no types, no validation, no computed fields. `dataclass` and Pydantic add the structure layer, but stop being dicts/mappings: you pay a conversion tax at every boundary — `dataclasses.asdict()`, `.model_dump()`, explicit serialization. `TypedDict` sits in between but is a static annotation only, with no runtime enforcement or defaults.

`modict` fills that gap: it supports structure **and** remains a real `dict` — it passes `isinstance(x, dict)`, serializes directly to JSON, and works with any function expecting a mapping. You add typed fields, validators, and computed properties as you go the same way you'd subclass any Python class. Nothing breaks, nothing needs converting.

## When to use modict

- **Config and settings**: typed defaults, computed derived values, merge/diff/patch.
- **JSON/API payloads**: parse with `modict.loads()`, navigate with JSONPath, validate selectively.
- **ETL pipelines**: traverse with `walk`/`unwalk`, track changes with `diff`.
- **Typed events**: `extra="forbid"` + `required=True` fields give lightweight runtime-enforced structure — still a plain dict at the boundary.
- **Tree-shaped data**: model node hierarchies (components, ASTs, config trees) where each node carries its own logic and the whole structure stays natively serializable.
- **Prototyping**: start free-form, add types and validators as the shape stabilizes.

## Contents

- [Quickstart](#quickstart)
- [Installation](#installation)
- [Examples](#examples)
- [Core Concepts](#core-concepts)
- [Field Definition](#field-definition)
- [Factories](#factories)
- [Validators](#validators)
- [Computed Fields](#computed-fields)
- [Validation Pipeline](#validation-pipeline)
- [Path-Based Tools](#path-based-tools)
- [Configuration (Deep Dive)](#configuration-deep-dive)
- [Type Checking & Coercion](#type-checking--coercion)
- [Serialization](#serialization)
- [Deep Conversion & Deep Ops](#deep-conversion--deep-ops)
- [Payload vs Runtime](#payload-vs-runtime)
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


[↑ Back to top](#contents)

## Examples

See [examples/README.md](examples/README.md) for a small set of practical,
end-to-end scripts covering:
- typed webhook payloads
- config rollouts and patching
- adapting SDK / ORM objects with `from_attributes`
- redaction / export flows with `Query`, `Path`, `walk`, and `unwalk`


[↑ Back to top](#contents)

## Core Concepts

A plain `modict` is just a dict with attribute access and nested ops:

```python
from modict import modict

m = modict({"user": {"name": "Alice"}, "count": 1})

assert m["count"] == 1
assert m.user.name == "Alice"  # attribute access for keys
assert isinstance(m, dict)     # True — always
```

Subclass it to add typed fields and defaults:

```python
class User(modict):
    name: str            # validated/coerced if provided; required at init by default (require_all="at_init")
    age: int = 25        # default value
    country: str = "FR"

u = User({"name": "Alice", "age": "30"})
assert u.age == 30       # coerced from str
assert u.country == "FR" # default applied
```

Model behavior is controlled via `_config`:

```python
class User(modict):
    _config = modict.config(extra="forbid", strict=True)
    name: str
    age: int = 25
```

> [!NOTE]
> Annotated fields without a default are required at construction time by default (`require_all="at_init"`), but can be freely deleted or popped afterwards — modict stays a mutable dict. Use `modict.field(required="always")` or `_config = modict.config(require_all="always")` to enforce presence as a permanent invariant. Use `require_all="never"` to make all fields fully optional.

Use `modict.field(...)` for full control over hint, default, and validators.

`repr(modict)` shows the live user-facing view. Computed fields are evaluated for display and rendered as `Computed(current_value)`.


[↑ Back to top](#contents)

## Field Definition

For most fields, the recommended style is still the simple direct one:

```python
from modict import modict

class User(modict):
    name: str
    age: int = 25
```

Use `modict.field(...)` when you need more explicit control over a field
definition:

```python
from modict import MISSING, modict

modict.field(
    default=MISSING,  # default value (MISSING means "no default value")
    hint=None,       # type hint, None = use class annotation when provided
    required="never",  # "never" | "at_init" | "always" (True → "always", False → "never")
    validators=None, # internal: used by the metaclass when collecting @modict.validator(...)
)
```

`default=MISSING` is already the default behavior, so you usually do not need to
write it explicitly.

Example:

```python
from modict import modict

class User(modict):
    name: str = modict.field(required=True)
    age = modict.field(default=25, hint=int)

u = User({"name": "Alice", "age": "30"})
assert u.age == 30
```

Note: if you pass `hint=...` explicitly in `modict.field(...)`, it takes precedence over the class annotation.


[↑ Back to top](#contents)

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


[↑ Back to top](#contents)

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

The method receives only the live instance (`self`) and mutates it in place. The validation pipeline is **suspended** during execution — field validators, type coercion, and key constraints do not apply to assignments made inside the method. The validator has full authority.

- `mode="before"` — runs after individual field validators `"before"`, before coercion/type-checking
- `mode="after"` — runs after individual field validators `"after"`, after coercion/type-checking

```python
from modict import modict

class Range(modict):
    start: int
    end: int

    @modict.model_validator(mode="after")
    def check_order(self):
        if self["start"] > self["end"]:
            raise ValueError("start must be <= end")
```


[↑ Back to top](#contents)

## Computed Fields

Computed fields are virtual values evaluated on access. They are stored as `Computed` objects inside the dict and evaluated via `__getitem__`.

When a computed is declared on the **class**, it becomes part of the model
contract just like any other declared field:
- it is collected into `__fields__`
- it participates in key-level model semantics
- its return value is checked against the field hint (class annotation first,
  callable return annotation second)

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

The modict.computed API is quite flexible and supports inline definitions as well:

Inline (non-decorator) form:

```python
from modict import modict

class Calc(modict):
    a: int
    b: int
    sum:int = modict.computed(lambda m: m.a + m.b, cache=True, deps=["a", "b"])
```

By contrast, a computed attached dynamically on an **instance** is just a
dynamic value stored under that key. It does **not** create a new model field
or change the class-level contract:

Inline "dict value" form (no subclass):

```python
from modict import modict

m = modict({"a": 1, "b": 2})
m["sum"] = modict.computed(lambda m: m.a + m.b)
assert m.sum == 3
```

Notes:
- Computed values still go through the validation pipeline (type checks, JSON serializability check, …) when enabled.
- Dynamic instance-level computeds only benefit from field-level type hints if the key was already declared on the class. Otherwise they remain plain dynamic values.
- Cache invalidation semantics:
  - `deps=None` (default): invalidate on any key change.
  - `deps=[...]`: invalidate only when one of the listed keys changes (can include other computed names).
  - `deps=[]`: never invalidate automatically.

Manual invalidation:

```python
from modict import modict

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


[↑ Back to top](#contents)

## Validation Pipeline

The pipeline is controlled by `_config.check_values`:
- `check_values=True` (default): active only when the class looks model-like (has hints, validators, or relevant config) — early exit otherwise.
- `check_values=False`: bypassed entirely (pure dict behavior).

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


[↑ Back to top](#contents)

## Path-Based Tools

`modict` comes with a consistent path system for reading/writing nested structures (including inside lists), plus a `Path` object for disambiguation and introspection.

### Supported path formats

You can target nested values using:
- **JSONPath strings** (RFC 9535): `$.users[0].name`
- **Tuples** of keys/indices: `("users", 0, "name")`
- **`Path` objects**: `Path("$.users[0].name")`

`Path(...)` also accepts relative dotted strings such as `users[0].name` and
normalizes them back to the absolute JSONPath form in `str(path)`.

### The `Path` object

`Path` is a parsed, strongly-typed representation of a nested path.

```python
from modict import Path

p = Path("$.users[0].name")
p = Path("users[0].name")
assert tuple(p) == ("users", 0, "name")
assert str(p) == "$.users[0].name"      # __str__ renders back to JSONPath
assert repr(p) == "Path($.users[0].name)"

assert p.starts_with(("users", 0))
assert p.relative_to(("users",)) == Path((0, "name"))

bound = p.with_root({"users": [{"name": "Alice"}]})
assert bound.resolve() == "Alice"
```

Internally, a `Path` is a tuple of `PathNode` components. Each node carries:
- the **key/index** (`"users"`, `0`, `"name"`)
- an optional reference to the **origin container instance** when it can be inferred, which lets helpers distinguish `Mapping` vs `Sequence` structure during reconstruction.

All nested helpers accept JSONPath strings, tuples, or `Path` objects interchangeably.

### Nested operations

```python
from modict import modict

m = modict({"user": {"name": "Alice"}})

m.get_nested("$.user.name")           # "Alice"
m.set_nested("$.user.age", 30)
m.has_nested("$.user.age")            # True
m.pop_nested("$.user.age")            # 30
m.del_nested("$.user.name")           # removes the key

m.set_nested(
    "$.prefs.theme",
    "dark",
    create_missing=True,
    container_factory=lambda path: {},
)
```

### Paths in deep traversal

- `walk()` yields `(Path, value)` leaf pairs.
- `walked()` returns a `{Path: value}` mapping.
- `unwalk(walked)` reconstructs a nested structure from a `{Path: value}` mapping using plain `dict` / `list` containers.
- `unwalk(..., kind_resolver=...)` can refine the inferred structure per container path.
- `ignore_types=True` remains available as a legacy mode to ignore `Path` hints and use only local key-shape heuristics.
- `modict.unwalk(...)` then retypes the root mapping through the target class, so model validation/coercion can re-establish the desired root type.


[↑ Back to top](#contents)

## Configuration (Deep Dive)

All model-like behavior is controlled by the class attribute `_config`, a `modictConfig` dataclass created via `modict.config(...)`.
Only modict-supported options are accepted — unknown keys raise `TypeError`.

```python
from modict import modict

class User(modict):
    _config = modict.config(
        check_values=True,
        extra="allow",
        strict=False,
        validate_assignment=True,  # default
        auto_convert=True,
    )
```

### Config reference

- `check_values`: `True` (default) / `False`.
  - `True`: active only when the class looks model-like (has hints, validators, model validators, or config constraints like `extra != "allow"`, `enforce_json=True`, `strict=True`) — early exit otherwise.
  - `False`: bypassed entirely (pure dict behavior, no coercion or type checking).
- `check_keys`: `True` (default) / `False`.
  - Key-level constraints are *structural* checks (presence/allowed-keys/invariants), separate from value validation.
  - `True`: active only when the model declares key constraints (`extra != "allow"`, `require_all != "never"`, computed fields, or any field with `required != "never"`) — early exit otherwise.
  - `False`: bypassed entirely — `required`, `require_all`, `extra="forbid"/"ignore"`, and computed overwrite/delete protection are all skipped.
  - `frozen=True` is always enforced regardless of `check_keys`.

Example: keep structure strict but skip value coercion/type checking:

```python
from modict import modict

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
- `override_computed`: when `False` (default), computed fields are protected at runtime: you cannot overwrite or delete them on an existing instance. During model construction/casting, class-declared computed fields still win over incoming values so the target model contract is preserved.
- `require_all`: controls the required level for all declared fields. Accepts `"never"` | `"at_init"` | `"always"` (or `bool` for backward compat). Default: `"at_init"`. The field-level `required` and `require_all` interact by taking the stronger constraint (`"always"` > `"at_init"` > `"never"`).
- `evaluate_computed`: when `True` (default), computed fields are evaluated on access. When `False`, the `Computed` object itself is returned (pure storage mode, no evaluation).

Required vs defaults (dict-first semantics):
- A class default (e.g. `age: int = 25`) is an *initializer*: injected once at construction if missing, always removable afterwards.
- `"at_init"` (default): field must be provided at construction, but can be deleted freely after — dict mutability is preserved.
- `"always"`: field is a permanent invariant — deletion is blocked. Opt in explicitly via `modict.field(required="always")` or `require_all="always"`.

### Performance / dict-like mode

If you want `modict` to behave as close as possible to a plain `dict` (minimal overhead), opt out of most advanced features:

```python
from modict import modict

class Fast(modict):
    _config = modict.config(
        check_values=False,      # skip validation/coercion pipeline
        check_keys=False,        # skip structural key constraints (required/extra/...)
        auto_convert=False,      # skip lazy conversion of nested containers on access
        evaluate_computed=False  # treat Computed as raw stored objects
    )
```

### Config inheritance / merging

Config values are merged across the MRO. The key rule: **only values explicitly passed to `modict.config(...)` participate in the merge** — default values never silently override a parent's choice.

```python
from modict import modict

class Base(modict):
    _config = modict.config(extra="forbid", strict=True)

class Child(Base):
    # No _config — inherits Base's config as-is.
    # effective: extra="forbid", strict=True

class Override(Child):
    _config = modict.config(extra="allow")
    # Only `extra` was explicitly set here, so only `extra` overrides.
    # effective: extra="allow", strict=True  (strict inherited from Base)
```

With multiple inheritance, the **left-most base wins** for any conflicting explicitly-set key:

```python
from modict import modict

class A(modict):
    _config = modict.config(strict=True)

class B(modict):
    _config = modict.config(strict=False, extra="forbid")

class C(A, B):
    pass
    # strict → True  (A wins over B, A is left-most)
    # extra  → "forbid"  (only B set it, no conflict)
```


[↑ Back to top](#contents)

## Type Checking & Coercion

`modict` relies on its internal runtime type system (`modict/typechecker/`) for:
- type checking against annotations (`check_type(hint, value)`)
- best-effort coercion (`coerce(value, hint)`) when `strict=False`
- the `@typechecked` decorator for runtime checking of function arguments/return values

This subsystem supports common `typing` constructs (`Union`, `Optional`, `list[str]`, `dict[str, int]`, `tuple[T, ...]`, ABCs from `collections.abc`, …).

When coercion fails, the original value is kept; the subsequent type check then decides whether it's accepted (based on hints and `strict` mode). This means `strict=False` is permissive but not silent — type mismatches still raise if the hint doesn't match.


[↑ Back to top](#contents)

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
from datetime import datetime
from modict import modict

class Event(modict):
    _config = modict.config(json_encoders={datetime: lambda d: d.isoformat()})
    name: str
    ts: datetime

e = Event(name="launch", ts=datetime(2024, 1, 1))
e.dumps(encoders={datetime: lambda d: d.timestamp()})
# {"name": "launch", "ts": 1704067200.0}
```

`dump()` writes to a file path or file-like object:

```python
from datetime import datetime
from modict import modict

class Event(modict):
    _config = modict.config(json_encoders={datetime: lambda d: d.isoformat()})
    name: str
    ts: datetime

e = Event(name="launch", ts=datetime(2024, 1, 1))
e.dump("event.json")
```

### `loads` / `load` (input)

Class-level methods that parse JSON and return a `modict` instance:

```python
from modict import modict

m = modict.loads('{"name": "launch", "ts": "2024-01-01T00:00:00"}')
m = modict.load("event.json")
```

These are thin wrappers around `json.loads`/`json.load` — no custom deserialization logic is applied. For typed deserialization with coercion, construct from the parsed dict directly:

```python
from datetime import datetime
from modict import modict

class Event(modict):
    name: str
    ts: datetime

data = modict.loads('{"name": "launch", "ts": "2024-01-01T00:00:00"}')
event = Event(**data)  # pipeline runs: coercion, type checks, validators, ...
```

### `to_jsonable`

For serialization beyond JSON (e.g. YAML, MessagePack), `to_jsonable(obj, encoders)` from `modict.collections_utils` recursively converts a structure to plain JSON-safe types (dicts, lists, primitives). This is what `dumps`/`dump` use internally.


[↑ Back to top](#contents)

## Deep Conversion & Deep Ops

### Deep conversion

`modict` ships with conversion utilities that preserve container identity as much as possible:
- `modict.convert(obj)`: recursively upgrades `dict` nodes to `modict` (and walks into mutable containers).
  - The root dict becomes your class; nested dicts become plain `modict` unless they were already instances.
  - `recurse=False` stops recursion when reaching a `modict` node (used internally for lazy `auto_convert`).
- `m.to_modict()`: deep conversion of an instance in-place (calls `convert(self)`).
- `m.to_dict()`: deep un-conversion back to plain containers.

### Deep operations on nested structures

> **Naming convention**: verb form (`walk`, `find`, `diff`) returns a lazy generator or flat inspection dict; past-participle form (`walked`, `found`, `diffed`) returns the result materialized — as a `{Path: value}` modict or a nestable patch ready for `merge()`.

- `walk()` / `walked()`: flatten a nested structure to `(Path, value)` pairs.
- `unwalk(walked, *, kind_resolver=None)`: reconstruct a nested structure from a `{Path: value}` mapping using structural `dict` / `list` containers, with an optional hook to refine inferred `mapping` / `sequence` kinds per path. The root can then be recast through `modict.unwalk(...)`.
- `merge(mapping)`: deep, in-place merge (mappings merge by key; sequences merge by index). Returns `None` — modifies in place.
- `diff(mapping)`: deep diff — returns a flat `{Path: (left_value, right_value)}` dict.
- `diffed(mapping)`: minimal nested patch — a modict shaped so that `self.merge(self.diffed(other))` equals `other`. Keys removed in `other` are set to `MISSING`.
- `deep_equals(mapping)`: deep equality by comparing walked representations (container types are ignored — a modict and a plain dict with the same leaves are equal). Use this when cross-type equality is needed; `==` uses the native dict comparison (type-sensitive).


[↑ Back to top](#contents)

## Payload vs Runtime

This is an advanced pattern.

One of `modict`'s more flexible use cases is building objects that are:
- **real dict payloads** for serialization, diffing, patching, and transport
- **real Python objects** with methods, runtime metadata, and business behavior

The important distinction is:
- **mapping keys** are the payload
- **attrs** are runtime/business context

That separation is what keeps the object plastic without making the serialized
representation fuzzy.

### Why this exists

In many codebases, the same conceptual object gets split into several layers:
- a DTO / payload dict for transport
- a model object for validation
- a runtime object carrying services, registries, caches, renderers, parent refs, etc.

`modict` can collapse a lot of that back into one object:
- the **payload** still lives directly in the dict
- the **behavior** lives on the class as normal methods
- the **runtime context** lives in attrs outside the dict

That means the same object can be:
- dumped to JSON
- diffed and patched deeply
- passed anywhere a `dict` or `Mapping` is expected
- still used as a domain object with methods like `render()`, `mount()`, `resolve_theme()`, `dispatch()`, ...

### When to use `attr(...)`

Use `modict.attr(...)` when a value should stay an attribute instead of becoming
a field or a payload key.

Typical cases:
- class metadata such as `source_system`, `component_kind`, `schema_version`
- instance metadata such as `trace_id`, `request_context`, `parent`, `dom_ref`
- business/runtime objects that must not leak into JSON output

```python
from modict import modict

class Component(modict):
    kind = modict.attr("button")
    label: str

component = Component(label="Save")
component.set_attr("trace_id", "req_123")

assert component.kind == "button"
assert component.trace_id == "req_123"
assert "kind" not in component
assert "trace_id" not in component
```

Rule of thumb:
- if it should serialize, diff, merge, or travel over the wire: put it in the dict
- if it is runtime-only context or behavior support: keep it as an attr

### When to use `wrap(...)`

Use `wrap(...)` when you need extra constructor-time business parameters but do
**not** want to break the native `dict` constructor semantics.

This is important because `modict` intentionally preserves the predictability of:
- `MyModict(data)`
- `MyModict(**payload)`

So instead of inventing a custom `__init__(data, registry, renderer, ...)`,
you keep the dict constructor clean and opt into an explicit wrapped
construction path:

```python
from modict import modict

class Component(modict):
    name: str

    @classmethod
    def __wrap_init__(cls, init, *, registry, renderer):
        def wrapped(*dict_args, **dict_kwargs):
            obj = init(*dict_args, **dict_kwargs)
            obj.set_attr("registry", registry)
            obj.set_attr("renderer", renderer)
            return obj
        return wrapped

component = Component.wrap(registry=my_registry, renderer=my_renderer)(
    name="hero"
)
```

This is there for two reasons:
- `Component(data)` and `Component(**payload)` stay predictable and fully dict-like
- wrapped construction gets full control around instantiation without polluting the payload with business-only parameters

This gives you full control around instantiation:
- pre-processing incoming dict args before native construction
- post-processing the fully validated/coerced object after construction
- composition through inheritance via multiple `__wrap_init__` layers

When inheritance is involved, parameter routing stays explicit. There is only
one wrap-time parameter space, so each `__wrap_init__` consumes what it needs
and forwards the rest deliberately:

```python
from modict import modict

class BaseComponent(modict):
    name: str

    @classmethod
    def __wrap_init__(cls, init, *, registry):
        def wrapped(*dict_args, **dict_kwargs):
            obj = init(*dict_args, **dict_kwargs)
            obj.set_attr("registry", registry)
            return obj
        return wrapped


class Button(BaseComponent):
    label: str

    @classmethod
    def __wrap_init__(cls, init, *, registry, renderer):
        # Route `registry` to the parent wrapper yourself.
        init = BaseComponent.__wrap_init__(init, registry=registry)

        def wrapped(*dict_args, **dict_kwargs):
            obj = init(*dict_args, **dict_kwargs)
            obj.set_attr("renderer", renderer)
            return obj
        return wrapped


button = Button.wrap(registry=my_registry, renderer=my_renderer)(
    name="save-button",
    label="Save",
)
```

That explicit routing is the point: `modict` keeps the dict constructor clean,
and `wrap(...)` gives you full control instead of inventing an implicit second
constructor protocol.

### Good use cases

- UI/component trees: serializable props/state/children in the dict, runtime
  refs/renderer/registry in attrs, methods like `mount()` and `render()` on the class
- SDK/ORM adapters: transport-ready payload in the dict, source handles/session/context in attrs
- workflow/job objects: diffable state in the dict, runtime executor/logger/trace context in attrs
- event/message envelopes: wire payload in the dict, dispatch helpers and runtime routing context outside it

See [examples/ui_component_tree.py](examples/ui_component_tree.py) for a full
end-to-end example of this pattern.


[↑ Back to top](#contents)

## Package Tour (Internal Modules)

This section is an overview of the main internal modules and what functionality they implement.
If you only need the user-facing API, skip to [Public API Reference](#public-api-reference).

Several submodules are intentionally usable almost like small standalone
packages. When you want the deeper, module-specific API rather than the
high-level `modict` overview, jump directly to:
- [modict/path_utils/README.md](modict/path_utils/README.md) for `Path` and path parsing/resolution
- [modict/collections_utils/README.md](modict/collections_utils/README.md) for nested ops, deep traversal, diff/merge, and `Query`
- [modict/typechecker/README.md](modict/typechecker/README.md) for runtime typing, coercion, and function decorators

This main README stays focused on the unified user-facing story; the module
READMEs are the deeper reference points once you start using those pieces more
directly.

### `modict/core/` (the `modict` class)

This is the glue layer that turns the subpackages into one coherent dict-first
model object.

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

This package is responsible for paths, nested operations, and deep traversal.
For the full module-level API, see [modict/collections_utils/README.md](modict/collections_utils/README.md).
Path parsing and representation details live separately in [modict/path_utils/README.md](modict/path_utils/README.md).

- `_path.py`: `Path` / `PathNode` — JSONPath (RFC 9535) parsing and formatting via `jsonpath-ng`.
  - Path components can cache origin container references so `walk()` → `unwalk()` can distinguish `Mapping` vs `Sequence` structure without recreating arbitrary concrete container classes.
  - `Path(...)` accepts JSONPath strings, tuples/lists of keys, or another `Path`.
- `_basic.py`: container-agnostic `get_key` / `set_key` / `has_key` / `keys` / `unroll`.
- `_advanced.py`: `get_nested` / `set_nested` / `pop_nested` / `del_nested` / `has_nested`, `walk` / `walked` / `unwalk`, `deep_merge` / `diff_nested` / `deep_equals`.
- `_view.py`: `View` — base class for custom collection views over mappings or sequences.
- `_missing.py`: `MISSING` sentinel to distinguish "absent" from `None`.

### `modict/typechecker/` (runtime typing + coercion)

For the full module-level API, see [modict/typechecker/README.md](modict/typechecker/README.md).

- `TypeChecker`: checks values against `typing` hints and collection ABCs.
- `Coercer`: best-effort conversions for common hints/containers.
- Convenience API: `check_type`, `coerce`, `can_coerce`, and `typechecked`, `coerced` for decorator-based type checking and coercion on functions.

### `modict/model_api/` (field system)

This is the internal field/validator/computed layer used by `modict` during
class creation and validation. Most users should stay on the class-level
helpers (`modict.field`, `modict.factory`, `@modict.validator`,
`@modict.computed`) rather than importing this module directly.

- `Field`, `Factory`, `Computed`, `Attribute`: field descriptor types used by `modictMeta` during class creation.
- `Validator`, `ModelValidator`: signature adapters for common call styles (allow flexible validator signatures).
- `build_fields_and_model_validators`: metaclass helper that collects fields and validators from a class dict.


[↑ Back to top](#contents)

## Public API Reference

This section lists the main convenience symbols exported by `modict` and the
main methods on `modict` instances.

### Exports

For most code, the normal import is just:

```python
from modict import modict
```

Advanced modules expose their richer surfaces directly:
- `modict.path_utils`
- `modict.collections_utils`
- `modict.typechecker`
- `modict.model_api`

The root package keeps only the most common convenience symbols:

- Data structure:
  - `modict`
- JSONPath types:
  - `Path`
- Sentinel:
  - `MISSING`
- Search:
  - `Query(path=MISSING, value=MISSING)` — combined path + value constraint; `.find(root)` returns matching `(Path, value)` pairs. `MISSING` means "no constraint"; `None` as `value` matches leaves whose value is literally `None`
- Type checking / coercion:
  - `check_type(hint, value)`
  - `coerce(value, hint)`
  - `can_coerce(value, hint)`
  - `typechecked` (decorator)
  - Exceptions: `TypeCheckError`, `TypeCheckException`, `TypeCheckFailureError`, `TypeMismatchError`, `CoercionError`

### `modict` class methods

  - `modict.config(**kwargs) -> modictConfig`
  - `modict.field(...) -> Field`
  - `modict.factory(callable) -> Factory`
  - `modict.attr(value) -> Attribute`
- `modict.wrap(*wrap_args, **wrap_kwargs) -> callable`
- `@modict.validator(field_name, mode="before"|"after")`
- `@modict.model_validator(mode="before"|"after")`
- `@modict.computed(cache=False, deps=None)`
- JSON helpers:
  - `modict.loads(s, **json_kwargs) -> modict`
  - `modict.load(fp_or_path, **json_kwargs) -> modict`
- Conversion:
  - `modict.convert(obj, seen=None) -> Any`
  - `modict.unconvert(obj, seen=None) -> Any`
  - `modict.unwalk(walked: dict[Path, Any], ignore_types: bool = False, *, kind_resolver=None) -> Any`

### `modict` instance methods

Instance methods keep standard dict behavior, plus:

- Validation:
  - `validate()`
- Runtime attrs:
  - `set_attr(name, value) -> None`
  - `has_attr(name) -> bool`
  - `del_attr(name) -> None`
- Conversion:
  - `to_modict() -> modict` (deep conversion)
  - `to_dict() -> dict` (deep unconvert)
- Serialization:
  - `dumps(exclude_none=False, encoders=None, **json_kwargs) -> str`
  - `dump(fp_or_path, exclude_none=False, encoders=None, **json_kwargs) -> None`
- Nested operations (JSONPath / tuple / Path):
  - `get_nested(path, default=MISSING)`
  - `set_nested(path, value, *, create_missing=False, container_factory=None)` where `container_factory` is called as `factory(path)`
  - `del_nested(path)`
  - `pop_nested(path, default=MISSING)`
  - `has_nested(path) -> bool`
- Key operations:
  - `translate(mapping_or_kwargs) -> modict` (returns a plain translated modict)
  - `exclude(*keys) -> modict`
  - `extract(*keys) -> modict`
  - `find(query=MISSING, *, path_constraint=MISSING, value_constraint=MISSING) -> Generator`
  - `found(query=MISSING, *, path_constraint=MISSING, value_constraint=MISSING) -> modict`
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


[↑ Back to top](#contents)

## Development

**Install in editable mode with dev dependencies:**

```bash
git clone https://github.com/B4PT0R/modict.git
cd modict
pip install -e ".[dev]"
```

This installs `modict` in editable mode along with `pytest`, `pytest-cov`, `pytest-html`, `flake8`, and `black`.

**Run the test suite:**

```bash
python3 -m pytest -q
```

**Run with coverage:**

```bash
python3 -m pytest --cov=modict --cov-report=term-missing
```

**Lint and format:**

```bash
flake8 modict/
black modict/
```

Tests are distributed across submodules (`modict/core/tests/`, `modict/typechecker/tests/`, etc.) and a top-level `tests/` directory for integration tests. All are discovered automatically by pytest.

[↑ Back to top](#contents)

## Contributing

Contributions are welcome.

- Please open an issue to discuss larger changes.
- For pull requests: add/adjust tests under `tests/` and keep `python3 -m pytest -q` green.
- Local setup: `pip install -e ".[dev]"`.

See `CONTRIBUTING.md` for details.

[↑ Back to top](#contents)

## License

MIT. See `LICENSE`.

[↑ Back to top](#contents)
