# Changelog

## 0.3.2

### Highlights
- Enhanced `deep_merge()` with deletion support via `MISSING` sentinel value
- New `diffed()` method for structural diff and patch operations
- **Python 3.14+ compatibility** with full PEP 649 support

### Added
- `deep_merge()` now supports `MISSING` as a sentinel value to delete keys/indices during merge operations
- `modict.diffed(other)` method returns only the differences needed to transform one modict into another
- `_get_annotations()` helper function for Python 3.14+ compatibility (PEP 649: Deferred Evaluation of Annotations)
- Comprehensive test suite for deep operations (`tests/test_deep_operations.py` - 35 new tests)

### Changed
- `deep_merge()` now handles deletions safely in both Mappings (dicts) and Sequences (lists)
- Enhanced documentation for `merge()` with examples of recursive deletion using `MISSING`

### Fixed
- **Python 3.14+ compatibility**: Fixed metaclass annotation handling for PEP 649
- Annotation-only fields (e.g., `name: str`) now properly detected in Python 3.14+
- All 353 tests now pass on Python 3.14.2 (previously 57 failures)

### Technical Details
- `deep_merge()` collects keys/indices to delete before modification to avoid iteration errors
- List deletions processed in reverse order to maintain index validity
- `_get_annotations()` auto-detects `__annotations__` (Python 3.10-3.13) vs `__annotate_func__` (Python 3.14+)
- Full backward compatibility maintained for Python 3.10+

## 0.3.0

### Highlights
- Dict-first “model dict” ergonomics with explicit, opt-in model-like constraints.
- Stronger Pydantic interop and round-trip preservation of key modict semantics.
- More knobs to keep dict operations lightweight when you want performance.

### Added
- Field-level `required=True` (opt-in) and model-level `_config.require_all=True` for structural presence invariants.
- `_config.check_keys` to enable/disable structural key constraints independently from value validation.
- `_config.override_computed` to prevent accidental overrides/deletions of computed fields (opt-in override).
- `_config.evaluate_computed` to treat `Computed` as raw stored objects (no evaluation) for pure storage/perf mode.
- Manual computed cache invalidation helpers: `invalidate_computed(*names)` and `invalidate_all_computed()`.
- Pydantic interop: preserves computed metadata (`deps`, `cache`) and modict-only `check_keys` across modict → Pydantic → modict.

### Changed
- `modict.json_schema()` marks fields as required only when explicitly `required=True` (or when `require_all=True`), aligning schema “required” with opted-in invariants.
- `rename()` preserves raw stored values and avoids forcing computed evaluation.

### Notes
- `frozen=True` remains an absolute invariant (always enforced regardless of `check_keys`/`check_values`).
- Pydantic → modict conversion stays best-effort by design; modict-only behaviors are preserved only when the Pydantic model originated from `modict.to_model()`.

