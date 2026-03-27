# Examples

This folder contains small, runnable scripts that show `modict` in realistic
usage patterns instead of isolated API fragments.

Run them from the repository root:

```bash
python examples/webhook_order.py
python examples/config_rollout.py
python examples/sdk_object_adapter.py
python examples/redact_export.py
python examples/ui_component_tree.py
```

Files:

- `webhook_order.py`: typed JSON payload parsing, validators, computed fields,
  JSONPath access, and `Query`.
- `config_rollout.py`: dict-first config patching with `merge`, `diff`,
  `diffed`, `MISSING`, and nested writes.
- `sdk_object_adapter.py`: adapting attribute-based objects with
  `from_attributes`, nested typed submodels, `modict.attr(...)`, and outbound
  key translation.
- `redact_export.py`: redaction and export flows using `Query`, `Path`,
  `walked`, and `unwalk`.
- `ui_component_tree.py`: a React-like component tree with runtime attrs,
  business methods, HTML rendering, and serializable/diffable UI state.
