# typechecker

Runtime type checking and coercion utilities for Python.

## Features

- **Runtime type checking**: Validate types at runtime with detailed error messages
- **Type coercion**: Automatically convert values to target types
- **Decorator support**: Use `@typechecked` and `@coerced` decorators
- **Comprehensive types**: Support for primitives, generics, unions, and more

## Usage

```python
from ...typechecker import check_type, coerce, typechecked

# Basic type checking
check_type(42, int)  # OK
check_type("hello", int)  # Raises TypeMismatchError

# Type coercion
result = coerce("42", int)  # Returns 42
result = coerce("3.14", float)  # Returns 3.14

# Decorator usage
@typechecked
def add(a: int, b: int) -> int:
    return a + b

add(1, 2)  # OK
add("1", "2")  # Raises TypeMismatchError

@coerced
def multiply(a: int, b: int) -> int:
    return a * b

multiply("5", "3")  # Returns 15 (coerced from strings)
```

## API

### Functions

- `check_type(value, expected_type)` - Validate that value matches expected type
- `coerce(value, target_type)` - Convert value to target type
- `can_coerce(value, target_type)` - Check if value can be coerced
- `typechecked(func)` - Decorator for runtime type checking
- `coerced(func)` - Decorator for automatic type coercion

### Classes

- `TypeChecker` - Low-level type checking engine
- `Coercer` - Low-level type coercion engine

### Exceptions

- `TypeCheckException` - Base exception for type errors
- `TypeMismatchError` - Raised when types don't match
- `CoercionError` - Raised when coercion fails

## Part of b4pt0r

This package is part of the [b4pt0r](https://github.com/b4pt0r/b4pt0r) monorepo.

Install with: `pip install b4pt0r[typechecker]`
