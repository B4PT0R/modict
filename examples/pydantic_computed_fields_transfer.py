"""
Demonstration of Pydantic computed fields transfer to modict.

Pydantic v2 introduced @computed_field decorators that define properties
computed from other fields. modict now automatically transfers these
computed fields when converting from Pydantic models.
"""

from modict import modict

try:
    from pydantic import BaseModel, computed_field
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False
    print("⚠️  Pydantic v2 required - this example requires Pydantic >= 2.0")
    exit(0)


# ============================================================================
# Example 1: Basic Computed Field Transfer
# ============================================================================

print("=" * 70)
print("Example 1: Basic Computed Field Transfer")
print("=" * 70)

class PydanticUser(BaseModel):
    first_name: str
    last_name: str

    @computed_field
    @property
    def full_name(self) -> str:
        """Computed field combining first and last name."""
        return f"{self.first_name} {self.last_name}"

# Convert to modict - computed field is automatically transferred
ModictUser = modict.from_model(PydanticUser)

# Create instances and test
pydantic_user = PydanticUser(first_name="Alice", last_name="Smith")
modict_user = ModictUser(first_name="Alice", last_name="Smith")

print(f"Pydantic user full_name: {pydantic_user.full_name}")
print(f"modict user full_name:   {modict_user.full_name}")
print(f"Both work identically: {pydantic_user.full_name == modict_user.full_name}")

print()


# ============================================================================
# Example 2: Multiple Computed Fields
# ============================================================================

print("=" * 70)
print("Example 2: Multiple Computed Fields")
print("=" * 70)

class PydanticCircle(BaseModel):
    radius: float

    @computed_field
    @property
    def diameter(self) -> float:
        return self.radius * 2

    @computed_field
    @property
    def circumference(self) -> float:
        return 2 * 3.14159 * self.radius

    @computed_field
    @property
    def area(self) -> float:
        return 3.14159 * self.radius ** 2

# Convert to modict
ModictCircle = modict.from_model(PydanticCircle)

# All computed fields are transferred
circle = ModictCircle(radius=5.0)
print(f"Radius: {circle.radius}")
print(f"Diameter: {circle.diameter}")
print(f"Circumference: {circle.circumference:.2f}")
print(f"Area: {circle.area:.2f}")

print()


# ============================================================================
# Example 3: Dynamic Computed Fields
# ============================================================================

print("=" * 70)
print("Example 3: Dynamic Computed Fields (Update with Data Changes)")
print("=" * 70)

class PydanticPrice(BaseModel):
    base_price: float
    tax_rate: float

    @computed_field
    @property
    def total_price(self) -> float:
        return self.base_price * (1 + self.tax_rate)

# Convert to modict
ModictPrice = modict.from_model(PydanticPrice)

# Create instance
price = ModictPrice(base_price=100.0, tax_rate=0.2)
print(f"Initial - Base: ${price.base_price}, Total: ${price.total_price}")

# Change underlying values
price.base_price = 150.0
print(f"After base price change - Base: ${price.base_price}, Total: ${price.total_price}")

price.tax_rate = 0.15
print(f"After tax change - Base: ${price.base_price}, Total: ${price.total_price}")

print()


# ============================================================================
# Example 4: Computed Fields with Complex Logic
# ============================================================================

print("=" * 70)
print("Example 4: Computed Fields with Complex Logic")
print("=" * 70)

class PydanticEmployee(BaseModel):
    name: str
    age: int
    years_experience: int
    performance_rating: float  # 0.0 to 1.0

    @computed_field
    @property
    def is_senior(self) -> bool:
        """Senior if 5+ years experience."""
        return self.years_experience >= 5

    @computed_field
    @property
    def is_eligible_for_promotion(self) -> bool:
        """Eligible if senior and high performance."""
        return self.is_senior and self.performance_rating >= 0.8

    @computed_field
    @property
    def summary(self) -> str:
        """Summary string with all derived info."""
        status = "Senior" if self.is_senior else "Junior"
        promotion = "Eligible" if self.is_eligible_for_promotion else "Not eligible"
        return f"{self.name} ({status}) - {promotion} for promotion"

# Convert to modict
ModictEmployee = modict.from_model(PydanticEmployee)

# Create employees
emp1 = ModictEmployee(
    name="Alice",
    age=30,
    years_experience=7,
    performance_rating=0.9
)

emp2 = ModictEmployee(
    name="Bob",
    age=25,
    years_experience=3,
    performance_rating=0.85
)

print(emp1.summary)
print(emp2.summary)

print()


# ============================================================================
# Example 5: Nested Models with Computed Fields
# ============================================================================

print("=" * 70)
print("Example 5: Nested Models with Computed Fields")
print("=" * 70)

class PydanticAddress(BaseModel):
    street: str
    city: str
    zip_code: str

    @computed_field
    @property
    def full_address(self) -> str:
        return f"{self.street}, {self.city} {self.zip_code}"

class PydanticPerson(BaseModel):
    name: str
    address: PydanticAddress

    @computed_field
    @property
    def mailing_label(self) -> str:
        return f"{self.name}\n{self.address.full_address}"

# Convert to modict
ModictPerson = modict.from_model(PydanticPerson)
ModictAddress = modict.from_model(PydanticAddress)

# Create nested structure
person = ModictPerson(
    name="Charlie Brown",
    address=ModictAddress(
        street="123 Main St",
        city="Springfield",
        zip_code="12345"
    )
)

print("Mailing Label:")
print(person.mailing_label)

print()


# ============================================================================
# Example 6: Round-Trip Conversion
# ============================================================================

print("=" * 70)
print("Example 6: Round-Trip Conversion (Pydantic → modict → Pydantic)")
print("=" * 70)

class Original(BaseModel):
    width: float
    height: float

    @computed_field
    @property
    def area(self) -> float:
        return self.width * self.height

    @computed_field
    @property
    def perimeter(self) -> float:
        return 2 * (self.width + self.height)

# Pydantic → modict
AsModict = modict.from_model(Original)
rect1 = AsModict(width=10.0, height=5.0)
print(f"modict version - Area: {rect1.area}, Perimeter: {rect1.perimeter}")

# modict → Pydantic
BackToPydantic = AsModict.to_model()
rect2 = BackToPydantic(width=10.0, height=5.0)
print(f"Pydantic version - Area: {rect2.area}, Perimeter: {rect2.perimeter}")

print("✅ Computed fields preserved through round-trip conversion!")

print()


# ============================================================================
# Example 7: Type Annotations Preserved
# ============================================================================

print("=" * 70)
print("Example 7: Type Annotations Preserved")
print("=" * 70)

class PydanticTyped(BaseModel):
    count: int

    @computed_field
    @property
    def doubled(self) -> int:
        return self.count * 2

    @computed_field
    @property
    def is_positive(self) -> bool:
        return self.count > 0

# Convert to modict
ModictTyped = modict.from_model(PydanticTyped)

# Check annotations are preserved
print("Annotations in modict class:")
for field_name, field_type in ModictTyped.__annotations__.items():
    print(f"  {field_name}: {field_type}")

print()


# ============================================================================
# Summary
# ============================================================================

print("=" * 70)
print("Summary")
print("=" * 70)
print("""
Pydantic computed field transfer features:

1. ✅ Automatic transfer - @computed_field properties are converted to modict Computed
2. ✅ Dynamic updates - computed values update when underlying data changes
3. ✅ Type annotations preserved - return types are maintained
4. ✅ Complex logic supported - computed fields can reference other computed fields
5. ✅ Nested models - computed fields work in nested structures
6. ✅ Round-trip conversion - computed fields survive Pydantic ↔ modict conversions
7. ✅ Multiple fields - unlimited computed fields per model

Note: Computed field conversion is automatic when using modict.from_model().
No manual configuration needed!
""")
