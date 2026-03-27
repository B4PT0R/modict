# Benchmarks

Small standalone scripts for quick performance checks and regressions.

Goals:
- keep scripts runnable directly from the repo root
- focus on realistic repeated operations rather than synthetic one-liners only
- make before/after comparisons easy when changing internals

Usage:

```bash
python benchmarks/run_all.py
python benchmarks/typechecker_cache.py
python benchmarks/modict_core_ops.py
python benchmarks/path_utils_ops.py
python benchmarks/collections_utils_ops.py
```

Notes:
- these are not part of the test suite
- numbers are machine-dependent; compare relative deltas more than absolute timings
- prefer adding a focused script here when optimizing a hotspot, instead of burying timing code inside tests

Current scripts:
- `run_all.py`: sequential runner for the benchmark scripts in this directory
- `typechecker_cache.py`: repeated `check_type`, `coerce`, and typed `modict` init with cache on/off
- `modict_core_ops.py`: repeated assignment, no-op reassignment, update, and computed access/invalidation paths
- `path_utils_ops.py`: repeated `Path` parsing, chaining, resolve, walk, and slicing operations
- `collections_utils_ops.py`: repeated nested access, traversal, reconstruction, diff, and deep-merge operations
