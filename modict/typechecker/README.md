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

## API

### Functions

- `check_type(hint, value)` — raises `TypeMismatchError` if value does not match hint
- `coerce(value, hint)` — best-effort conversion; returns original value on failure
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
