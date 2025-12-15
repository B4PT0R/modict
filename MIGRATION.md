# Migration Guide: modict 0.3.0

## Overview

modict 0.3.0 builds on 0.2.x and introduces new *opt-in* “model-like” invariants and
performance knobs, plus stronger Pydantic interoperability for round-trips.

This guide will help you migrate your code to the new API.

## What Changed

### 0.3.0: Structural invariants are explicit (opt-in)

`modict` stays dict-first: annotations and class defaults do not automatically make keys “required invariants”.

New knobs:
- `Field(required=True)` (opt-in) marks a field as structurally required (presence enforced).
- `_config.require_all=True` enforces presence of all declared fields (including computed).
- `_config.check_keys` controls whether structural key constraints are enforced (`"auto"` / `True` / `False`).

If you previously relied on “missing annotated fields should raise” behavior, switch to:
```python
class M(modict):
    x: int = modict.field(required=True)
```

### 0.3.0: Computed safety and performance modes

- `_config.override_computed=False` (default) prevents accidental overriding/deleting computed fields.
- `_config.evaluate_computed=False` allows treating computed values as raw `Computed` objects (no evaluation).

### 1. Path Format (Non-Breaking)

**Before (modict < 0.2.0)**: Paths used dot notation with ambiguous integer handling
```python
data.get_nested("users.0.name")    # Ambiguous: is '0' a string key or index?
```

**After (modict >= 0.2.0)**: JSONPath notation required
```python
data.get_nested("$.users[0].name")  # ✅ Clear: [0] is an array index
data.get_nested("$.config['0']")    # ✅ Clear: '0' is a string key
```

**Migration**: Update all path strings to use JSONPath notation (prefix with `$`):

| Old Format | New Format |
|------------|------------|
| `"a.b.c"` | `"$.a.b.c"` |
| `"a.0.b"` | `"$.a[0].b"` |
| `"users.0.name"` | `"$.users[0].name"` |
| `"config.0"` | `"$.config['0']"` (if '0' is a string key) |

**Backward Compatibility**: Tuple paths still work and are auto-converted:
```python
# This still works (no changes needed)
data.get_nested(("users", 0, "name"))
```

### 2. Path Objects in Return Values (Breaking Change)

**Before (modict < 0.2.0)**: `walk()`, `walked()`, `diff()` returned strings
```python
for path_str, value in data.walk():
    print(f"{path_str}: {value}")  # path_str was a string like "users.0.name"
```

**After (modict >= 0.2.0)**: These methods return `Path` objects
```python
for path, value in data.walk():
    print(f"{path}: {value}")  # path is a Path object (auto-converts to string)
```

**Migration**: Most code will work as-is due to `Path.__str__()`, but if you need strings:

```python
# Option 1: Use str() conversion (implicit in f-strings)
for path, value in data.walk():
    path_str = str(path)  # or path.to_jsonpath()

# Option 2: Convert Path keys in dictionaries
walked = data.walked()
walked_strings = {str(k): v for k, v in walked.items()}

# Option 3: Use path.to_tuple() for tuple format
for path, value in data.walk():
    path_tuple = path.to_tuple()  # ('users', 0, 'name')
```

### 3. Collection Utilities Module Restructuring (Internal Change)

**Before**: `modict._collections_utils` was a single file
**After**: Now a package with submodules (`_path.py`, `_basic.py`, `_advanced.py`, etc.)

**Migration**: Only affects code importing from private modules (not recommended):
```python
# If you were importing from private modules (not recommended)
# from modict._collections_utils import parse_jsonpath  # ❌ Old

# Use public API instead
from modict import modict
from modict._collections_utils import Path  # ✅ Public API
```

## Step-by-Step Migration

### 1. Update Path Strings

**Find and replace** all path strings in your code:

```bash
# Search for old-style paths
grep -r "get_nested\|set_nested\|del_nested\|pop_nested\|has_nested" --include="*.py"
```

**Update each occurrence**:
```python
# Before
user = data.get_nested("users.0.profile.city")
data.set_nested("config.theme", "dark")

# After
user = data.get_nested("$.users[0].profile.city")
data.set_nested("$.config.theme", "dark")
```

### 2. Handle Path Objects in walk() Results

If you process `walk()` or `walked()` results:

```python
# Before (strings)
walked_dict = data.walked()
for path_str, value in walked_dict.items():
    # path_str was a string
    parts = path_str.split('.')

# After (Path objects)
walked_dict = data.walked()
for path, value in walked_dict.items():
    # path is a Path object
    parts = path.to_tuple()  # or path.components
    jsonpath = path.to_jsonpath()
```

### 3. Update Tests

If you have tests comparing paths:

```python
# Before
walked = data.walked()
assert "users.0.name" in walked  # ❌ Won't work with Path keys

# After - Option 1: Use Path objects
from modict._collections_utils import Path
walked = data.walked()
assert Path.from_jsonpath("$.users[0].name") in walked  # ✅

# After - Option 2: Convert to tuples
walked_tuples = {p.to_tuple(): v for p, v in walked.items()}
assert ('users', 0, 'name') in walked_tuples  # ✅

# After - Option 3: Convert to strings
walked_strings = {str(p): v for p, v in walked.items()}
assert "$.users[0].name" in walked_strings  # ✅
```

## New Features You Can Use

### 1. Unambiguous Path Access

```python
data = modict({"items": [1, 2], "keys": {"0": "a", 1: "b"}})

# Array index
data.get_nested("$.items[0]")     # 1 (clear: array index)

# String key '0'
data.get_nested("$.keys['0']")    # "a" (clear: string key)

# Note: Integer keys in dicts cannot be represented in JSONPath
# Use direct access for integer dict keys
value = data.keys[1]  # "b"
```

### 2. Path Metadata

```python
from modict._collections_utils import Path

path = Path.from_jsonpath("$.users[0].profile.city")

# Access components with exact container class metadata
for comp in path.components:
    class_name = comp.container_class.__name__ if comp.container_class else "ambiguous"
    print(f"{comp.value} ({class_name})")
# Output:
# users (dict)
# 0 (list)
# profile (dict)
# city (dict)

# Convert between formats
print(path.to_jsonpath())  # "$.users[0].profile.city"
print(path.to_tuple())     # ('users', 0, 'profile', 'city')
```

### 3. Container Type Preservation

Path components now store the **exact container class** instead of generic type strings:

**Before**: `container_type` was a string literal (`"mapping"`, `"sequence"`, `"unknown"`)
```python
# modict < 0.2.0
component.container_type  # "mapping" or "sequence" or "unknown"
```

**After**: `container_class` stores the actual Python class
```python
# modict >= 0.2.0
component.container_class  # dict, list, OrderedDict, UserDict, etc., or None
```

**Benefits**:
- `walk()` → `unwalk()` now preserves exact container types (OrderedDict, UserDict, etc.)
- Better type information for introspection
- No performance impact (hash/equality still use JSONPath strings)

**Example**:
```python
from collections import OrderedDict, UserList

# Original structure with custom types
data = {
    'config': OrderedDict([('x', 1), ('y', 2)]),
    'items': UserList([10, 20, 30])
}

# Walk and unwalk preserve exact types
walked_data = walked(data)
reconstructed = unwalk(walked_data)

type(reconstructed['config'])  # OrderedDict (preserved!)
type(reconstructed['items'])   # UserList (preserved!)
```

### 4. Path Normalization

```python
from modict._collections_utils import Path

# All these create equivalent Path objects
path1 = Path.from_jsonpath("$.users[0].name")
path2 = Path.from_tuple(('users', 0, 'name'))
path3 = Path.normalize("$.users[0].name")  # Auto-detects format
path4 = Path.normalize(('users', 0, 'name'))
```

## Common Issues

### Issue: "Legacy dot-notation detected" Error

**Problem**: Using old-style paths without `$` prefix

```python
data.get_nested("users.0.name")
# ValueError: Legacy dot-notation detected: 'users.0.name'
```

**Solution**: Add `$` prefix and use bracket notation for indices
```python
data.get_nested("$.users[0].name")  # ✅
```

### Issue: Path Object Keys in Dictionary

**Problem**: Comparing or looking up Path keys

```python
walked = data.walked()
if "users.0.name" in walked:  # ❌ Won't work (keys are Path objects)
    ...
```

**Solutions**:
```python
# Option 1: Use Path objects for lookup
from modict._collections_utils import Path
if Path.from_jsonpath("$.users[0].name") in walked:  # ✅
    ...

# Option 2: Convert keys to strings
walked_str = {str(k): v for k, v in walked.items()}
if "$.users[0].name" in walked_str:  # ✅
    ...

# Option 3: Convert keys to tuples
walked_tuple = {k.to_tuple(): v for k, v in walked.items()}
if ('users', 0, 'name') in walked_tuple:  # ✅
    ...
```

### Issue: Integer Keys in Dicts

**Problem**: JSONPath cannot represent integer keys in dicts

```python
data = modict({"users": {0: "admin"}})
# No JSONPath representation for integer key 0 in a dict
```

**Solution**: Use direct access or tuple paths
```python
# Direct access
value = data.users[0]  # ✅

# Tuple path (still works)
value = data.get_nested(("users", 0))  # ✅

# Note: This is a documented limitation of JSONPath
```

## Testing Your Migration

Run this script to verify basic compatibility:

```python
from modict import modict
from modict._collections_utils import Path

# Test 1: JSONPath strings work
data = modict({"users": [{"name": "Alice"}]})
assert data.get_nested("$.users[0].name") == "Alice"
print("✓ JSONPath strings work")

# Test 2: Tuple paths still work
assert data.get_nested(("users", 0, "name")) == "Alice"
print("✓ Tuple paths work")

# Test 3: walk() returns Path objects
for path, value in data.walk():
    assert isinstance(path, Path)
    break
print("✓ walk() returns Path objects")

# Test 4: Path conversions
path = Path.from_jsonpath("$.users[0].name")
assert path.to_tuple() == ('users', 0, 'name')
assert path.to_jsonpath() == "$.users[0].name"
print("✓ Path conversions work")

print("\n✅ Migration successful!")
```

## Configuration Migration: Pydantic-Aligned Semantics

### What Changed

The `allow_extra` boolean parameter has been replaced with the `extra` parameter that accepts three string values, following Pydantic's ConfigDict conventions.

| Old Syntax | New Syntax | Behavior |
|------------|------------|----------|
| `allow_extra=True` | `extra='allow'` | Allow and store extra attributes (default) |
| `allow_extra=False` | `extra='forbid'` | Raise KeyError on extra attributes |
| N/A | `extra='ignore'` | Silently ignore extra attributes (new!) |

### Migration Examples

**Before (Deprecated)**:
```python
from modict import modict

class MyModel(modict):
    _config = modict.config(
        allow_extra=False,  # ⚠️ Deprecated
        strict=True
    )
    name: str
    age: int
```

**After (Recommended)**:
```python
from modict import modict

class MyModel(modict):
    _config = modict.config(
        extra='forbid',  # ✅ Pydantic-aligned
        strict=True
    )
    name: str
    age: int
```

### New Feature: `extra='ignore'` Mode

The new `'ignore'` mode silently discards extra attributes:

```python
class IgnoreExtraModel(modict):
    _config = modict.config(extra='ignore')
    name: str

model = IgnoreExtraModel(name="Alice", unknown="ignored")
print(model)  # {'name': 'Alice'}
print('unknown' in model)  # False - silently ignored
```

### Backward Compatibility

**The old `allow_extra` parameter still works** but emits a `DeprecationWarning`:

```python
# This still works but triggers a warning
config = modict.config(allow_extra=False)
# ⚠️  DeprecationWarning: Use extra='forbid' instead
```

Conversion rules:
- `allow_extra=True` → `extra='allow'`
- `allow_extra=False` → `extra='forbid'`
- If both are provided, `extra` takes precedence

### Additional Pydantic-Aligned Fields

New configuration fields have been added:

```python
class FullConfig(modict):
    _config = modict.config(
        # modict-specific
        auto_convert=True,

        # Pydantic-aligned (actively used)
        extra='allow',
        strict=False,
        coerce=False,
        enforce_json=False,
        frozen=False,
        validate_default=False,
        str_strip_whitespace=False,
        str_to_lower=False,
        str_to_upper=False,
        use_enum_values=False,

        # Pydantic-aligned (reserved for future use)
        validate_assignment=False,
        populate_by_name=False,
        arbitrary_types_allowed=False,
    )
```

#### New Feature: `frozen` - Immutability

Make modict instances immutable after creation:

```python
class FrozenConfig(modict):
    _config = modict.config(frozen=True)
    name: str

config = FrozenConfig(name="Alice")
# config.name = "Bob"  # ❌ TypeError: Cannot assign to field 'name': instance is frozen
```

#### New Feature: `validate_default` - Validate Defaults at Class Definition

Validate that default values match their type annotations at class definition time:

```python
class Config(modict):
    _config = modict.config(validate_default=True)
    name: str = "Alice"  # ✅ Valid
    # age: int = "wrong"  # ❌ TypeError at class definition

config = Config()
assert config.name == "Alice"
```

This catches type errors early rather than at runtime.

#### New Feature: String Transformations

Apply automatic transformations to string values:

```python
class EmailConfig(modict):
    _config = modict.config(
        str_strip_whitespace=True,
        str_to_lower=True
    )
    email: str

config = EmailConfig(email="  ALICE@EXAMPLE.COM  ")
assert config.email == "alice@example.com"  # Stripped and lowercased
```

Available transformations:
- `str_strip_whitespace`: Remove leading/trailing whitespace
- `str_to_lower`: Convert to lowercase
- `str_to_upper`: Convert to uppercase

**Note**: `str_to_lower` takes precedence over `str_to_upper` if both are enabled.

#### New Feature: `use_enum_values` - Automatic Enum Value Extraction

Automatically extract `.value` from Enum instances:

```python
from enum import Enum

class Color(Enum):
    RED = "red"
    GREEN = "green"
    BLUE = "blue"

class Config(modict):
    _config = modict.config(use_enum_values=True)
    color: str

config = Config(color=Color.RED)
assert config.color == "red"  # Value extracted automatically
assert not isinstance(config.color, Color)  # Just the string value
```

### Configuration Migration Checklist

- [ ] Replace `allow_extra=True` with `extra='allow'`
- [ ] Replace `allow_extra=False` with `extra='forbid'`
- [ ] Consider using `extra='ignore'` for silently discarding unknown fields
- [ ] Update tests to use the new parameter names
- [ ] Run your test suite (273 tests pass with new system)

## Need Help?

- Check the updated [README.md](README.md) for examples
- See [examples/pydantic_config_semantics.py](examples/pydantic_config_semantics.py) for configuration examples
- File an issue at [github.com/B4PT0R/modict/issues](https://github.com/B4PT0R/modict/issues)
- See [RFC 9535](https://www.rfc-editor.org/rfc/rfc9535.html) for JSONPath specification
