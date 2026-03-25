# Changelog

All notable changes to collections_utils will be documented in this file.

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
