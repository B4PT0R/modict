# Changelog

All notable changes to typechecker will be documented in this file.

## [0.1.0] - 2024-01-05

### Added
- Initial release as part of b4pt0r monorepo
- `check_type()` function for runtime type validation
- `coerce()` function for type coercion
- `can_coerce()` function to test coercion feasibility
- `@typechecked` decorator for automatic type checking
- `@coerced` decorator for automatic type coercion
- `TypeChecker` class for low-level type checking
- `Coercer` class for low-level type coercion
- Support for primitives, generics, unions, and complex types
- Comprehensive error messages with type mismatch details
