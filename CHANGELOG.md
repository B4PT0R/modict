# Changelog

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

