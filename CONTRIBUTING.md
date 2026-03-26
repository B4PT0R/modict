# Contributing to modict

Thanks for considering a contribution!

## Development setup

```bash
pip install -e ".[dev]"
python3 -m pytest -q
```

Focused commands:

```bash
python3 -m pytest -q modict/typechecker/tests/test_typechecker.py
```

The repository CI runs the suite on Python `3.10` through `3.14`. If you change
runtime typing behavior, prefer adding a targeted regression test in the
`typechecker` test module as well as keeping the full suite green.

## Guidelines

- Keep changes focused and consistent with existing APIs.
- Add or update tests in `tests/` for behavior changes.
- Avoid changing public API names unless necessary.
- Prefer small, reviewable PRs.

## Reporting issues

Please include:
- Python version
- `modict` version
- a minimal reproduction snippet (or failing test)
