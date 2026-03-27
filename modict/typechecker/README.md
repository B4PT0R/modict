# typechecker

Runtime type checking and coercion utilities. Used internally by modict's validation pipeline and available as a standalone public API.

## Usage

```python
from modict import check_type, coerce, can_coerce, typechecked, TypeMismatchError

# Type checking — hint first, value second
check_type(int, 42)        # OK
check_type(int, "hello")   # raises TypeMismatchError

# Coercion
coerce("42", int)          # 42
coerce("3.14", float)      # 3.14
can_coerce("42", int)      # True

# Decorator: raises on type mismatch
@typechecked
def add(a: int, b: int) -> int:
    return a + b

add(1, 2)     # OK
add("1", "2") # raises TypeMismatchError

# Decorator: coerces arguments before the call
from modict.typechecker import coerced

@coerced
def multiply(a: int, b: int) -> int:
    return a * b

multiply("5", "3")  # 15
```

Supports `typing` constructs: `Union`, `Optional`, `list[str]`, `dict[str, int]`, `tuple[T, ...]`, ABCs from `collections.abc`, and more.

Supported runtime-friendly constructs include:
- `Union`, `Optional`, `Literal`, `LiteralString`, `Annotated`
- `TypedDict` including `Required[...]` / `NotRequired[...]`
- `Callable[...]`, `Protocol`, `type[T]` / `Type[T]`
- forward references as strings or explicit `ForwardRef` objects
- modern `TypeAliasType` aliases when available on the running Python version

## Runtime Semantics

`typechecker` aims to be reliable at runtime, not exhaustive with every static-only
feature from `typing`.

### Strictly checked

These cases are validated structurally and should be treated as strong runtime guarantees:
- concrete classes and built-in containers
- `TypedDict` declared keys and annotated value types
- `Callable[...]` signatures, including parameter/return compatibility
- `Protocol` declared members (attributes and methods)
- `type[T]` / `Type[T]`

### Intentionally permissive

Some hints cannot be validated soundly at runtime without consuming iterators or
probing arbitrary values. In those cases the checker validates interface shape only:
- `Iterator[T]`
- `Iterable[T]` when the value is itself an iterator
- `Container[T]`
- `KeysView[T]`, `ValuesView[T]`, `ItemsView[K, V]`

This permissiveness is intentional and covered by tests.

### Coercion policy

`coerce(value, hint)` is conservative:
- it only performs best-effort conversions that are reasonable at runtime
- it does not attempt to synthesize class objects for `Type[T]`
- recursive coercion paths fail with `CoercionError` instead of recursing indefinitely

### Recursion safety

Recursive aliases and cyclic values are handled defensively:
- repeated `(hint, value)` pairs during checking short-circuit safely
- recursive coercion detects loops and fails explicitly with `CoercionError`

## API

### Functions

- `check_type(hint, value)` — raises `TypeMismatchError` if value does not match hint
- `coerce(value, hint)` — best-effort conversion; raises `CoercionError` on failure
- `can_coerce(value, hint) -> bool` — check without raising

### Decorators

- `@typechecked` — validates arguments and return value against annotations at call time
- `@coerced` — coerces arguments to annotated types before the call

### Classes

- `TypeChecker` — low-level type checking engine
- `Coercer` — low-level coercion engine

### Exceptions

- `TypeCheckException` — base exception
- `TypeMismatchError` — type does not match hint
- `TypeCheckFailureError` — unexpected error during type check
- `CoercionError` — coercion attempted but failed
