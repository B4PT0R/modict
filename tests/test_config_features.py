"""Tests for Pydantic-aligned configuration features."""

import pytest
from modict import modict


def test_frozen_immutability():
    """Test that frozen=True makes instances immutable."""

    class FrozenConfig(modict):
        _config = modict.config(frozen=True)
        name: str
        count: int = 0

    # Can create instance
    config = FrozenConfig(name="test", count=42)
    assert config.name == "test"
    assert config.count == 42

    # Cannot modify after creation
    with pytest.raises(TypeError, match="frozen"):
        config.name = "new name"

    with pytest.raises(TypeError, match="frozen"):
        config["name"] = "new name"

    with pytest.raises(TypeError, match="frozen"):
        config.new_field = "value"

    # Cannot delete
    with pytest.raises(TypeError, match="frozen"):
        del config.name

    with pytest.raises(TypeError, match="frozen"):
        del config["count"]


def test_frozen_false_allows_mutation():
    """Test that frozen=False allows mutations (default)."""

    class MutableConfig(modict):
        _config = modict.config(frozen=False)
        name: str

    config = MutableConfig(name="test")

    # Can modify
    config.name = "new name"
    assert config.name == "new name"

    config["name"] = "another name"
    assert config["name"] == "another name"

    # Can add fields
    config.extra = "allowed"
    assert config.extra == "allowed"

    # Can delete
    del config.extra
    assert "extra" not in config


def test_str_strip_whitespace():
    """Test str_strip_whitespace configuration."""

    class StripModel(modict):
        _config = modict.config(str_strip_whitespace=True, validate_assignment=True)
        name: str
        email: str

    # Whitespace is stripped
    model = StripModel(name="  Alice  ", email="\tbob@example.com\n")
    assert model.name == "Alice"
    assert model.email == "bob@example.com"

    # Also works on assignment
    model.name = "  Charlie  "
    assert model.name == "Charlie"

    # Non-strings are unaffected
    model.count = 42
    assert model.count == 42


def test_str_to_lower():
    """Test str_to_lower configuration."""

    class LowerModel(modict):
        _config = modict.config(str_to_lower=True, validate_assignment=True)
        username: str
        email: str

    model = LowerModel(username="AlIcE", email="BOB@EXAMPLE.COM")
    assert model.username == "alice"
    assert model.email == "bob@example.com"

    # Also works on assignment
    model.username = "CHARLIE"
    assert model.username == "charlie"


def test_str_to_upper():
    """Test str_to_upper configuration."""

    class UpperModel(modict):
        _config = modict.config(str_to_upper=True, validate_assignment=True)
        code: str
        status: str

    model = UpperModel(code="abc123", status="active")
    assert model.code == "ABC123"
    assert model.status == "ACTIVE"

    # Also works on assignment
    model.code = "xyz789"
    assert model.code == "XYZ789"


def test_str_transformations_combined():
    """Test combining multiple string transformations."""

    class CombinedModel(modict):
        _config = modict.config(
            str_strip_whitespace=True,
            str_to_lower=True
        )
        email: str

    # Strip then lowercase
    model = CombinedModel(email="  ALICE@EXAMPLE.COM  ")
    assert model.email == "alice@example.com"


def test_str_to_lower_and_upper_mutually_exclusive():
    """Test that str_to_lower takes precedence over str_to_upper."""

    class ConflictModel(modict):
        _config = modict.config(
            str_to_lower=True,
            str_to_upper=True  # Should be ignored
        )
        name: str

    # str_to_lower wins (checked first with elif)
    model = ConflictModel(name="MixedCase")
    assert model.name == "mixedcase"


def test_frozen_with_extra_modes():
    """Test frozen works with different extra modes."""

    class FrozenForbid(modict):
        _config = modict.config(frozen=True, extra='forbid')
        name: str

    config = FrozenForbid(name="test")

    # Frozen prevents modification
    with pytest.raises(TypeError, match="frozen"):
        config.name = "new"

    # Extra='forbid' also prevents new fields (but frozen is checked first)
    with pytest.raises(TypeError, match="frozen"):
        config.extra = "value"


def test_string_transformations_with_coercion():
    """Test that string transformations work with coercion."""

    class CoerceAndTransform(modict):
        _config = modict.config(
            strict=False,
            str_strip_whitespace=True,
            str_to_lower=True
        )
        email: str
        count: int

    # String is transformed
    model = CoerceAndTransform(email="  ALICE@EXAMPLE.COM  ", count="42")
    assert model.email == "alice@example.com"
    assert model.count == 42  # Coerced to int


def test_frozen_with_nested_modicts():
    """Test frozen on nested modict structures."""

    class FrozenParent(modict):
        _config = modict.config(frozen=True)
        name: str
        child: dict

    parent = FrozenParent(name="parent", child={"key": "value"})

    # Parent is frozen
    with pytest.raises(TypeError, match="frozen"):
        parent.name = "new"

    # But nested dict (not frozen) can be modified
    parent.child["key"] = "new value"  # This works (child is mutable dict)
    assert parent.child["key"] == "new value"


def test_string_transformations_preserve_none():
    """Test that None values are not transformed."""

    class NoneModel(modict):
        _config = modict.config(str_to_lower=True)
        name: str | None = None

    model = NoneModel()
    assert model.name is None

    model = NoneModel(name=None)
    assert model.name is None


def test_frozen_inheritance():
    """Test frozen inheritance."""

    class FrozenParent(modict):
        _config = modict.config(frozen=True)
        name: str

    class UnfrozenChild(FrozenParent):
        _config = modict.config(frozen=False)
        age: int

    # Child overrides frozen
    child = UnfrozenChild(name="test", age=25)
    child.name = "new"  # Should work
    assert child.name == "new"


def test_config_features_full_example():
    """Integration test with multiple config features."""

    class FullConfig(modict):
        _config = modict.config(
            extra='forbid',
            strict=False,
            frozen=False,
            validate_assignment=True,
            str_strip_whitespace=True,
            str_to_lower=True
        )
        username: str
        email: str
        age: int

    # All features work together
    config = FullConfig(
        username="  AlIcE  ",
        email="ALICE@EXAMPLE.COM",
        age="25"  # Will be coerced
    )

    assert config.username == "alice"
    assert config.email == "alice@example.com"
    assert config.age == 25

    # Can modify (not frozen)
    config.age = "30"
    assert config.age == 30

    # Extra fields forbidden
    with pytest.raises(KeyError):
        config.extra = "not allowed"
