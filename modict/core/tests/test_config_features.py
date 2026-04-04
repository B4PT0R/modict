"""Tests for configuration features."""

import pytest
from ...core import modict


def test_frozen_immutability():
    """Test that frozen=True makes instances immutable."""

    class FrozenConfig(modict):
        _config = modict.config(frozen=True)
        name: str
        count: int = 0

    config = FrozenConfig(name="test", count=42)
    assert config.name == "test"
    assert config.count == 42

    with pytest.raises(TypeError, match="frozen"):
        config.name = "new name"

    with pytest.raises(TypeError, match="frozen"):
        config["name"] = "new name"

    with pytest.raises(TypeError, match="frozen"):
        config.new_field = "value"

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

    config.name = "new name"
    assert config.name == "new name"

    config["name"] = "another name"
    assert config["name"] == "another name"

    config.extra = "allowed"
    assert config.extra == "allowed"

    del config.extra
    assert "extra" not in config


def test_frozen_with_extra_modes():
    """Test frozen works with different extra modes."""

    class FrozenForbid(modict):
        _config = modict.config(frozen=True, extra='forbid')
        name: str

    config = FrozenForbid(name="test")

    with pytest.raises(TypeError, match="frozen"):
        config.name = "new"

    with pytest.raises(TypeError, match="frozen"):
        config.extra = "value"


def test_frozen_with_nested_modicts():
    """Test frozen on nested modict structures."""

    class FrozenParent(modict):
        _config = modict.config(frozen=True)
        name: str
        child: dict

    parent = FrozenParent(name="parent", child={"key": "value"})

    with pytest.raises(TypeError, match="frozen"):
        parent.name = "new"

    parent.child["key"] = "new value"
    assert parent.child["key"] == "new value"


def test_frozen_inheritance():
    """Test frozen inheritance."""

    class FrozenParent(modict):
        _config = modict.config(frozen=True)
        name: str

    class UnfrozenChild(FrozenParent):
        _config = modict.config(frozen=False)
        age: int

    child = UnfrozenChild(name="test", age=25)
    child.name = "new"
    assert child.name == "new"


def test_ignore_none_skips_init_and_assignment():
    class Config(modict):
        _config = modict.config(ignore_none=True)
        host: str = "localhost"
        port: int = 5432

    config = Config(host=None, port=1234)
    assert config.host == "localhost"
    assert config.port == 1234

    config["port"] = None
    assert config.port == 1234

    config.host = None
    assert config.host == "localhost"


def test_ignore_none_skips_update_and_merge_operator():
    class Config(modict):
        _config = modict.config(ignore_none=True)
        host: str = "localhost"
        port: int = 5432

    config = Config(host="db.internal", port=1234)
    config.update({"host": None, "port": 9999})
    assert config.host == "db.internal"
    assert config.port == 9999

    merged = config | {"host": None, "port": 7777}
    assert merged.host == "db.internal"
    assert merged.port == 7777


def test_ignore_none_setdefault_none_is_noop():
    class Config(modict):
        _config = modict.config(ignore_none=True)

    config = Config()
    assert config.setdefault("missing", None) is None
    assert "missing" not in config


def test_ignore_none_skips_default_none_for_effectively_optional_field():
    class Config(modict):
        _config = modict.config(ignore_none=True, require_all="never")
        host: str | None = None

    config = Config()
    assert "host" not in config


def test_ignore_none_keeps_default_none_for_effectively_required_field():
    class Config(modict):
        _config = modict.config(ignore_none=True, require_all="at_init")
        host: str | None = None

    config = Config()
    assert "host" in config
    assert config.host is None


def test_ignore_none_keeps_default_none_when_field_required_overrides_require_all():
    class Config(modict):
        _config = modict.config(ignore_none=True, require_all="never")
        host: str | None = modict.field(default=None, required="always")

    config = Config()
    assert "host" in config
    assert config.host is None
