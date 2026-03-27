# Changelog

All notable changes to collections_utils will be documented in this file.

## [0.1.1] - 2026-03-27

### Added
- `set_nested(..., create_missing=True, container_factory=...)` for explicit intermediate-container creation
- `unwalk(..., kind_resolver=...)` to refine inferred `mapping` / `sequence` structure per container path

### Changed
- `set_nested()` is now strict by default and no longer invents missing intermediate containers implicitly
- `unwalk()` now reconstructs structural `dict` / `list` containers instead of instantiating arbitrary source container classes
- `unwalk()` now builds and materializes an internal reconstruction tree instead of replaying every path through repeated nested writes
- `ignore_types` on `unwalk()` remains available as a legacy compatibility mode

## [0.1.0] - 2024-01-05

### Added
- Initial release as part of b4pt0r monorepo
- Collection utilities for nested data structures
- `walk()` and `walked()` for traversing nested containers
- `get_nested()`, `set_nested()`, `del_nested()` for path-based access
- `deep_merge()` for merging nested structures
- `deep_equals()` for comparing nested structures
- `diff_nested()` for finding differences
- `extract()` and `exclude()` for filtering
- `View` class for collection views
- Integration with path_utils for JSONPath support

### Changed
- Removed embedded _path.py module (791 lines)
- Now imports Path utilities from path_utils package
- Reorganized with src/ directory structure
