# Pydantic Interoperability

`modict` provides seamless interoperability with Pydantic, allowing you to convert between Pydantic model classes and modict classes at the class level (not just instances).

## Installation

Pydantic is an **optional dependency**. Install it separately:

```bash
pip install pydantic
```

## Key Features

- **Class-level conversion**: Convert entire class definitions, not just instances
- **Bidirectional**: Convert from Pydantic to modict and vice versa
- **Field preservation**: Type hints, defaults, and factories are preserved
- **No hard dependency**: Pydantic is only imported when these methods are used
- **Works with both Pydantic v1 and v2**

## API

### `modict.from_model()`

Convert a Pydantic BaseModel class to a modict class.

```python
@classmethod
def from_model(
    cls,
    pydantic_class,
    *,
    name=None,          # Custom name for the new modict class
    strict=None,        # Pydantic-like strict mode (no coercion)
    coerce=None,        # Deprecated alias; use strict=False instead
    **config_kwargs     # Additional modict config options
) -> Type[modict]
```

### `modict.to_model()`

Convert a modict class to a Pydantic BaseModel class.

```python
@classmethod
def to_model(
    cls,
    *,
    name=None,          # Custom name for the new Pydantic class
    config_class=None,  # Optional Pydantic Config class
    **config_kwargs     # Pydantic config options
) -> Type[BaseModel]
```

## Examples

### Basic Conversion: Pydantic → modict

```python
from pydantic import BaseModel
from modict import modict

# Define a Pydantic model
class UserModel(BaseModel):
    name: str
    age: int = 25
    email: str | None = None

# Convert to modict class
User = modict.from_model(UserModel)

# Use it like any modict
user = User(name="Alice")
user.age  # 25 (default value preserved)
user.admin = True  # Can add extra fields (modict flexibility)
```

### Basic Conversion: modict → Pydantic

```python
from modict import modict

# Define a modict class
class Product(modict):
    name: str
    price: float
    stock: int = 0

# Convert to Pydantic
ProductModel = Product.to_model()

# Use Pydantic validation
product = ProductModel(name="Laptop", price=999.99)

# This will raise ValidationError (Pydantic strictness)
try:
    invalid = ProductModel(name="Test", price="not a number")
except ValidationError:
    print("Validation failed!")
```

### With modict Config

```python
from pydantic import BaseModel
from modict import modict

class APIResponse(BaseModel):
    status: str
    code: int
    data: dict

# Convert with strict mode and coercion
Response = modict.from_model(
    APIResponse,
    strict=False
)

# Now string "200" will be coerced to int 200
response = Response(status="ok", code="200", data={})
response.code  # 200 (int, not str)
```

### Factory Fields

Both Pydantic's `Field(default_factory=...)` and modict's `modict.factory()` are preserved:

```python
from pydantic import BaseModel, Field
from modict import modict

# Pydantic with factory
class UserModel(BaseModel):
    name: str
    tags: list[str] = Field(default_factory=list)

User = modict.from_model(UserModel)

user1 = User(name="Alice")
user2 = User(name="Bob")

user1.tags.append("python")
# user2.tags is still [] - separate instances!

# modict with factory
class Product(modict):
    title: str
    categories: list[str] = modict.factory(list)

ProductModel = Product.to_model()

# Works the same way in Pydantic
```

### Round-trip Conversion

```python
from pydantic import BaseModel
from modict import modict

# Start with Pydantic
class PersonModel(BaseModel):
    first_name: str
    last_name: str
    age: int

# Convert to modict
Person = modict.from_model(PersonModel)

# Convert back to Pydantic (with custom name)
NewPersonModel = Person.to_model(name="PersonV2")

# All three work the same
pydantic_v1 = PersonModel(first_name="Alice", last_name="Smith", age=30)
modict_ver = Person(first_name="Bob", last_name="Jones", age=25)
pydantic_v2 = NewPersonModel(first_name="Charlie", last_name="Brown", age=35)
```

### Data Transfer Between Instances

```python
from pydantic import BaseModel
from modict import modict

class DataModel(BaseModel):
    id: int
    content: str

Data = modict.from_model(DataModel)

# Create modict instance
modict_data = Data(id=1, content="Hello")

# Transfer to Pydantic (using dict conversion)
pydantic_data = DataModel.model_validate(dict(modict_data))

# Transfer back to modict
modict_data2 = Data(**pydantic_data.model_dump())
```

## Use Cases

### 1. API Development

Use Pydantic for request/response validation, convert to modict for flexible data manipulation:

```python
from pydantic import BaseModel
from modict import modict

# API schema (strict validation)
class UserRequest(BaseModel):
    email: str
    password: str

# Internal representation (flexible)
User = modict.from_model(UserRequest, strict=False)

def create_user(request_data: dict):
    # Validate with Pydantic
    validated = UserRequest.model_validate(request_data)

    # Work with modict
    user = User(**validated.model_dump())
    user.id = generate_id()  # Add extra fields
    user.created_at = datetime.now()

    return user
```

### 2. Configuration Management

Define schemas in Pydantic, use modict for runtime config manipulation:

```python
from pydantic import BaseModel
from modict import modict

class DatabaseConfig(BaseModel):
    host: str
    port: int = 5432
    database: str

# Convert for flexible config handling
Config = modict.from_model(DatabaseConfig)

config = Config(host="localhost", database="myapp")
config.port  # 5432 (default)

# Add runtime overrides
config.timeout = 30
config.pool_size = 10
```

### 3. Testing

Define strict Pydantic models, convert to modict for flexible test fixtures:

```python
from pydantic import BaseModel
from modict import modict

class User(BaseModel):
    id: int
    name: str
    email: str

TestUser = modict.from_model(User)

def test_something():
    # Create test data with flexibility
    user = TestUser(id=1, name="Test")
    user.email = "test@example.com"
    user.is_test = True  # Extra field for testing

    # Convert back for validation
    validated = User.model_validate(dict(user.extract('id', 'name', 'email')))
```

## Computed Fields Support

**NEW**: modict computed fields are now converted to Pydantic v2's `@computed_field` decorator!

```python
from modict import modict

class Person(modict):
    first_name: str
    last_name: str

    @modict.computed()
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

# Convert to Pydantic (requires Pydantic v2)
PersonModel = Person.to_model()

person = PersonModel(first_name="Alice", last_name="Smith")
person.full_name  # "Alice Smith"

# Computed fields are included in JSON serialization
person.model_dump()  # {'first_name': 'Alice', 'last_name': 'Smith', 'full_name': 'Alice Smith'}
```

**Note**: Computed field conversion requires **Pydantic v2**. With Pydantic v1, computed fields are skipped.

See [pydantic_computed_fields.py](pydantic_computed_fields.py) for more examples.

## Custom Validators Support

**NEW**: Custom validators are now fully bidirectional between modict and Pydantic!

### modict → Pydantic

```python
from modict import modict

class User(modict):
    email: str

    @modict.check('email')
    def validate_email(self, value):
        return value.lower().strip()

# Convert to Pydantic
UserModel = User.to_model()

user = UserModel(email="  ALICE@EXAMPLE.COM  ")
user.email  # "alice@example.com" - validator works!
```

### Pydantic → modict

```python
from pydantic import BaseModel, field_validator

class ProductModel(BaseModel):
    name: str

    @field_validator('name')
    @classmethod
    def validate_name(cls, value):
        return value.strip().title()

# Convert to modict
Product = modict.from_model(ProductModel)

product = Product(name="  laptop  ")
product.name  # "Laptop" - validator transferred!
```

### Features

- ✅ **Bidirectional conversion** - Works in both directions
- ✅ **Multiple validators** - Chained validators are preserved in order
- ✅ **Error handling** - Validators that raise errors work correctly
- ✅ **Pydantic v1 & v2** - Compatible with both versions

See [pydantic_validators.py](pydantic_validators.py) for detailed examples.

## Limitations

1. **Computed fields**: Requires Pydantic v2 (skipped in v1). Caching and dependencies are not preserved.
2. **Nested models**: Nested Pydantic models preserve their type in annotations, but you may need to convert them separately
3. **Config merging**: modict and Pydantic have different config systems; they don't automatically merge

## Error Handling

If Pydantic is not installed:

```python
from modict import modict

class User(modict):
    name: str

try:
    UserModel = User.to_model()
except ImportError as e:
    print(e)  # "Pydantic is required for this feature. Install it with: pip install pydantic"
```

Invalid conversions:

```python
from modict import modict

class NotPydantic:
    name: str

try:
    User = modict.from_model(NotPydantic)
except TypeError as e:
    print(e)  # "Expected Pydantic BaseModel class, got ..."
```

## Best Practices

1. **Use Pydantic for validation boundaries** (API inputs, external data)
2. **Use modict for internal flexibility** (business logic, data manipulation)
3. **Convert at boundaries**, not in hot paths (class conversion is one-time, but adds overhead)
4. **Leverage both strengths**:
   - Pydantic: Strict validation, JSON schema generation, API documentation
   - modict: Flexible attribute access, computed properties, nested operations

## Running the Example

```bash
python examples/pydantic_interop.py
```

## See Also

- [Pydantic Documentation](https://docs.pydantic.dev/)
- [modict README](../README.md)
- [Test Suite](../tests/test_pydantic_interop.py)
