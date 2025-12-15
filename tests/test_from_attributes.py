import pytest

from modict import modict


class Plain:
    def __init__(self, name: str, age: int):
        self.name = name
        self.age = age
        self.extra = "x"


def test_from_attributes_enabled_builds_from_object_attributes():
    class User(modict):
        _config = modict.config(from_attributes=True)
        name: str
        age: int

    u = User(Plain("Alice", 30))
    assert u.name == "Alice"
    assert u.age == 30
    assert "extra" not in u


def test_from_attributes_disabled_does_not_accept_object():
    class User(modict):
        name: str
        age: int

    with pytest.raises(TypeError):
        User(Plain("Alice", 30))
