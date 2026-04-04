# modict — You already know Python dicts. You just unlocked the next level.

You probably write dicts everywhere:

```python
user = {"name": "Alice", "age": 30, "email": "alice@example.com"}
```

And that's a great choice — dicts are fast, flexible, and universal. But as your project grows, you might want to **type** some fields, **validate** values, **derive** computed properties, or **diff** two versions. So you reach for a `dataclass` or a Pydantic `BaseModel`... and suddenly it no longer behaves like a dict. You have to convert, serialize, traverse, adapt.

**modict lets you stay in dict-land while gaining all of that.**

---

## Start like a plain dict

```python
from modict import modict

user = modict(name="Alice", age=30, email="alice@example.com")
print(user.name)   # "Alice" — attribute access
print(user["age"]) # 30     — dict access, equally valid
assert isinstance(user, dict)  # True
```

Both access styles work interchangeably. A modict serializes to JSON and works with all your existing functions, no changes needed.

---

## Add types when you're ready

Later, you want to make the structure explicit. Declare a subclass:

```python
class User(modict):
    name: str
    age: int = 0
    email: str = modict.field(required='always')

user = User(name="Alice", age=30, email="alice@example.com")
user.age = "thirty"  # TypeError — automatically
```

The dict is now typed. Assignments are checked, defaults are applied, required fields can't be deleted.

> [!NOTE]
> By default (`require_all="at_init"`), annotated fields without a default must be provided at construction — but can be freely deleted afterwards. modict stays a mutable dict. To enforce permanent presence, use `modict.field(required="always")` or `_config = modict.config(require_all="always")`. To make fields fully optional, use `require_all="never"`.

---

## Add computed fields

Your `User` needs a display name derived from its parts. Split the name and add a computed field:

```python
class User(modict):
    first_name: str
    last_name: str
    age: int = 0
    email: str = modict.field(required=True)

    @modict.computed(deps=["first_name", "last_name"])
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

user = User(first_name="Alice", last_name="Martin", age=30, email="alice@example.com")
print(user.full_name)  # "Alice Martin"
user.last_name = "Dupont"
print(user.full_name)  # "Alice Dupont" — recomputed automatically
```

---

## And it's still a dict

```python
import json
json.dumps(user)       # works — no .model_dump() or .dict() needed
dict(user)             # works
{**user, "extra": 1}   # works
```

---

## Parse from JSON

Your `User` comes from an API payload? modict parses directly into your model:

```python
payload = '{"first_name": "Alice", "last_name": "Martin", "age": 30, "email": "alice@example.com"}'
user = User.loads(payload)  # JSON → validated User automatically
```

And if the structure is deeply nested, you don't need to write `app["users"][0]["email"]` everywhere. Nested dicts are auto-upgraded, so chained attribute access just works:

```python
class App(modict):
    name: str
    users: list[User] = modict.factory(list)

app = App(
    name="myapp",
    users=[
        {"first_name": "Alice", "last_name": "Martin", "age": 30, "email": "alice@example.com"},
        {"first_name": "Bob",   "last_name": "Smith",  "age": 25, "email": "bob@example.com"},
    ]
)

email = app.users[0].email  # "alice@example.com"

# or JSONPath helpers for programmatic access
app.get_nested("$.users[0].email")                      # "alice@example.com"
app.set_nested("$.users[0].email", "alice@company.com")
app.has_nested("$.users[1].email")                      # True
```

---

## Add validators

Your `User` needs business rules. Add field-level and model-level validators:

```python
class User(modict):
    first_name: str
    last_name: str
    age: int = 0
    email: str = modict.field(required=True)
    role: str = "user"

    @modict.computed(deps=["first_name", "last_name"])
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @modict.validator("age", mode='after')
    def check_age(self, value):
        if value < 0:
            raise ValueError("Age must be positive")
        return value

    @modict.model_validator(mode="after")
    def check_admin_age(self):
        if self.role == "admin" and self.age < 18:
            raise ValueError("Admin users must be at least 18")
```

---

## Compare and merge

You want to compare two versions of a `User` — before and after an update. modict has tools for that:

```python
before = User(first_name="Alice", last_name="Martin", age=30, email="alice@example.com", role="user")
after  = User(first_name="Alice", last_name="Martin", age=30, email="alice@example.com", role="admin")

before.diff(after)
# yields (path,changes) pairs, here: "$.role", ("user", "admin")

before.merge(after)  # in-place deep merge
```

And to traverse the full structure, leaf by leaf:

```python
for path, value in user.walk():
    print(path, "→", value)
# $.first_name → Alice
# $.last_name → Martin
# $.age → 30
# ...
```

---

## Search your data like a query

You have a list of users and want to find all admins without a manual loop:

```python
from modict import Query

class App(modict):
    name:str
    users:list[User] = modict.factory(list)

app = App(
    name="myapp",
    users=[
        User(first_name="Alice", last_name="Martin", age=30, email="a@example.com", role="admin"),
        User(first_name="Bob",   last_name="Smith",  age=25, email="b@example.com", role="user"),
        User(first_name="Carol", last_name="Jones",  age=35, email="c@example.com", role="admin"),
    ]
)

admins = app.found(Query(path="$.users[*]", value=lambda u: u.role == "admin"))
# returns all admin User dicts, indexed by their paths
```

---

## Fine-grained control over what's allowed

Lock down your `User` to reject unknown keys:

```python
class User(modict):
    _config = modict.config(extra="forbid")
    first_name: str
    last_name: str
    ...

User(first_name="Alice", last_name="Martin", unknown_field="oops")
# KeyError: "unknown_field" is not a declared field
```

Or make it immutable after construction:

```python
class User(modict):
    _config = modict.config(frozen=True)
    ...

user = User(first_name="Alice", last_name="Martin", age=30, email="alice@example.com")
user.age = 31  # TypeError
```

---

## Metadata outside the payload

Sometimes you need runtime state that must never leak into your JSON, your diffs, or your comparisons — a session id, a cache key, an internal flag. `attr` stores it outside the dict payload entirely:

```python
user = User(first_name="Alice", last_name="Martin", age=30, email="alice@example.com")
user.set_attr("_session_id", "abc123")

json.dumps(user)              # {"first_name": "Alice", ...} — no _session_id
user.has_attr("_session_id")  # True — available at runtime, invisible outside
```

---

## Inheritance: compose your models

Your `User` can be a base for more specific models:

```python
class User(modict):
    _config = modict.config(extra="forbid")
    first_name: str
    last_name: str
    age: int = 0
    email: str = modict.field(required=True)
    role: str = "user"

class AdminUser(User):
    role: str = "admin"
    permissions: list = modict.factory(list)
    department: str = modict.field(required=True)
```

Each level inherits fields, validators, and config from its parent. Override only what changes.

---

## A runtime type system included

modict ships its own type checking engine that you can also use directly:

```python
from modict import check_type, coerce

check_type(list[int], [1, 2, 3])      # True
check_type(list[int], [1, "two", 3])  # False

coerce(["1", "2", "3"], list[int])    # [1, 2, 3]
```

It handles pretty much all modern Python types — `int | None`, `list[str]`, `dict[str, Any]`, `Literal`, `TypedDict`, `Protocol`, and more — with no extra dependencies.

---

## In short: the progressive path

```
user = modict(...)               → enhanced dict, nothing more
class User(modict):
    first_name: str              → typing and coercion
    @computed(deps=[...])        → derived fields with cache
    @validator / @model_validator → business validation
    _config = modict.config(...) → structural constraints
```

You only enable what you need, when you need it.

How does it compare?

|                              | plain dict | dataclass | Pydantic BaseModel | **modict** |
|------------------------------|------------|-----------|--------------------|------------|
| Progressive (start simple)   | 🟢         | 🟡        | 🟡                 | 🟢         |
| It's a real dict             | 🟢         | 🔴        | 🔴                 | 🟢         |
| Type annotations             | 🔴         | 🟢        | 🟢                 | 🟢         |
| Runtime type checking        | 🔴         | 🔴        | 🟢                 | 🟢         |
| Mutability control (frozen)  | 🔴         | 🟡        | 🟢                 | 🟢         |
| JSON without conversion      | 🟢         | 🔴        | 🔴                 | 🟢         |
| Serialization helpers        | 🔴         | 🔴        | 🟢                 | 🟡         |
| Nested traversal & diffing   | 🔴         | 🔴        | 🔴                 | 🟢         |
| Learning curve (to expert)   | 🟢         | 🟡        | 🔴                 | 🟡         |
| Advanced use cases           | 🔴         | 🟡        | 🟢                 | 🟢         |
| Performance                  | 🟢         | 🟢        | 🟡                 | 🟡         |


## Try it!

```
pip install modict
```
