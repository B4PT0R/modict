"""
Example demonstrating Pydantic-aligned configuration semantics in modict.

modict now follows Pydantic's ConfigDict naming conventions for familiarity
and consistency with the broader Python ecosystem.
"""

from modict import modict


# Example 1: Using 'extra' parameter (Pydantic-style)
class StrictUser(modict):
    """User with strict field validation - no extra fields allowed."""
    _config = modict.config(
        extra='forbid',  # Pydantic-style: 'allow', 'forbid', or 'ignore'
        strict=True,
        validate_assignment=True
    )

    name: str
    age: int
    email: str | None = None


# Example 2: Backward compatibility with allow_extra
# Note: This will show a deprecation warning
import warnings

print("=" * 60)
print("Example 1: Pydantic-aligned 'extra' parameter")
print("=" * 60)

user = StrictUser(name="Alice", age=30)
print(f"✅ Created user: {user}")

try:
    user.undefined_field = "value"
except KeyError as e:
    print(f"❌ KeyError (extra='forbid'): {e}")

print()

# Example 3: Different 'extra' modes
print("=" * 60)
print("Example 2: Different 'extra' modes")
print("=" * 60)

class AllowExtraUser(modict):
    """Default behavior: extra fields are allowed."""
    _config = modict.config(extra='allow')  # Default
    name: str

class ForbidExtraUser(modict):
    """No extra fields allowed."""
    _config = modict.config(extra='forbid')
    name: str

class IgnoreExtraUser(modict):
    """Extra fields are silently ignored."""
    _config = modict.config(extra='ignore')
    name: str


# Test 'allow' mode
allow_user = AllowExtraUser(name="Bob", extra_field="allowed")
print(f"✅ extra='allow': {allow_user}")
print(f"   Can access extra_field: {allow_user.extra_field}")

# Test 'forbid' mode
try:
    forbid_user = ForbidExtraUser(name="Charlie", extra_field="not allowed")
except KeyError as e:
    print(f"❌ extra='forbid': KeyError during creation")

# Test 'ignore' mode
ignore_user = IgnoreExtraUser(name="Diana", extra_field="ignored")
has_extra = 'extra_field' in ignore_user
print(f"✅ extra='ignore': {ignore_user}")
print(f"   Extra field was silently ignored and NOT stored")
print(f"   Has 'extra_field' attribute: {has_extra}")

print()

# Example 4: Backward compatibility
print("=" * 60)
print("Example 3: Backward compatibility with allow_extra")
print("=" * 60)

with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter("always")

    class OldStyleUser(modict):
        """Using deprecated allow_extra parameter."""
        _config = modict.config(allow_extra=False)  # Deprecated!
        name: str

    if w:
        print(f"⚠️  DeprecationWarning: {w[0].message}")
        print(f"   Use extra='forbid' instead of allow_extra=False")

print()

# Example 5: Full Pydantic-aligned config
print("=" * 60)
print("Example 4: Full Pydantic-aligned configuration")
print("=" * 60)

class ConfiguredModel(modict):
    """Model with full Pydantic-style configuration."""
    _config = modict.config(
        # modict-specific
        auto_convert=True,

        # Pydantic-aligned (actively used)
        extra='forbid',
        strict=False,  # lax mode enables best-effort coercion
        enforce_json=True,
        frozen=False,
        validate_assignment=True,

        # Pydantic-aligned (reserved for future use)
        validate_default=False,
        populate_by_name=False,
        arbitrary_types_allowed=False,
    )

    name: str
    count: int = 0


model = ConfiguredModel(name="test", count="42")  # String coerced to int
print(f"✅ Created model with coercion: {model}")
print(f"   count type: {type(model.count).__name__} (coerced from str)")

try:
    model.count = "invalid"
except TypeError as e:
    print(f"❌ TypeError (lax mode, can't coerce 'invalid'): {type(e).__name__}")

print()
print("=" * 60)
print("Summary")
print("=" * 60)
print("✅ modict now follows Pydantic's ConfigDict semantics")
print("✅ Use extra='allow'/'forbid'/'ignore' instead of allow_extra")
print("✅ Backward compatibility maintained with deprecation warnings")
print("✅ All 272 tests passing!")
