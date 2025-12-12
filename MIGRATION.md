# Migration Guide: modict 0.2.0

## Overview

modict 0.2.0 introduces **JSONPath (RFC 9535)** support for unambiguous nested structure access. This guide will help you migrate your code to the new API.

## What Changed

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

# Access components with metadata
for comp in path.components:
    print(f"{comp.value} ({comp.container_type})")
# Output:
# users (mapping)
# 0 (sequence)
# profile (mapping)
# city (mapping)

# Convert between formats
print(path.to_jsonpath())  # "$.users[0].profile.city"
print(path.to_tuple())     # ('users', 0, 'profile', 'city')
```

### 3. Path Normalization

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

## Need Help?

- Check the updated [README.md](README.md) for examples
- File an issue at [github.com/B4PT0R/modict/issues](https://github.com/B4PT0R/modict/issues)
- See [RFC 9535](https://www.rfc-editor.org/rfc/rfc9535.html) for JSONPath specification
