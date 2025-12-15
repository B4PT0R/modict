"""Example demonstrating Pydantic interoperability with modict.

This example shows how to convert between Pydantic models and modict classes.
"""

try:
    from pydantic import BaseModel, Field
    PYDANTIC_AVAILABLE = True
except ImportError:
    print("Pydantic is not installed. Install it with: pip install pydantic")
    PYDANTIC_AVAILABLE = False
    exit(1)

from modict import modict


def example_pydantic_to_modict():
    """Convert a Pydantic model to a modict class."""
    print("=" * 60)
    print("Example 1: Converting Pydantic Model to modict")
    print("=" * 60)

    # Define a Pydantic model
    class UserModel(BaseModel):
        name: str
        age: int = 25
        email: str | None = None
        tags: list[str] = Field(default_factory=list)

    print("\nOriginal Pydantic Model:")
    print(f"  Class: {UserModel.__name__}")
    print(f"  Fields: {list(UserModel.model_fields.keys())}")

    # Convert to modict
    User = modict.from_model(UserModel)

    print("\nConverted modict class:")
    print(f"  Class: {User.__name__}")
    print(f"  Fields: {list(User.__fields__.keys())}")

    # Create instances
    user1 = User(name="Alice", age=30)
    user2 = User(name="Bob")  # Uses default age

    print("\nInstances:")
    print(f"  user1: {user1}")
    print(f"  user2: {user2}")
    print(f"  user2.age (default): {user2.age}")

    # Test factory field
    user1.tags.append("python")
    user2.tags.append("javascript")

    print(f"\n  user1.tags: {user1.tags}")
    print(f"  user2.tags: {user2.tags}")
    print("  ✓ Each instance has its own list (factory works!)")


def example_modict_to_pydantic():
    """Convert a modict class to a Pydantic model."""
    print("\n" + "=" * 60)
    print("Example 2: Converting modict to Pydantic Model")
    print("=" * 60)

    # Define a modict class
    class Product(modict):
        name: str
        price: float
        stock: int = 0
        tags: list[str] = modict.factory(list)

    print("\nOriginal modict class:")
    print(f"  Class: {Product.__name__}")
    print(f"  Fields: {list(Product.__fields__.keys())}")

    # Convert to Pydantic
    ProductModel = Product.to_model()

    print("\nConverted Pydantic Model:")
    print(f"  Class: {ProductModel.__name__}")
    print(f"  Fields: {list(ProductModel.model_fields.keys())}")

    # Create instances
    product1 = ProductModel(name="Laptop", price=999.99)
    product2 = ProductModel(name="Mouse", price=29.99, stock=50)

    print("\nInstances:")
    print(f"  product1: {product1}")
    print(f"  product2: {product2}")

    # Test Pydantic validation
    print("\nPydantic validation:")
    try:
        invalid = ProductModel(name="Invalid", price="not a number")
    except Exception as e:
        print(f"  ✓ Validation error caught: {type(e).__name__}")


def example_round_trip():
    """Demonstrate round-trip conversion."""
    print("\n" + "=" * 60)
    print("Example 3: Round-trip Conversion")
    print("=" * 60)

    # Start with Pydantic
    class PersonModel(BaseModel):
        first_name: str
        last_name: str
        age: int

    print("\n1. Original Pydantic Model")
    print(f"   Class: {PersonModel.__name__}")

    # Convert to modict
    Person = modict.from_model(PersonModel)
    print("\n2. Converted to modict")
    print(f"   Class: {Person.__name__}")

    # Convert back to Pydantic
    NewPersonModel = Person.to_model(name="PersonModelV2")
    print("\n3. Converted back to Pydantic")
    print(f"   Class: {NewPersonModel.__name__}")

    # Test both work the same
    pydantic_person = PersonModel(first_name="Alice", last_name="Smith", age=30)
    modict_person = Person(first_name="Bob", last_name="Jones", age=25)
    new_pydantic = NewPersonModel(first_name="Charlie", last_name="Brown", age=35)

    print("\n4. All three classes work:")
    print(f"   Pydantic original: {pydantic_person}")
    print(f"   modict version:    {modict_person}")
    print(f"   Pydantic v2:       {new_pydantic}")


def example_with_config():
    """Demonstrate using modict config with converted classes."""
    print("\n" + "=" * 60)
    print("Example 4: Using modict Config with Conversions")
    print("=" * 60)

    # Pydantic model
    class ConfigModel(BaseModel):
        name: str
        value: int

    print("\nConverting with modict config options:")

    # Convert with strict mode and coercion
    StrictConfig = modict.from_model(
        ConfigModel,
        name="StrictConfig",
        strict=False,
    )

    print(f"  Class: {StrictConfig.__name__}")
    print(f"  Config strict: {StrictConfig._config.strict}")

    # Test coercion
    config = StrictConfig(name="test", value="42")  # String will be coerced to int
    print(f"\n  Created with value='42' (string)")
    print(f"  config.value: {config.value} (type: {type(config.value).__name__})")
    print("  ✓ Coercion worked!")


def example_data_transfer():
    """Demonstrate transferring data between modict and Pydantic instances."""
    print("\n" + "=" * 60)
    print("Example 5: Data Transfer Between Instances")
    print("=" * 60)

    # Define both
    class DataModel(BaseModel):
        id: int
        content: str

    Data = modict.from_model(DataModel)
    NewDataModel = Data.to_model()

    print("\nCreating modict instance:")
    modict_data = Data(id=1, content="Hello from modict")
    print(f"  {modict_data}")

    print("\nConverting data to Pydantic instance:")
    # Use dict() to get data, then validate with Pydantic
    pydantic_data = NewDataModel.model_validate(dict(modict_data))
    print(f"  {pydantic_data}")

    print("\nConverting Pydantic data to modict instance:")
    modict_data2 = Data(**pydantic_data.model_dump())
    print(f"  {modict_data2}")

    print("\n  ✓ Data transfers seamlessly between both!")


if __name__ == "__main__":
    if PYDANTIC_AVAILABLE:
        example_pydantic_to_modict()
        example_modict_to_pydantic()
        example_round_trip()
        example_with_config()
        example_data_transfer()

        print("\n" + "=" * 60)
        print("All examples completed successfully!")
        print("=" * 60)
