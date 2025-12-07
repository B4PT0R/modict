# modict - The Swiss Army Knife of Python Data Structures

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**modict** is a sophisticated, hybrid data structure that combines the simplicity of Python dictionaries with the power of dataclasses and the robustness and runtime typechecking capabilities of Pydantic models. It's designed to be the versatile tool you'll want to use in every project for handling structured data.

## 🎯 Philosophy & Goals

**modict** bridges the gap between different Python data paradigms:

- **📚 Dict-like**: Native dictionary inheritance with full compatibility - modicts ARE dicts!
- **🏗️ Dataclass-like**: Type annotations and structured field definitions  
- **🛡️ Pydantic-like**: Runtime validation, type coercion, custom validators, and computed properties
- **🔧 Developer-friendly**: Intuitive API that "just works" for common patterns
- **100% standard library** - No external dependencies, all is coded from scratch including the typechecker and coercion engine

### Why modict?

```python
# Traditional approaches require choosing between flexibility and structure
data = {"name": "Alice", "age": 30}           # Dict: flexible but unstructured

@dataclass
class User: name: str; age: int               # Dataclass: structured but rigid

class User(BaseModel): name: str; age: int    # Pydantic: powerful but heavy

# modict: Best of all worlds
class User(modict):
    name: str
    age: int = 25

user = User(name="Alice")                   # ✅ Structured
user.age                                    # 25 ✅ Default value
user.email = "alice@email.com"              # ✅ Flexible  
user['phone'] = "123-456-7890"              # ✅ Dict-compatible
isinstance(user,dict)                       # True (still a dict!)
```

## 🚀 Key Features

### Core Capabilities
- **Full dict inheritance** - All native dict methods work seamlessly.
- **Attribute-style access** - `obj.key` and `obj['key']` both work
- **Type annotations** - Optional runtime validation with a powerful type validation and coercion system
- **Recursive conversion**  
  - Explicit: `modict.convert()` / `.to_modict()` for full deep conversion  
  - Automatic: `auto_convert=True` (default) converts nested dicts to `modict` on first access
- **JSON-first design** - Built-in JSON serialization/deserialization
- **Path-based access** - Access nested structures with dot notation

### Advanced Features
- **Computed properties** - Dynamic values with dependency tracking
- **Custom validators** - Field-level validation and transformation
- **Type coercion** - Intelligent type conversion system
- **Deep operations** - Merge, diff, walk through nested structures
- **Field extraction** - Select/exclude keys with simple methods

## 📦 Installation

```bash
pip install modict
```

## 🏃‍♂️ Quick Start

### Basic Usage

```python
from modict import modict

# Create from dict or keyword arguments
user = modict({"name": "Alice", "age": 30})
user = modict(name="Alice", age=30)

# Attribute and dict-style access
print(user.name)        # "Alice"
print(user['age'])      # 30

# Add new fields dynamically
user.email = "alice@email.com"
user['phone'] = "123-456-7890"
```

### Structured Classes

```python
from modict import modict
from typing import List, Optional

class User(modict):
    name: str
    age: int = 25
    email: Optional[str] = None
    tags: List[str] = modict.factory(list)  # Factory for mutable defaults

# Type-safe creation
user = User(name="Bob", age=35)
print(user.age)         # 35
print(user.tags)        # []
```

### Nested Structures & Path Access

```python
# Automatic recursive conversion
data = modict({
    "users": [
        {"name": "Alice", "profile": {"city": "Paris"}},
        {"name": "Bob", "profile": {"city": "Lyon"}}
    ],
    "settings": {"theme": "dark"}
})

# Path-based access
print(data.get_nested("users.0.name"))           # "Alice"
data.set_nested("users.0.profile.country", "France")
print(data.has_nested("settings.theme"))         # True

# Chained attribute access works too 
# (Only if auto_convert=True (default) - see below about config)
print(data.users[0].profile.city)                # "Paris"
```

## 💫 Advanced Features

### Computed Properties

```python
class Calculator(modict):
    a: float = 0
    b: float = 0
    
    @modict.computed(cache=True, deps=['a', 'b'])
    def sum_ab(self):
        print("Computing sum...")
        return self.a + self.b
    
    @modict.computed(cache=True, deps=['sum_ab'])  # Cascading dependencies
    def doubled_sum(self):
        return self.sum_ab * 2

calc = Calculator(a=10, b=20)
print(calc.sum_ab)         # "Computing sum..." → 30
print(calc.sum_ab)         # 30 (cached)
calc.a = 15                # Invalidates cache automatically
print(calc.sum_ab)         # "Computing sum..." → 35
print(calc.doubled_sum)    # 70
```

### Custom Validators

```python
class Profile(modict):
    email: str
    age: int
    
    @modict.check('email')
    def validate_email(self, value):
        """Clean and validate email addresses"""
        email = value.lower().strip()
        if '@' not in email:
            raise ValueError("Invalid email format")
        return email
    
    @modict.check('age')  
    def validate_age(self, value):
        """Ensure age is reasonable"""
        age = int(value)
        if age < 0 or age > 150:
            raise ValueError("Invalid age range")
        return age

profile = Profile(email="  ALICE@EMAIL.COM  ", age="30")
print(profile.email)  # "alice@email.com" (cleaned)
print(profile.age)    # 30 (converted to int)
```

### Deep Operations

```python
# Deep merging
network_config = modict({"db": {"host": "localhost", "port": 5432}})
overrides = {"db": {"port": 3306, "ssl": True}}
network_config.merge(overrides)
# Result: {"db": {"host": "localhost", "port": 3306, "ssl": True}}

# Walking through nested structures
data = modict({"users": [{"name": "Alice"}, {"name": "Bob"}]})
for path, value in data.walk():
    print(f"{path}: {value}")
# Output:
# users.0.name: Alice
# users.1.name: Bob

# Flattened view
flat = data.walked()  # {"users.0.name": "Alice", "users.1.name": "Bob"}
```

## 🛠️ Configuration Options

The cassmethod `modict.config` allows you to customize the behavior of your modict subclass.
It returns an `modictConfig` object (dataclass) that you may pass as the `_config` class variable or your modict.

```python
class MyModict(modict):
    _config = modict.config(
        auto_convert=True,          # Auto-convert dicts to modicts in nested sub-containers (upon access)
        strict=False,               # Strict runtime type checking
        coerce=False,               # Enable automatic type coercion
        allow_extra=True,           # Disallow extra attributes
        enforce_json=False,         # Enforce JSON serializability of values
    )
```

`auto_convert` controls whether dicts found in nested mutable containers (MutableMappings, MutableSequence) 
are automatically converted to `modict` (if they aren't already) on first access.
Note that MutableMappings that are NOT dicts won't be converted, but their content may if they are dicts.

Subclass configs are properly merged with parent class configs, also supporting multiple inheritance patterns (following MRO order).

```python
class Parent(modict):
    _config = modict.config(strict=True, coerce=False)

class Child(Parent):
    _config = modict.config(coerce=True)  # strict=True, coerce=True (overrides Parent)

class A(modict):
    _config = modict.config(strict=True)
    a: int=1
    value: str="A"

class B(modict):
    _config = modict.config(strict=False, coerce=True)
    b: int=2
    value: str="B"

class C(A,B):
    _config = modict.config(allow_extra=False) 
    # strict=True from A (A overrides B, since A follows B in MRO), 
    # coerce=True from B
    # allow_extra=False from C

c = C()
print(c.a) # 1
print(c.b) # 2
print(c.value) # "A" (A overrides B)
c.a = "3"
print(c.a) # 3 (coercion enabled)

try:
    c.a = "invalid" 
except Exception as e:
    print(e) # ❌ TypeError (strict mode enabled)

try:
    c.undefined = "value" 
except Exception as e:
    print(e) # ❌ KeyError (extra fields not allowed)
```

### Example

```python
class StrictConfig(modict):

    _config=modict.config(
        strict = True          # Enable runtime type checking
        allow_extra = False    # Disallow undefined fields
        coerce = True          # Enable type coercion
    )

    name: str
    count: int

config = StrictConfig(name="test", count=42)
# config.undefined = "value"    # ❌ KeyError (extra fields not allowed)
# config.count = "32"           # coerced to int (coercion enabled)
# config.count = "invalid"      # ❌ TypeError (can't be coerced, type checking raises an error)
```

## 📄 JSON Integration

```python

# JSON-enforced mode
class JSONConfig(modict):

    _config=modict.config(
        enforce_json=True
    )

# Built-in JSON support
config = JSONConfig.load("config.json")        # Load from file
config = JSONConfig.loads(json_string)         # Load from string

config.dump("output.json", indent=2)          # Save to file
json_str = config.dumps(indent=2)             # Convert to string

config.data = {1, 2, 3}   # ❌ ValueError (sets are not JSON-serializable)
```

## 🎨 Field Utilities

```python
user = modict(name="Alice", age=30, email="alice@email.com", phone="123-456")

# Extract specific fields
basic_info = user.extract('name', 'age')         # {"name": "Alice", "age": 30}

# Exclude sensitive fields  
public_info = user.exclude('email', 'phone')     # {"name": "Alice", "age": 30}

# Rename fields
user.rename(email='email_address')               # Changes key name

# Deep copy
backup = user.deepcopy()
```

## 🔄 Conversion & Compatibility

```python

# let's turn auto-conversion off globally (affects all modict instances created after this change)
modict._config.auto_convert = False

# Convert existing dicts to modicts (recursive)
data = {"user": {"name": "Alice"}, "count": 42}

safe_modict = modict(data)            # No auto-conversion
safe_modict.user.name                # ❌ AttributeError (user is still a dict)
safe_modict.user["name"]             # "Alice" (works with dict access)
isinstance(safe_modict.user, modict)  # False (it's a plain dict)
data["user"] is safe_modict.user     # True (same object)

modict_data = safe_modict.to_modict()  # Deep conversion (in-place on the structure)
isinstance(modict_data.user, modict)  # True (now it's a modict)
data["user"] is modict_data.user     # False: user has been converted to a new modict
modict_data.user.name                # ✅ "Alice" (user is now a modict)
dict_data = modict_data.to_dict()    # Back to plain dicts

# Factory method for clean conversion
converted = modict.convert(complex_nested_dict)
unconverted = modict.unconvert(converted)  # Back to plain dicts
```

## ⚠️ Important Behaviors & Limitations

### Descriptor Handling

modict distinguishes between **definitions** and **assignments** in class namespaces:

```python
class MyModict(modict):
    # ✅ DEFINITIONS (stay as class methods)
    @classmethod
    def my_classmethod(cls):
        return "method behavior"
    
    @property  
    def my_property(self):
        return "property behavior"
    
    # ✅ ASSIGNMENTS (become dict fields)
    external_func = some_external_function        # Stored in dict
    external_cm = classmethod(external_function)  # Stored in dict (may be non-callable)

obj = MyModict()
obj.my_classmethod()     # ✅ Works (bound method)
obj.external_func("x")   # ✅ Works (raw function, no binding)
obj.external_cm("x")     # ❌ May fail ('classmethod' object not callable)
```

**Principle**: *Syntax determines behavior*
- `def`/`@decorator` syntax → Class behavior (Python semantics)
- `=` assignment syntax → Data storage (user responsibility)

### Import Limitations

Imports inside class namespaces are treated as field assignments:

```python
# ❌ PROBLEMATIC
class MyModict(modict):
    import json        # Becomes a 'json' field in the modict

    def method(self):
        return json.dumps(self)  # ❌ NameError: 'json' not defined

# ✅ RECOMMENDED  
import json
class MyModict(modict):
    # json accessible via module scope
    pass
```

This limitation rarely affects normal usage of modict as a data structure.

### Memory Considerations

- **Validation overhead**: Type checking and coercion add runtime cost
- **Computed properties**: Cached values consume additional memory
- **Recursive conversion**: Deep nesting may impact performance

## 🆚 Comparison with Alternatives

| Feature | modict | dict | dataclass | Pydantic |
|---------|-------|------|-----------|----------|
| Dict compatibility | ✅ Full | ✅ Native | ❌ No | ❌ Limited |
| Attribute access | ✅ Yes | ❌ No | ✅ Yes | ✅ Yes |
| Type validation | ✅ Optional | ❌ No | ❌ No | ✅ Yes |
| Runtime flexibility | ✅ High | ✅ High | ❌ Low | ❌ Medium |
| Nested structures | ✅ Auto | ❌ Manual | ❌ Manual | ✅ Auto |
| JSON integration | ✅ Built-in | ❌ Manual | ❌ Manual | ✅ Built-in |
| Learning curve | 🟡 Medium | 🟢 Low | 🟢 Low | 🔴 High |
| Performance | 🟡 Good | 🟢 Excellent | 🟢 Excellent | 🟡 Good |

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### Development Setup

```bash
git clone https://github.com/your-username/modict.git
cd modict
pip install -e .[dev]
pytest
```

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Inspired by the flexibility of Python dicts, the structure of dataclasses, and the power of Pydantic
- Built with modern Python typing and metaclass techniques
- Community feedback and real-world usage patterns

---

**modict**: *Because data structures should be both powerful and pleasant to use* 🚀
