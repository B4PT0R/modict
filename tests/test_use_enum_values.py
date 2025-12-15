"""Tests for use_enum_values configuration feature."""

import pytest
import sys
from enum import Enum, IntEnum
from modict import modict

# StrEnum is only available in Python 3.11+
if sys.version_info >= (3, 11):
    from enum import StrEnum
else:
    # Fallback for Python 3.10
    class StrEnum(str, Enum):
        pass


class Color(Enum):
    RED = "red"
    GREEN = "green"
    BLUE = "blue"


class Priority(IntEnum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3


class Status(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    DONE = "done"


def test_use_enum_values_enabled():
    """Test that enum values are extracted when use_enum_values=True."""

    class Config(modict):
        _config = modict.config(use_enum_values=True)
        color: str
        priority: int

    config = Config(color=Color.RED, priority=Priority.HIGH)

    # Values should be extracted from enums
    assert config.color == "red"
    assert config.priority == 3
    assert not isinstance(config.color, Color)
    assert not isinstance(config.priority, Priority)


def test_use_enum_values_disabled():
    """Test that enum instances are preserved when use_enum_values=False."""

    class Config(modict):
        _config = modict.config(use_enum_values=False)
        color: Color
        priority: Priority

    config = Config(color=Color.GREEN, priority=Priority.MEDIUM)

    # Enum instances should be preserved
    assert config.color == Color.GREEN
    assert config.priority == Priority.MEDIUM
    assert isinstance(config.color, Color)
    assert isinstance(config.priority, Priority)


def test_use_enum_values_default():
    """Test that use_enum_values defaults to False."""

    class Config(modict):
        color: Color

    config = Config(color=Color.BLUE)

    # Should preserve enum by default
    assert config.color == Color.BLUE
    assert isinstance(config.color, Color)


def test_use_enum_values_with_str_enum():
    """Test use_enum_values with StrEnum."""

    class Config(modict):
        _config = modict.config(use_enum_values=True)
        status: str

    config = Config(status=Status.ACTIVE)

    assert config.status == "active"
    assert not isinstance(config.status, Status)


def test_use_enum_values_assignment():
    """Test that enum values are extracted on assignment."""

    class Config(modict):
        _config = modict.config(use_enum_values=True, validate_assignment=True)
        color: str

    config = Config(color="initial")
    config.color = Color.RED

    assert config.color == "red"
    assert not isinstance(config.color, Color)


def test_use_enum_values_with_coercion():
    """Test use_enum_values works with type coercion."""

    class Config(modict):
        _config = modict.config(use_enum_values=True, strict=False)
        priority: str  # Will coerce int to str

    config = Config(priority=Priority.HIGH)

    # Should extract value (3) then coerce to "3"
    assert config.priority == "3"
    assert isinstance(config.priority, str)


def test_use_enum_values_with_string_transformations():
    """Test use_enum_values with string transformations."""

    class Config(modict):
        _config = modict.config(
            use_enum_values=True,
            str_to_upper=True
        )
        color: str

    config = Config(color=Color.RED)

    # Should extract "red" then uppercase to "RED"
    assert config.color == "RED"


def test_use_enum_values_non_enum_unchanged():
    """Test that non-enum values are unchanged."""

    class Config(modict):
        _config = modict.config(use_enum_values=True)
        color: str
        count: int

    config = Config(color="plain string", count=42)

    # Non-enum values should pass through unchanged
    assert config.color == "plain string"
    assert config.count == 42


def test_use_enum_values_mixed():
    """Test mixing enum and non-enum values."""

    class Config(modict):
        _config = modict.config(use_enum_values=True)
        color: str
        status: str
        count: int

    config = Config(
        color=Color.RED,
        status="custom",
        count=42
    )

    assert config.color == "red"
    assert config.status == "custom"
    assert config.count == 42


def test_use_enum_values_with_nested():
    """Test use_enum_values with nested structures."""

    class Inner(modict):
        _config = modict.config(use_enum_values=True)
        color: str

    class Outer(modict):
        _config = modict.config(use_enum_values=True)
        priority: int
        inner: Inner

    inner = Inner(color=Color.BLUE)
    outer = Outer(priority=Priority.LOW, inner=inner)

    assert outer.priority == 1
    assert outer.inner.color == "blue"


def test_use_enum_values_in_dict():
    """Test use_enum_values with dict values."""

    class Config(modict):
        _config = modict.config(use_enum_values=True)
        settings: dict

    config = Config(settings={"color": Color.RED, "priority": Priority.HIGH})

    # Note: Nested dict values are not automatically processed
    # Only direct field assignments go through _check_value
    assert config.settings["color"] == Color.RED  # Still enum


def test_use_enum_values_with_extra_allow():
    """Test use_enum_values with extra='allow'."""

    class Config(modict):
        _config = modict.config(use_enum_values=True, extra='allow')
        color: str

    config = Config(color=Color.RED)
    config.extra_field = Priority.HIGH

    assert config.color == "red"
    assert config.extra_field == 3


def test_use_enum_values_with_extra_forbid():
    """Test use_enum_values with extra='forbid'."""

    class Config(modict):
        _config = modict.config(use_enum_values=True, extra='forbid')
        color: str

    config = Config(color=Color.RED)

    assert config.color == "red"

    with pytest.raises(KeyError):
        config.extra_field = Priority.HIGH


def test_use_enum_values_with_frozen():
    """Test use_enum_values with frozen=True."""

    class Config(modict):
        _config = modict.config(use_enum_values=True, frozen=True)
        color: str

    config = Config(color=Color.RED)

    assert config.color == "red"

    with pytest.raises(TypeError, match="frozen"):
        config.color = Color.BLUE
