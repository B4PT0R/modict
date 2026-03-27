# Changelog

All notable changes to path_utils will be documented in this file.

## [0.1.1] - 2026-03-27

### Added
- `Path.__repr__()` with readable `Path($.a[0].b)` formatting
- `Path.with_root(root)` for non-mutating rebinding
- `Path.starts_with(...)`, `Path.is_ancestor_of(...)`, and `Path.relative_to(...)`

### Changed
- `Path` now iterates over raw keys, so `tuple(path)` is the public way to extract segments
- `Path(existing_path)` now preserves cached container references unless a new `root=` is provided
- Removed the public `.keys` property in favor of the sequence interface

## [0.1.0] - 2024-01-05

### Added
- Initial release as part of b4pt0r monorepo
- `Path` class for JSONPath-based navigation
- `PathNode` class for path components
- `is_identifier()` function for identifier validation
- `ensure_absolute()` function for JSONPath validation
- `find_paths()` query functionality
- Support for JSONPath (RFC 9535)
- Comprehensive path manipulation utilities
