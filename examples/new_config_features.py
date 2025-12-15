"""
Demonstration of new Pydantic-aligned configuration features in modict 0.2.0.

This example showcases:
- frozen: Immutable instances
- validate_default: Validate defaults at class definition time
- String transformations: str_strip_whitespace, str_to_lower, str_to_upper
- use_enum_values: Automatic enum value extraction
"""

from enum import Enum, IntEnum
from modict import modict


# ============================================================================
# Example 1: Frozen (Immutable) Configurations
# ============================================================================

print("=" * 70)
print("Example 1: Frozen (Immutable) Configurations")
print("=" * 70)


class APIConfig(modict):
    """Immutable API configuration - prevents accidental modifications."""

    _config = modict.config(frozen=True)

    api_key: str
    base_url: str = "https://api.example.com"
    timeout: int = 30


# Create immutable config
api_config = APIConfig(api_key="secret_key_123")
print(f"API Config: {api_config}")
print(f"Base URL: {api_config.base_url}")

# Try to modify (will raise TypeError)
try:
    api_config.api_key = "new_key"
    print("❌ This shouldn't be reached!")
except TypeError as e:
    print(f"✅ Prevented modification: {e}")

print()


# ============================================================================
# Example 2: Validate Defaults at Class Definition
# ============================================================================

print("=" * 70)
print("Example 2: Validate Defaults at Class Definition")
print("=" * 70)


class ValidatedConfig(modict):
    """Configuration with validated defaults - catches errors early."""

    _config = modict.config(validate_default=True)

    name: str = "Alice"
    age: int = 25
    active: bool = True


print("✅ ValidatedConfig defined successfully with valid defaults")
config = ValidatedConfig()
print(f"Config: {config}")

# This would fail at class definition time (commented to allow script to run):
# class InvalidConfig(modict):
#     _config = modict.config(validate_default=True)
#     age: int = "not_a_number"  # ❌ TypeError at class definition!

print("❌ InvalidConfig would raise TypeError at class definition")
print()


# ============================================================================
# Example 3: String Transformations
# ============================================================================

print("=" * 70)
print("Example 3: String Transformations")
print("=" * 70)


class EmailConfig(modict):
    """Email configuration with automatic string transformations."""

    _config = modict.config(
        str_strip_whitespace=True, str_to_lower=True  # Remove whitespace  # Convert to lowercase
    )

    email: str
    username: str


# Whitespace and case are automatically normalized
email_config = EmailConfig(email="  ALICE@EXAMPLE.COM  ", username="  Bob123  ")

print(f"Original input: '  ALICE@EXAMPLE.COM  '")
print(f"Normalized email: '{email_config.email}'")
print(f"Normalized username: '{email_config.username}'")
print()


class CodeConfig(modict):
    """Configuration that uppercases codes."""

    _config = modict.config(str_to_upper=True)

    country_code: str
    currency_code: str


code_config = CodeConfig(country_code="us", currency_code="usd")
print(f"Country code: {code_config.country_code}")
print(f"Currency code: {code_config.currency_code}")
print()


# ============================================================================
# Example 4: Enum Value Extraction
# ============================================================================

print("=" * 70)
print("Example 4: Enum Value Extraction")
print("=" * 70)


class Color(Enum):
    """Color enumeration."""

    RED = "red"
    GREEN = "green"
    BLUE = "blue"


class Priority(IntEnum):
    """Priority levels."""

    LOW = 1
    MEDIUM = 2
    HIGH = 3


class TaskConfig(modict):
    """Task configuration with automatic enum value extraction."""

    _config = modict.config(use_enum_values=True)

    title: str
    priority: int
    color: str


# Enums are automatically converted to their values
task = TaskConfig(title="Important Task", priority=Priority.HIGH, color=Color.RED)

print(f"Task: {task}")
print(f"Priority value: {task.priority} (type: {type(task.priority).__name__})")
print(f"Color value: {task.color} (type: {type(task.color).__name__})")
print(f"Is priority an enum? {isinstance(task.priority, Priority)}")  # False
print()


# ============================================================================
# Example 5: Combining Multiple Features
# ============================================================================

print("=" * 70)
print("Example 5: Combining Multiple Features")
print("=" * 70)


class Status(Enum):
    """Status enumeration."""

    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"


class ApplicationConfig(modict):
    """
    Production-ready configuration combining multiple features.

    - Immutable after creation
    - Validates defaults at class definition
    - Normalizes string inputs
    - Extracts enum values
    - Strict type checking
    - Forbids extra fields
    """

    _config = modict.config(
        frozen=True,  # Immutable
        validate_default=True,  # Validate defaults early
        str_strip_whitespace=True,  # Clean strings
        str_to_lower=True,  # Normalize case
        use_enum_values=True,  # Extract enum values
        strict=True,  # Type checking
        extra="forbid",  # No extra fields
    )

    app_name: str = "myapp"
    version: str = "1.0.0"
    status: str
    debug: bool = False


# Create configuration
app_config = ApplicationConfig(
    app_name="  MyApp  ",  # Will be normalized to "myapp"
    status=Status.ACTIVE,  # Will be extracted to "active"
)

print(f"App Config: {app_config}")
print(f"App name (normalized): '{app_config.app_name}'")
print(f"Status (extracted): '{app_config.status}'")
print(f"Version: {app_config.version}")
print(f"Debug: {app_config.debug}")

# Try to modify frozen config
try:
    app_config.debug = True
except TypeError as e:
    print(f"✅ Prevented modification: Cannot modify frozen config")

# Try to add extra field
try:
    app_config.extra_field = "value"
except TypeError as e:
    print(f"✅ Prevented extra field (frozen check first)")

print()


# ============================================================================
# Example 6: Pydantic Interoperability
# ============================================================================

print("=" * 70)
print("Example 6: Pydantic Interoperability")
print("=" * 70)

try:
    from pydantic import BaseModel, ConfigDict

    class PydanticUser(BaseModel):
        """Pydantic model with configuration."""

        model_config = ConfigDict(
            extra="forbid",
            frozen=True,
            str_strip_whitespace=True,
            str_to_lower=True,
        )

        username: str
        email: str

    # Convert to modict - config is preserved
    ModictUser = modict.from_model(PydanticUser)

    print(f"✅ Converted Pydantic model to modict")
    print(f"   extra: {ModictUser._config.extra}")
    print(f"   frozen: {ModictUser._config.frozen}")
    print(f"   str_strip_whitespace: {ModictUser._config.str_strip_whitespace}")
    print(f"   str_to_lower: {ModictUser._config.str_to_lower}")

    # Create instance
    user = ModictUser(username="  ALICE  ", email="  ALICE@EXAMPLE.COM  ")
    print(f"\nUser: {user}")
    print(f"Username (normalized): '{user.username}'")
    print(f"Email (normalized): '{user.email}'")

    # Convert back to Pydantic - config is preserved
    BackToPydantic = ModictUser.to_model()
    pydantic_user = BackToPydantic(username="  BOB  ", email="  BOB@EXAMPLE.COM  ")
    print(f"\nPydantic user: {pydantic_user}")
    print(f"Username (normalized): '{pydantic_user.username}'")
    print(f"Email (normalized): '{pydantic_user.email}'")

except ImportError:
    print("⚠️  Pydantic not installed - skipping interop example")

print()


# ============================================================================
# Summary
# ============================================================================

print("=" * 70)
print("Summary")
print("=" * 70)
print(
    """
New configuration features in modict 0.2.0:

1. frozen=True
   - Make instances immutable after creation
   - Prevents accidental modifications
   - Perfect for configuration objects

2. validate_default=True
   - Validate default values at class definition time
   - Catch type errors early (at import time)
   - Better development experience

3. String transformations
   - str_strip_whitespace: Remove leading/trailing whitespace
   - str_to_lower: Convert to lowercase
   - str_to_upper: Convert to uppercase
   - Automatic normalization of string inputs

4. use_enum_values=True
   - Automatically extract .value from Enum instances
   - Store values instead of enum objects
   - Simplifies serialization and comparison

5. Bidirectional Pydantic interop
   - Convert Pydantic models to modict (preserving config)
   - Convert modict to Pydantic models (preserving config)
   - Full round-trip compatibility

All features follow Pydantic's ConfigDict semantics for familiarity.
"""
)
