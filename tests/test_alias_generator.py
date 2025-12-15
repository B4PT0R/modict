import pytest

from modict import modict, Field, MISSING


def test_alias_generator_generates_aliases_for_input():
    class User(modict):
        _config = modict.config(alias_generator=str.upper, populate_by_name=False)
        name: str = Field(default=MISSING)

    u = User({"NAME": "Alice"})
    assert u.name == "Alice"

    with pytest.raises(KeyError):
        User({"name": "Alice"})


def test_alias_generator_does_not_override_explicit_aliases():
    class User(modict):
        _config = modict.config(alias_generator=str.upper, populate_by_name=False, extra="forbid")
        name: str = Field(default=MISSING, aliases={"alias": "full_name"})

    u = User({"full_name": "Alice"})
    assert u.name == "Alice"

    with pytest.raises(KeyError):
        User({"NAME": "Alice"})


def test_alias_generator_invalid_return_type_raises():
    def bad(_field_name: str):
        return 123

    with pytest.raises(TypeError):
        class User(modict):
            _config = modict.config(alias_generator=bad)
            name: str = Field(default=MISSING)
