"""Example demonstrating Pydantic computed fields interoperability.

This example shows how modict computed fields are converted to Pydantic v2 @computed_field.
Note: Requires Pydantic v2 for computed field support.
"""

try:
    from pydantic import BaseModel, __version__ as pydantic_version
    PYDANTIC_AVAILABLE = True
    PYDANTIC_V2 = pydantic_version.startswith('2.')
except ImportError:
    print("Pydantic is not installed. Install it with: pip install pydantic")
    PYDANTIC_AVAILABLE = False
    PYDANTIC_V2 = False
    exit(1)

if not PYDANTIC_V2:
    print("This example requires Pydantic v2 for computed field support.")
    print(f"You have Pydantic {pydantic_version}")
    exit(1)

from modict import modict


def example_basic_computed():
    """Basic computed field conversion."""
    print("=" * 60)
    print("Example 1: Basic Computed Field")
    print("=" * 60)

    # Define modict with computed field
    class Person(modict):
        first_name: str
        last_name: str

        @modict.computed()
        def full_name(self):
            return f"{self.first_name} {self.last_name}"

    print("\nOriginal modict class:")
    print(f"  Fields: {list(Person.__fields__.keys())}")

    # Convert to Pydantic
    PersonModel = Person.to_model()

    print("\nConverted Pydantic Model:")
    print(f"  Fields: {list(PersonModel.model_fields.keys())}")
    print(f"  Computed fields: {list(PersonModel.model_computed_fields.keys())}")

    # Create instance
    person = PersonModel(first_name="Alice", last_name="Smith")

    print("\nInstance:")
    print(f"  person.first_name: {person.first_name}")
    print(f"  person.last_name: {person.last_name}")
    print(f"  person.full_name: {person.full_name}")

    # JSON serialization includes computed fields
    print(f"\nJSON: {person.model_dump_json()}")


def example_typed_computed():
    """Computed field with type hints."""
    print("\n" + "=" * 60)
    print("Example 2: Typed Computed Fields")
    print("=" * 60)

    class Calculator(modict):
        a: float
        b: float

        @modict.computed()
        def sum(self) -> float:
            return self.a + self.b

        @modict.computed()
        def product(self) -> float:
            return self.a * self.b

        @modict.computed()
        def description(self) -> str:
            return f"{self.a} and {self.b}"

    print("\nOriginal modict class:")
    print(f"  Regular fields: {[k for k, v in Calculator.__fields__.items() if not isinstance(v.get_default(), type(Calculator.__fields__['sum'].get_default()))]}")
    print(f"  Computed fields: {[k for k, v in Calculator.__fields__.items() if isinstance(v.get_default(), type(Calculator.__fields__['sum'].get_default()))]}")

    # Convert to Pydantic
    CalcModel = Calculator.to_model()

    print("\nConverted Pydantic Model:")
    print(f"  Regular fields: {list(CalcModel.model_fields.keys())}")
    print(f"  Computed fields: {list(CalcModel.model_computed_fields.keys())}")

    # Create and use
    calc = CalcModel(a=10.5, b=3.2)

    print("\nComputations:")
    print(f"  sum: {calc.sum}")
    print(f"  product: {calc.product}")
    print(f"  description: {calc.description}")


def example_complex_computed():
    """More complex computed fields."""
    print("\n" + "=" * 60)
    print("Example 3: Complex Computed Fields")
    print("=" * 60)

    class Rectangle(modict):
        width: float
        height: float

        @modict.computed()
        def area(self) -> float:
            """Calculate the area of the rectangle."""
            return self.width * self.height

        @modict.computed()
        def perimeter(self) -> float:
            """Calculate the perimeter of the rectangle."""
            return 2 * (self.width + self.height)

        @modict.computed()
        def diagonal(self) -> float:
            """Calculate the diagonal of the rectangle."""
            return (self.width ** 2 + self.height ** 2) ** 0.5

        @modict.computed()
        def is_square(self) -> bool:
            """Check if the rectangle is a square."""
            return self.width == self.height

    # Convert to Pydantic
    RectModel = Rectangle.to_model()

    print("\nRectangle Model:")
    print(f"  Fields: width, height")
    print(f"  Computed: {list(RectModel.model_computed_fields.keys())}")

    # Create instances
    rect = RectModel(width=5, height=3)
    square = RectModel(width=4, height=4)

    print("\nRectangle (5x3):")
    print(f"  area: {rect.area}")
    print(f"  perimeter: {rect.perimeter}")
    print(f"  diagonal: {rect.diagonal:.2f}")
    print(f"  is_square: {rect.is_square}")

    print("\nSquare (4x4):")
    print(f"  area: {square.area}")
    print(f"  perimeter: {square.perimeter}")
    print(f"  diagonal: {square.diagonal:.2f}")
    print(f"  is_square: {square.is_square}")


def example_mixed_fields():
    """Mix of regular, factory, and computed fields."""
    print("\n" + "=" * 60)
    print("Example 4: Mixed Field Types")
    print("=" * 60)

    class Order(modict):
        # Regular fields
        order_id: int
        customer_name: str

        # Field with default
        status: str = "pending"

        # Factory field
        items: list[str] = modict.factory(list)

        # Computed fields
        @modict.computed()
        def item_count(self) -> int:
            return len(self.items)

        @modict.computed()
        def summary(self) -> str:
            return f"Order #{self.order_id} for {self.customer_name}: {self.item_count} items ({self.status})"

    # Convert to Pydantic
    OrderModel = Order.to_model()

    print("\nOrder Model:")
    print(f"  Regular fields: {[k for k in OrderModel.model_fields.keys()]}")
    print(f"  Computed fields: {list(OrderModel.model_computed_fields.keys())}")

    # Create order
    order = OrderModel(order_id=123, customer_name="Alice")
    order.items.extend(["Book", "Pen", "Notebook"])

    print("\nOrder instance:")
    print(f"  order_id: {order.order_id}")
    print(f"  customer_name: {order.customer_name}")
    print(f"  status: {order.status}")
    print(f"  items: {order.items}")
    print(f"  item_count: {order.item_count}")
    print(f"  summary: {order.summary}")

    # JSON includes computed fields
    print(f"\nJSON serialization includes computed fields:")
    import json
    print(json.dumps(json.loads(order.model_dump_json()), indent=2))


def example_validation_with_computed():
    """Pydantic validation with computed fields."""
    print("\n" + "=" * 60)
    print("Example 5: Validation with Computed Fields")
    print("=" * 60)

    class Product(modict):
        name: str
        price: float
        tax_rate: float = 0.2

        @modict.computed()
        def tax_amount(self) -> float:
            return self.price * self.tax_rate

        @modict.computed()
        def total_price(self) -> float:
            return self.price + self.tax_amount

    ProductModel = Product.to_model()

    print("\nCreating product with validation:")
    product = ProductModel(name="Laptop", price=999.99)

    print(f"  name: {product.name}")
    print(f"  price: ${product.price:.2f}")
    print(f"  tax_rate: {product.tax_rate * 100}%")
    print(f"  tax_amount: ${product.tax_amount:.2f}")
    print(f"  total_price: ${product.total_price:.2f}")

    print("\nTrying invalid data:")
    try:
        invalid = ProductModel(name="Test", price="not a number")
    except Exception as e:
        print(f"  ✓ Validation error: {type(e).__name__}")

    print("\nComputed fields work in validated models:")
    product2 = ProductModel(name="Mouse", price=29.99, tax_rate=0.15)
    print(f"  {product2.name}: ${product2.price:.2f} + ${product2.tax_amount:.2f} = ${product2.total_price:.2f}")


if __name__ == "__main__":
    if PYDANTIC_AVAILABLE and PYDANTIC_V2:
        example_basic_computed()
        example_typed_computed()
        example_complex_computed()
        example_mixed_fields()
        example_validation_with_computed()

        print("\n" + "=" * 60)
        print("All examples completed successfully!")
        print("=" * 60)
        print("\nNote: Computed fields are read-only in Pydantic,")
        print("just like in modict with cache=True.")
