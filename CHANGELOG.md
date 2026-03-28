# Changelog

## 0.4.7

### Changed
- `require_all` config option now accepts `"never"` | `"at_init"` | `"always"` instead of `bool`. Default changed from `False` to `"at_init"`: annotated fields without a default are now required at construction time but remain freely deletable afterwards. `True`/`False` still accepted for backward compat.
- `modict.field(required=...)` follows the same three-level scale. The stronger constraint between field-level `required` and config-level `require_all` always wins.

### Fixed
- Deletion of declared fields is now only blocked when the effective required level is `"always"` — `"at_init"` fields can be freely removed after construction.

## 0.4.6

### Added
- `QUICKSTART.md`: a narrative, example-driven introduction to modict for new users

### Changed
- README intro rewritten for clarity and conciseness: tighter positioning, cleaner "Why modict" paragraph, richer use-case descriptions
- Development section now includes full local setup instructions

### Fixed
- Protocol compatibility hardened on older Python versions (3.10/3.11)
- Cross-version typing and JSONPath compatibility fixes

## 0.4.5

### Added
- A dedicated `benchmarks/` directory with sequential runners for `typechecker`, `modict core`, `path_utils`, and `collections_utils`

### Changed
- `typechecker` and `coercer` now cache compiled hint/coercion plans more aggressively, with additional fast paths for trivial scalar/runtime checks
- `modict` hot paths (`__setitem__`, `update()`, computed invalidation, key/value pipeline guards) were tightened to avoid repeated no-op work and repeated structural scans
- `path_utils` now caches parsed JSONPath strings, making repeated path-based operations dramatically cheaper
- `collections_utils` traversal and reconstruction paths (`walk`, `unwalk`, `diff_nested`, `set_nested`) now rely on lighter internal path/container handling for better deep-op throughput

### Fixed
- Runtime container helper fast paths now still respect explicit `excluded=...` overrides

### Tests
- Added regression coverage around performance-sensitive copy/translate/computed bookkeeping paths and the newer `typechecker` fast paths

## 0.4.4

### Added
- `modict.attr(...)` / `Attribute` for explicit runtime/class metadata that stays outside the payload instead of being collected as a field
- `set_attr()` / `has_attr()` / `del_attr()` instance helpers for ergonomic runtime metadata management
- `modict.wrap(...)` / `__wrap_init__()` for advanced constructor-time business context without polluting the native dict-like constructor signature
- A new `examples/` directory with practical end-to-end scripts covering webhook payloads, config rollouts, SDK object adaptation, redaction/export flows, and a React-like UI component tree

### Changed
- `wrap(...)` now resolves a single `__wrap_init__` entry point on the target class; inheritance-time parameter routing is explicit inside user overrides instead of being inferred across the MRO
- The root `modict` package now keeps a tighter convenience surface focused on the main entry points; advanced descriptor/config/runtime classes stay exposed from their dedicated submodules
- The README now starts every Python snippet from explicit imports, routes readers more clearly toward submodule READMEs from the package tour, and keeps advanced payload/runtime patterns later in the narrative
- `Computed` semantics are documented more explicitly: class-declared computeds participate in the model contract, while dynamic instance computeds remain runtime values unless they target an already-declared field

### Fixed
- Runtime attrs declared with `modict.attr(...)` now bypass field collection reliably, remain available through inheritance, and can be overridden or cleared on instances without conflicting with declared field names
- `wrap(...)` behavior is now aligned between implementation, documentation, and tests for inheritance-heavy use cases

### Tests
- Added regression coverage for runtime attrs, wrapped construction, explicit wrap-parameter routing in inheritance scenarios, dynamic computed typing semantics, and the narrowed root public API

## 0.4.3

### Fixed
- `clear()` now respects `frozen=True` and computed-field protection invariants
- Replacing a computed field now invalidates dependant computed caches consistently, and `after` model validators no longer bypass assignment/key policies
- `Config.copy()` / `Config.merge()` now isolate mutable config payloads such as `json_encoders`
- `reset_global_typechecker()` now resets the global coercer too, keeping the public helper singletons in sync
- `Path.__radd__()` now treats `str` / `int` as single path keys, and `PathNode` reports stable errors for invalid containers
- `walk()` is now cycle-safe, and `deep_merge()` no longer treats `str` / `bytes` / `bytearray` as mergeable deep sequences
- `modict.__or__()` now works correctly on frozen instances without mutating the source object
- `convert()` / `unconvert()` now handle self-referential structures safely while preserving the intended in-place container semantics
- `coerce()` now handles PEP 604 optionals like `int | None`, and hostile iterables/mappings now fail with `CoercionError` instead of leaking raw runtime exceptions

### Changed
- Validator and model-validator signature errors are now detected at registration time, while runtime `TypeError`s raised inside validator bodies are preserved as-is
- Documentation now explicitly reflects the accepted relative `Path(...)` string forms

### Tests
- Expanded regression and edge-case coverage across `core`, `path_utils`, `collections_utils`, `model_api`, and `typechecker`, including cycles, alias preservation, hostile coercion inputs, and `from_attributes` failure modes

## 0.4.2

### Removed
- `rename()` from the public API; in-place key renaming was a poor fit for typed/model-like modicts and could break expected key structure

### Added
- `translate()` to return a plain `modict` with translated keys, intended for payload/header/schema projection without mutating the source object
- Path ergonomics improvements: `tuple(path)` iteration on keys, readable `repr(path)`, non-mutating `with_root()`, and relationship helpers `starts_with()`, `is_ancestor_of()`, `relative_to()`
- `unwalk(..., kind_resolver=...)` and `modict.unwalk(..., kind_resolver=...)` to refine inferred `mapping` / `sequence` structure per container path

### Changed
- `set_nested()` is now strict by default: missing intermediate containers raise unless `create_missing=True` is passed explicitly
- `set_nested(..., create_missing=True)` now uses a `container_factory(path)` hook instead of implicit container invention
- `unwalk()` now reconstructs structural `dict` / `list` containers via an internal tree build/materialization pass instead of replaying every path through repeated nested writes
- `modict.unwalk()` continues to recast the root mapping through the target class so model validation/coercion can re-establish the desired root type safely
- `Path` no longer exposes a `.keys` property; the public sequence API is now `tuple(path)` / iteration on keys
- `ignore_types` on `unwalk()` is now a legacy compatibility mode; structure selection is driven by the default or custom `kind_resolver`
- `repr(modict)` now renders computed fields as `Computed(current_value)` instead of hiding their derived nature in console output

## 0.4.1

### Added
- GitHub Actions test workflow covering Python `3.10` through `3.14`
- Additional regression coverage for `typechecker` runtime semantics, recursion safety, and permissive interface-only checks

### Changed
- `typechecker` documentation now distinguishes strictly checked constructs from intentionally permissive runtime-only checks
- Contribution guide now includes the focused `typechecker` test command and CI expectations

### Fixed
- Hardened `typechecker` and `coercer` around `Callable[...]` variance, `Protocol` member checking, `TypedDict` with `Required[...]` / `NotRequired[...]`, `type[T]`, explicit `ForwardRef`, and modern `TypeAliasType`
- Recursive aliases and cyclic values now fail safely during coercion instead of recursing indefinitely
- Remaining French comments/docstrings in the `typechecker` public surface were translated to English

## 0.4.0

### Removed
- Pydantic interoperability (`modict.from_model`, `MyModict.to_model`, `TypeCache`, and the conversion module)
- JSON Schema export (`modict.json_schema`) and field `constraints`
- `invalidate_all_computed()` — use `invalidate_computed()` with no arguments instead
- `filter()` / `filtered()` — redundant with native Python filtering; also blocked those key names

### Added
- `Query(path=MISSING, value=MISSING)` primitive in `collections_utils` for combined path+value search
  - `path`: `MISSING`=any, `str`=JSONPath, `Path`/`tuple`=exact match, `callable`=predicate
  - `value`: `MISSING`=any, `callable`=predicate, any literal (incl. `None`)=equality check
- `find()` / `found()` on modict instances via `Query` or inline `path`/`value` constraints
- `update(other=(), /, **kwargs)` override that routes all assignments through the validation pipeline

### Fixed
- `popitem()` now returns the last-inserted item (was returning first, violating the dict LIFO contract)
- `update()` override prevents CPython from bypassing `__setitem__` validation

### Changed
- All French inline comments translated to English throughout the codebase
- README rewritten: intro compares modict to `dict`, `dataclass`, `TypedDict`, `Pydantic`, `attrs`
- `diffed()` documented with `self.merge(self.diffed(other)) == other` contract
- Comprehensive test suite: +120 tests covering all native dict methods and modict-specific ops

## 0.3.3

### Fixed
- `diffed()` now uses `ignore_types=True` internally to prevent reconstructing modict classes with default values
- This ensures `diffed()` only returns actual differences, not defaults injected during reconstruction

### Added
- `ignore_types` parameter for `unwalk()` and `modict.unwalk()` to prevent container type reconstruction
- 3 new tests for `ignore_types` functionality in `tests/test_deep_operations.py`

### Technical Details
- When `ignore_types=True`, `unwalk()` reconstructs structures using plain `dict` and `list` instead of original container classes
- This prevents modict subclasses with defaults from injecting their default values during diff reconstruction

## 0.3.2

### Highlights
- Enhanced `deep_merge()` with deletion support via `MISSING` sentinel value
- New `diffed()` method for structural diff and patch operations
- **Python 3.14+ compatibility** with full PEP 649 support

### Added
- `deep_merge()` now supports `MISSING` as a sentinel value to delete keys/indices during merge operations
- `modict.diffed(other)` method returns only the differences needed to transform one modict into another
- `_get_annotations()` helper function for Python 3.14+ compatibility (PEP 649: Deferred Evaluation of Annotations)
- `ignore_types` parameter for `unwalk()` and `modict.unwalk()` to prevent container type reconstruction
- Comprehensive test suite for deep operations (`tests/test_deep_operations.py` - 38 new tests)

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
- Manual computed cache invalidation helpers: `invalidate_computed(*names)` (no args = all).
- Pydantic interop: preserves computed metadata (`deps`, `cache`) and modict-only `check_keys` across modict → Pydantic → modict.

### Changed
- `modict.json_schema()` marks fields as required only when explicitly `required=True` (or when `require_all=True`), aligning schema “required” with opted-in invariants.
- `rename()` preserves raw stored values and avoids forcing computed evaluation.

### Notes
- `frozen=True` remains an absolute invariant (always enforced regardless of `check_keys`/`check_values`).
- Pydantic → modict conversion stays best-effort by design; modict-only behaviors are preserved only when the Pydantic model originated from `modict.to_model()`.
