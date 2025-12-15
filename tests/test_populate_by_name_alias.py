import pytest

from modict import modict, Field, MISSING


def test_alias_population_default_populate_by_name_false_disallows_field_name():
    class User(modict):
        _config = modict.config(populate_by_name=False)
        name: str = Field(default=MISSING, aliases={"alias": "full_name"})

    u = User({"full_name": "Alice"})
    assert u.name == "Alice"

    with pytest.raises(KeyError):
        User({"name": "Alice"})


def test_alias_population_populate_by_name_true_allows_field_name_and_alias():
    class User(modict):
        _config = modict.config(populate_by_name=True)
        name: str = Field(default=MISSING, aliases={"alias": "full_name"})

    u1 = User({"full_name": "Alice"})
    assert u1.name == "Alice"

    u2 = User({"name": "Bob"})
    assert u2.name == "Bob"


def test_alias_population_rejects_both_alias_and_field_name():
    class User(modict):
        _config = modict.config(populate_by_name=True)
        name: str = Field(default=MISSING, aliases={"alias": "full_name"})

    with pytest.raises(TypeError):
        User({"name": "Alice", "full_name": "Alice"})
