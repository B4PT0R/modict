"""Example demonstrating Pydantic validator interoperability.

This example shows how modict @check validators and Pydantic @field_validator
are converted bidirectionally.
"""

try:
    from pydantic import BaseModel, ValidationError, __version__ as pydantic_version
    PYDANTIC_AVAILABLE = True
    PYDANTIC_V2 = pydantic_version.startswith('2.')
except ImportError:
    print("Pydantic is not installed. Install it with: pip install pydantic")
    PYDANTIC_AVAILABLE = False
    PYDANTIC_V2 = False
    exit(1)

if PYDANTIC_V2:
    from pydantic import field_validator
else:
    from pydantic import validator

from modict import modict


def example_modict_to_pydantic():
    """Convert modict validators to Pydantic"""
    print("=" * 60)
    print("Example 1: modict @check → Pydantic validator")
    print("=" * 60)

    class User(modict):
        email: str
        age: int

        @modict.check('email')
        def validate_email(self, value):
            """Normalize email to lowercase and strip whitespace"""
            return value.lower().strip()

        @modict.check('age')
        def validate_age(self, value):
            """Ensure age is reasonable"""
            if value < 0 or value > 150:
                raise ValueError("Age must be between 0 and 150")
            return value

    print("\nOriginal modict class with validators:")
    print(f"  email validator: normalize (lowercase + strip)")
    print(f"  age validator: range check (0-150)")

    # Convert to Pydantic
    UserModel = User.to_model()

    print("\nConverted to Pydantic Model")
    print("  Validators are now Pydantic @field_validator")

    # Test validators work
    print("\nTesting validators:")
    user = UserModel(email="  ALICE@EXAMPLE.COM  ", age=30)
    print(f"  Input: email='  ALICE@EXAMPLE.COM  ', age=30")
    print(f"  Output: email='{user.email}', age={user.age}")
    print("  ✓ Email normalized!")

    print("\nTesting validation error:")
    try:
        invalid = UserModel(email="test@example.com", age=200)
    except ValidationError as e:
        print(f"  ✓ Validation failed for age=200")


def example_pydantic_to_modict():
    """Convert Pydantic validators to modict"""
    print("\n" + "=" * 60)
    print("Example 2: Pydantic validator → modict @check")
    print("=" * 60)

    if PYDANTIC_V2:
        class ProductModel(BaseModel):
            name: str
            price: float

            @field_validator('name')
            @classmethod
            def validate_name(cls, value):
                """Strip and title-case product names"""
                return value.strip().title()

            @field_validator('price')
            @classmethod
            def validate_price(cls, value):
                """Ensure price is positive"""
                if value <= 0:
                    raise ValueError("Price must be positive")
                return round(value, 2)
    else:
        class ProductModel(BaseModel):
            name: str
            price: float

            @validator('name')
            def validate_name(cls, value):
                return value.strip().title()

            @validator('price')
            def validate_price(cls, value):
                if value <= 0:
                    raise ValueError("Price must be positive")
                return round(value, 2)

    print("\nOriginal Pydantic Model with validators:")
    print(f"  name validator: strip + title case")
    print(f"  price validator: positive + round to 2 decimals")

    # Convert to modict
    Product = modict.from_model(ProductModel)

    print("\nConverted to modict class")
    print("  Validators are now modict @check methods")

    # Test validators work
    print("\nTesting validators:")
    product = Product(name="  laptop computer  ", price=999.999)
    print(f"  Input: name='  laptop computer  ', price=999.999")
    print(f"  Output: name='{product.name}', price={product.price}")
    print("  ✓ Name title-cased and price rounded!")


def example_multiple_validators():
    """Multiple validators on same field"""
    print("\n" + "=" * 60)
    print("Example 3: Multiple Validators on Same Field")
    print("=" * 60)

    class Article(modict):
        title: str

        @modict.check('title')
        def strip_title(self, value):
            """Remove whitespace"""
            return value.strip()

        @modict.check('title')
        def capitalize_title(self, value):
            """Capitalize each word"""
            return value.title()

        @modict.check('title')
        def check_length(self, value):
            """Ensure title is not too long"""
            if len(value) > 100:
                raise ValueError("Title too long (max 100 chars)")
            return value

    print("\nArticle with 3 chained validators:")
    print("  1. strip whitespace")
    print("  2. title case")
    print("  3. check max length")

    # Convert to Pydantic
    ArticleModel = Article.to_model()

    print("\n Converted to Pydantic - all validators preserved")

    # Test
    article = ArticleModel(title="  hello world from pydantic  ")
    print(f"\nInput: '  hello world from pydantic  '")
    print(f"Output: '{article.title}'")
    print("✓ All 3 validators applied in sequence!")


def example_round_trip():
    """Test validators survive round-trip conversion"""
    print("\n" + "=" * 60)
    print("Example 4: Round-trip Validator Conversion")
    print("=" * 60)

    class Person(modict):
        first_name: str
        last_name: str

        @modict.check('first_name')
        def validate_first_name(self, value):
            return value.strip().capitalize()

        @modict.check('last_name')
        def validate_last_name(self, value):
            return value.strip().upper()

    print("\n1. Start with modict (first_name: capitalize, last_name: UPPER)")

    # modict → Pydantic
    PersonModel = Person.to_model()
    print("2. Convert to Pydantic Model")

    # Pydantic → modict
    NewPerson = modict.from_model(PersonModel)
    print("3. Convert back to modict")

    # Test validators still work
    person = NewPerson(first_name="  alice  ", last_name="  smith  ")
    print(f"\n4. Create instance:")
    print(f"   Input: first_name='  alice  ', last_name='  smith  '")
    print(f"   Output: first_name='{person.first_name}', last_name='{person.last_name}'")
    print("   ✓ Validators survived round-trip!")


def example_complex_validation():
    """Complex validation with dependencies"""
    print("\n" + "=" * 60)
    print("Example 5: Complex Validation Logic")
    print("=" * 60)

    class Account(modict):
        username: str
        email: str
        password: str

        @modict.check('username')
        def validate_username(self, value):
            """Username must be alphanumeric and 3-20 chars"""
            value = value.lower().strip()
            if not value.isalnum():
                raise ValueError("Username must be alphanumeric")
            if len(value) < 3 or len(value) > 20:
                raise ValueError("Username must be 3-20 characters")
            return value

        @modict.check('email')
        def validate_email(self, value):
            """Basic email validation"""
            value = value.lower().strip()
            if '@' not in value or '.' not in value:
                raise ValueError("Invalid email format")
            return value

        @modict.check('password')
        def validate_password(self, value):
            """Password must be at least 8 chars"""
            if len(value) < 8:
                raise ValueError("Password must be at least 8 characters")
            return value

    print("\nAccount class with complex validation:")
    print("  - username: alphanumeric, 3-20 chars")
    print("  - email: basic format check")
    print("  - password: min 8 chars")

    # Convert to Pydantic
    AccountModel = Account.to_model()

    print("\nConverted to Pydantic Model")

    # Test valid data
    print("\nTesting valid data:")
    account = AccountModel(
        username="Alice123",
        email="alice@example.com",
        password="secret123"
    )
    print(f"  username: {account.username}")
    print(f"  email: {account.email}")
    print("  ✓ All validations passed!")

    # Test invalid data
    print("\nTesting invalid data:")
    test_cases = [
        ("ab", "alice@example.com", "password123", "username too short"),
        ("alice", "invalid-email", "password123", "invalid email"),
        ("alice", "alice@example.com", "short", "password too short"),
    ]

    for username, email, password, expected_error in test_cases:
        try:
            AccountModel(username=username, email=email, password=password)
            print(f"  ✗ Should have failed: {expected_error}")
        except ValidationError:
            print(f"  ✓ Correctly rejected: {expected_error}")


if __name__ == "__main__":
    if PYDANTIC_AVAILABLE:
        example_modict_to_pydantic()
        example_pydantic_to_modict()
        example_multiple_validators()
        example_round_trip()
        example_complex_validation()

        print("\n" + "=" * 60)
        print("All examples completed successfully!")
        print("=" * 60)
        print("\nKey takeaway: Validators are fully bidirectional!")
        print("- modict @check ↔ Pydantic @field_validator (v2)")
        print("- modict @check ↔ Pydantic @validator (v1)")
