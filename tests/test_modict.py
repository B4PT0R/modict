import pytest

from modict import modict


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
