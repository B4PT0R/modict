import pytest

from modict import modict, Field


def test_numeric_constraints_ge_lt_and_multiple_of():
    class User(modict):
        age: int = Field(default=0, constraints={"ge": 0, "lt": 130, "multiple_of": 2})

    User(age=2)
    with pytest.raises(ValueError):
        User(age=-1)
    with pytest.raises(ValueError):
        User(age=131)
    with pytest.raises(ValueError):
        User(age=3)


def test_length_constraints_for_strings():
    class User(modict):
        name: str = Field(default="", constraints={"min_length": 2, "max_length": 5})

    User(name="ab")
    User(name="abcde")
    with pytest.raises(ValueError):
        User(name="a")
    with pytest.raises(ValueError):
        User(name="abcdef")


def test_pattern_constraint():
    class User(modict):
        code: str = Field(default="", constraints={"pattern": r"^[A-Z]{3}$"})

    User(code="ABC")
    with pytest.raises(ValueError):
        User(code="AB")
    with pytest.raises(ValueError):
        User(code="AbC")


def test_constraints_apply_on_assignment_when_enabled():
    class User(modict):
        _config = modict.config(validate_assignment=True)
        age: int = Field(default=0, constraints={"ge": 0})

    u = User(age=0)
    with pytest.raises(ValueError):
        u.age = -1
