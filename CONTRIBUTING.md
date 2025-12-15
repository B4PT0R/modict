# Contributing to modict

Thanks for considering a contribution!

## Development setup

```bash
pip install -e ".[dev]"
python3 -m pytest -q
```

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

