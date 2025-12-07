import pytest

import modict as modict_pkg
from modict import (
    TypeMismatchError,
    coerce,
    modict,
    typechecked,
)


def test_attribute_access_and_defaults():
    class User(modict):
        name: str
        age: int = 30

    user = User(name="Alice")

    assert user.name == "Alice"
    assert user["age"] == 30  # default injected

    user.email = "a@example.com"  # attribute-style set writes to dict
    assert user["email"] == "a@example.com"
    user["age"] = 31
    assert user.age == 31


def test_auto_convert_nested_structures():
    data = modict({"users": [{"profile": {"city": "Paris"}}]})

    # list elements should be converted to modict lazily
    first_user = data["users"][0]
    assert isinstance(first_user, modict)
    assert first_user.profile.city == "Paris"

    # set_nested should create missing levels
    data.set_nested("settings.theme", "dark")
    assert data.get_nested("settings.theme") == "dark"


def test_convert_and_unconvert_roundtrip():
    original = {"a": {"b": [1, {"c": 2}]}}
    converted = modict.convert(original)

    assert isinstance(converted, modict)
    assert isinstance(converted.a, modict)
    assert isinstance(converted.a["b"][1], modict)
    assert converted.a.b[1].c == 2

    back_to_dict = modict.unconvert(converted)
    assert back_to_dict == original
    assert not isinstance(back_to_dict["a"], modict)


def test_computed_with_cache_and_invalidation():
    call_counter = {"count": 0}

    class Calc(modict):
        a: int = 1
        b: int = 2

        @modict.computed(cache=True, deps=["a", "b"])
        def total(self):
            call_counter["count"] += 1
            return self.a + self.b

    calc = Calc()
    assert calc.total == 3
    assert calc.total == 3  # cached
    assert call_counter["count"] == 1

    calc.a = 5  # invalidates cache via deps
    assert calc.total == 7
    assert call_counter["count"] == 2


def test_check_decorator_runs_and_transforms():
    class Profile(modict):
        email: str

        @modict.check("email")
        def normalize_email(self, value):
            return value.strip().lower()

    profile = Profile(email="  TEST@EMAIL.COM  ")
    assert profile.email == "test@email.com"
    profile.email = "NEW@MAIL.COM"
    assert profile.email == "new@mail.com"


def test_strict_and_allow_extra_enforced():
    class StrictModel(modict):
        _config = modict.config(strict=True, allow_extra=False)
        age: int

    sm = StrictModel(age=21)
    with pytest.raises(KeyError):
        sm["unexpected"] = 1

    with pytest.raises(TypeError):
        sm.age = "not-an-int"


def test_json_enforcement_blocks_non_serializable():
    class JSONOnly(modict):
        _config = modict.config(enforce_json=True)
        data: object

    with pytest.raises(ValueError):
        JSONOnly(data=set([1, 2, 3]))

    inst = JSONOnly(data={"ok": True})
    with pytest.raises(ValueError):
        inst.data = {1, 2, 3}  # set not JSON-serializable


def test_merge_and_deep_equals():
    base = modict({"db": {"host": "localhost", "port": 5432}})
    base.merge({"db": {"port": 3306, "ssl": True}})

    assert base.db.port == 3306
    assert base.db.ssl is True

    other = modict({"db": {"host": "localhost", "port": 3306, "ssl": True}})
    assert base.deep_equals(other)


def test_computed_dependency_chain_invalidation():
    call_counter = {"sum": 0, "double": 0}

    class Chain(modict):
        a: int = 1
        b: int = 2

        @modict.computed(cache=True, deps=["a", "b"])
        def summed(self):
            call_counter["sum"] += 1
            return self.a + self.b

        @modict.computed(cache=True, deps=["summed"])
        def doubled(self):
            call_counter["double"] += 1
            return self.summed * 2

    c = Chain()
    assert c.doubled == 6
    assert c.doubled == 6  # cached
    assert call_counter == {"sum": 1, "double": 1}

    c.b = 10  # should invalidate summed and doubled
    assert c.doubled == 22
    assert call_counter == {"sum": 2, "double": 2}


def test_version_exposed():
    assert isinstance(modict_pkg.__version__, str)
    assert modict_pkg.__version__ != ""


def test_coerce_utility_handles_common_structures():
    assert coerce("42", int) == 42
    assert coerce(("1", "2"), list[int]) == [1, 2]
    assert coerce([("k", "v")], dict[str, str]) == {"k": "v"}


def test_coercion_with_strict_type_checking_in_modict():
    class Person(modict):
        _config = modict.config(strict=True, coerce=True)
        age: int

    p = Person(age="5")
    assert p.age == 5 and isinstance(p.age, int)

    with pytest.raises(TypeError):
        p.age = "not-a-number"


def test_typechecked_decorator_checks_args_and_return():
    @typechecked
    def add(a: int, b: int) -> int:
        return a + b

    @typechecked
    def bad_return(a: int) -> int:
        return str(a)

    assert add(1, 2) == 3

    with pytest.raises(TypeMismatchError):
        add("x", 2)  # wrong arg type

    with pytest.raises(TypeMismatchError):
        bad_return(1)  # wrong return type
