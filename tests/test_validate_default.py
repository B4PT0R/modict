"""Tests for validate_default configuration feature."""

import pytest
from typing import List, Dict, Optional
from modict import modict


def test_validate_default_disabled():
    """Test that invalid defaults are allowed when validate_default=False."""

    class Config(modict):
        _config = modict.config(validate_default=False)
        name: str = 123  # Wrong type, but should work

    # Should not raise at class definition
    assert Config.__fields__['name'].default == 123


def test_validate_default_enabled_valid():
    """Test that valid defaults pass when validate_default=True."""

    class Config(modict):
        _config = modict.config(validate_default=True)
        name: str = "Alice"
        age: int = 25
        active: bool = True

    # Should not raise
    config = Config()
    assert config.name == "Alice"
    assert config.age == 25
    assert config.active is True


def test_validate_default_enabled_invalid_str():
    """Test that invalid str default raises TypeError."""

    with pytest.raises(TypeError, match="Invalid default value for field 'name'"):
        class Config(modict):
            _config = modict.config(validate_default=True)
            name: str = 123  # Wrong type


def test_validate_default_enabled_invalid_int():
    """Test that invalid int default raises TypeError."""

    with pytest.raises(TypeError, match="Invalid default value for field 'age'"):
        class Config(modict):
            _config = modict.config(validate_default=True)
            age: int = "not a number"


def test_validate_default_enabled_invalid_bool():
    """Test that invalid bool default raises TypeError."""

    with pytest.raises(TypeError, match="Invalid default value for field 'active'"):
        class Config(modict):
            _config = modict.config(validate_default=True)
            active: bool = "not a bool"


def test_validate_default_with_optional():
    """Test validate_default with Optional types."""

    class Config(modict):
        _config = modict.config(validate_default=True)
        name: Optional[str] = None
        age: Optional[int] = 25

    # Both None and value should work
    config = Config()
    assert config.name is None
    assert config.age == 25


def test_validate_default_with_optional_invalid():
    """Test that invalid Optional default raises TypeError."""

    with pytest.raises(TypeError, match="Invalid default value for field 'age'"):
        class Config(modict):
            _config = modict.config(validate_default=True)
            age: Optional[int] = "not valid"


def test_validate_default_with_list():
    """Test validate_default with list types."""

    class Config(modict):
        _config = modict.config(validate_default=True)
        numbers: List[int] = [1, 2, 3]

    config = Config()
    assert config.numbers == [1, 2, 3]


def test_validate_default_with_list_invalid():
    """Test that invalid list default raises TypeError."""

    with pytest.raises(TypeError, match="Invalid default value for field 'numbers'"):
        class Config(modict):
            _config = modict.config(validate_default=True)
            numbers: List[int] = "not a list"


def test_validate_default_with_dict():
    """Test validate_default with dict types."""

    class Config(modict):
        _config = modict.config(validate_default=True)
        settings: Dict[str, int] = {"a": 1, "b": 2}

    config = Config()
    assert config.settings == {"a": 1, "b": 2}


def test_validate_default_with_dict_invalid():
    """Test that invalid dict default raises TypeError."""

    with pytest.raises(TypeError, match="Invalid default value for field 'settings'"):
        class Config(modict):
            _config = modict.config(validate_default=True)
            settings: Dict[str, int] = "not a dict"


def test_validate_default_no_hint():
    """Test that fields without hints are skipped."""

    class Config(modict):
        _config = modict.config(validate_default=True)
        name = "Alice"  # No type hint

    # Should not raise (no hint to validate against)
    config = Config()
    assert config.name == "Alice"


def test_validate_default_no_default():
    """Test that fields without defaults are skipped."""

    class Config(modict):
        _config = modict.config(validate_default=True)
        name: str  # No default

    # Should not raise at class definition
    config = Config(name="Alice")
    assert config.name == "Alice"


def test_validate_default_with_computed():
    """Test that Computed defaults are skipped."""

    from modict import Computed

    class Config(modict):
        _config = modict.config(validate_default=True)
        name: str = Computed(lambda self: "Alice")

    # Should not raise (Computed is skipped)
    config = Config()
    assert config.name == "Alice"


def test_validate_default_with_factory():
    """Test that Factory defaults are skipped."""

    from modict import Factory

    class Config(modict):
        _config = modict.config(validate_default=True)
        numbers: List[int] = Factory(list)

    # Should not raise (Factory is skipped)
    config = Config()
    assert config.numbers == []


def test_validate_default_error_message():
    """Test that error message is informative."""

    with pytest.raises(TypeError) as exc_info:
        class Config(modict):
            _config = modict.config(validate_default=True)
            age: int = "wrong"

    error_msg = str(exc_info.value)
    assert "Invalid default value" in error_msg
    assert "field 'age'" in error_msg
    assert "expected" in error_msg
    assert "Set validate_default=False" in error_msg


def test_validate_default_inheritance():
    """Test validate_default with inheritance."""

    class Parent(modict):
        _config = modict.config(validate_default=True)
        name: str = "Alice"

    class Child(Parent):
        age: int = 25

    # Both defaults should be validated
    child = Child()
    assert child.name == "Alice"
    assert child.age == 25


def test_validate_default_inheritance_invalid():
    """Test that child invalid defaults are caught."""

    class Parent(modict):
        _config = modict.config(validate_default=True)
        name: str = "Alice"

    with pytest.raises(TypeError, match="Invalid default value for field 'age'"):
        class Child(Parent):
            age: int = "wrong"


def test_validate_default_with_nested_modict():
    """Test validate_default with nested modict types."""

    class Inner(modict):
        value: int = 10

    class Outer(modict):
        _config = modict.config(validate_default=True)
        inner: Inner = Inner()

    # Should validate that default is an instance of Inner
    outer = Outer()
    assert outer.inner.value == 10


def test_validate_default_multiple_fields():
    """Test validate_default with multiple fields."""

    class Config(modict):
        _config = modict.config(validate_default=True)
        name: str = "Alice"
        age: int = 25
        active: bool = True
        score: float = 9.5

    # All defaults valid
    config = Config()
    assert config.name == "Alice"
    assert config.age == 25
    assert config.active is True
    assert config.score == 9.5


def test_validate_default_combined_with_other_config():
    """Test validate_default combined with other config options."""

    class Config(modict):
        _config = modict.config(
            validate_default=True,
            extra='forbid',
            strict=True,
            frozen=True
        )
        name: str = "Alice"
        age: int = 25

    # Should work with all config options
    config = Config()
    assert config.name == "Alice"
    assert config.age == 25


def test_validate_default_disabled_allows_wrong_type():
    """Test that validate_default=False allows wrong types (default behavior)."""

    class Config(modict):
        # validate_default defaults to False
        name: str = 123

    # Should not raise at class definition
    config = Config()
    assert config.name == "123"  # Default is not validated at class definition; init validation coerces
