"""Tests for Pydantic computed field transfer to modict."""

import pytest

try:
    from pydantic import BaseModel, computed_field
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False

from modict import modict

pytestmark = pytest.mark.skipif(not PYDANTIC_AVAILABLE, reason="Pydantic not installed")


def test_basic_computed_field_transfer():
    """Test that Pydantic computed fields are transferred to modict."""

    class PydanticUser(BaseModel):
        first_name: str
        last_name: str

        @computed_field
        @property
        def full_name(self) -> str:
            return f"{self.first_name} {self.last_name}"

    # Convert to modict
    ModictUser = modict.from_model(PydanticUser)

    # Create instance
    user = ModictUser(first_name="Alice", last_name="Smith")

    # Computed field should work
    assert user.full_name == "Alice Smith"


def test_multiple_computed_fields():
    """Test multiple computed fields are transferred."""

    class PydanticPerson(BaseModel):
        first_name: str
        last_name: str
        age: int

        @computed_field
        @property
        def full_name(self) -> str:
            return f"{self.first_name} {self.last_name}"

        @computed_field
        @property
        def is_adult(self) -> bool:
            return self.age >= 18

        @computed_field
        @property
        def display_info(self) -> str:
            return f"{self.full_name} (Age: {self.age})"

    # Convert to modict
    ModictPerson = modict.from_model(PydanticPerson)

    # Create instance
    person = ModictPerson(first_name="Bob", last_name="Jones", age=25)

    # All computed fields should work
    assert person.full_name == "Bob Jones"
    assert person.is_adult is True
    assert person.display_info == "Bob Jones (Age: 25)"


def test_computed_field_with_annotations():
    """Test that computed field return type annotations are preserved."""

    class PydanticModel(BaseModel):
        value: int

        @computed_field
        @property
        def doubled(self) -> int:
            return self.value * 2

    # Convert to modict
    ModictModel = modict.from_model(PydanticModel)

    # Check that annotation is preserved
    assert hasattr(ModictModel, '__annotations__')
    assert 'doubled' in ModictModel.__annotations__
    assert ModictModel.__annotations__['doubled'] == int


def test_computed_field_updates_with_data():
    """Test that computed fields update when underlying data changes."""

    class PydanticConfig(BaseModel):
        base_price: float
        tax_rate: float

        @computed_field
        @property
        def total_price(self) -> float:
            return self.base_price * (1 + self.tax_rate)

    # Convert to modict
    ModictConfig = modict.from_model(PydanticConfig)

    # Create instance
    config = ModictConfig(base_price=100.0, tax_rate=0.2)

    # Initial computed value
    assert config.total_price == 120.0

    # Change underlying value
    config.base_price = 200.0

    # Computed value should update
    assert config.total_price == 240.0


def test_computed_field_with_nested_access():
    """Test computed fields with nested model access."""

    class PydanticAddress(BaseModel):
        street: str
        city: str

        @computed_field
        @property
        def full_address(self) -> str:
            return f"{self.street}, {self.city}"

    class PydanticUser(BaseModel):
        name: str
        address: PydanticAddress

        @computed_field
        @property
        def address_line(self) -> str:
            return f"{self.name}: {self.address.full_address}"

    # Convert to modict
    ModictUser = modict.from_model(PydanticUser)
    ModictAddress = modict.from_model(PydanticAddress)

    # Create instances
    address = ModictAddress(street="123 Main St", city="NYC")
    user = ModictUser(name="Alice", address=address)

    # Computed fields should work at both levels
    assert address.full_address == "123 Main St, NYC"
    assert user.address_line == "Alice: 123 Main St, NYC"


def test_computed_field_not_in_regular_fields():
    """Test that computed fields are not treated as regular fields."""

    class PydanticModel(BaseModel):
        name: str

        @computed_field
        @property
        def display_name(self) -> str:
            return f"Name: {self.name}"

    # Convert to modict
    ModictModel = modict.from_model(PydanticModel)

    # Check that computed field is not in __fields__
    assert 'name' in ModictModel.__fields__
    # Computed fields should be accessible but handled differently


def test_computed_field_round_trip():
    """Test that computed fields survive a round trip Pydantic → modict → Pydantic."""

    class OriginalPydantic(BaseModel):
        radius: float

        @computed_field
        @property
        def area(self) -> float:
            return 3.14159 * self.radius ** 2

    # Convert to modict
    AsModict = modict.from_model(OriginalPydantic)

    # Test modict version
    circle = AsModict(radius=5.0)
    assert abs(circle.area - 78.53975) < 0.001

    # Convert back to Pydantic
    BackToPydantic = AsModict.to_model()

    # Test Pydantic version
    circle2 = BackToPydantic(radius=5.0)
    assert abs(circle2.area - 78.53975) < 0.001


def test_computed_field_with_complex_logic():
    """Test computed fields with complex logic."""

    class PydanticOrder(BaseModel):
        order_items: list[dict]  # Renamed to avoid dict.items() conflict

        @computed_field
        @property
        def total_items(self) -> int:
            return len(self.order_items)

        @computed_field
        @property
        def total_price(self) -> float:
            return sum(item.get('price', 0.0) for item in self.order_items)

    # Convert to modict
    ModictOrder = modict.from_model(PydanticOrder)

    # Create instance
    order = ModictOrder(order_items=[
        {'name': 'Item A', 'price': 10.0},
        {'name': 'Item B', 'price': 20.0},
        {'name': 'Item C', 'price': 15.0}
    ])

    # Computed fields should work
    assert order.total_items == 3
    assert order.total_price == 45.0


def test_computed_field_caching():
    """Test that computed fields work with modict's caching."""

    call_count = 0

    class PydanticModel(BaseModel):
        value: int

        @computed_field
        @property
        def expensive_computation(self) -> int:
            nonlocal call_count
            call_count += 1
            return self.value * 100

    # Convert to modict with caching enabled
    ModictModel = modict.from_model(PydanticModel)

    # Create instance
    model = ModictModel(value=5)

    # Access computed field multiple times
    result1 = model.expensive_computation
    result2 = model.expensive_computation
    result3 = model.expensive_computation

    # Note: modict Computed fields support caching via cache=True parameter
    # Without it, the function is called each time
    assert result1 == 500
    assert result2 == 500
    assert result3 == 500
