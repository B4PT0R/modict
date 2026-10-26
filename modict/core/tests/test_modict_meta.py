"""Tests for modict metaclass utilities (config and views)."""

import pytest
import warnings
from ...core import modict
from ...core import modictConfig


def test_modictconfig_backward_compatibility():
    """Test that allow_extra parameter still works with deprecation warning."""
    # Test allow_extra=True → extra='allow'
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        config = modictConfig(allow_extra=True)
        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)
        assert "allow_extra" in str(w[0].message)
        assert config.extra == 'allow'

    # Test allow_extra=False → extra='forbid'
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        config = modictConfig(allow_extra=False)
        assert len(w) == 1
        assert config.extra == 'forbid'

    # Test that explicit extra parameter takes precedence
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        config = modictConfig(allow_extra=True, extra='ignore')
        assert len(w) == 1
        assert config.extra == 'ignore'  # extra wins


def test_modictconfig_copy_and_merge():
    base = modictConfig(strict=True, extra='forbid')
    copy_cfg = base.copy()

    assert copy_cfg.strict is True
    assert copy_cfg.extra == 'forbid'
    assert copy_cfg._explicit == base._explicit

    other = modictConfig(strict=False)
    merged = base.merge(other)

    # explicit fields from other override, rest from base
    assert merged.strict is False
    assert merged.extra == 'forbid'
    # _explicit union
    assert merged._explicit == base._explicit | other._explicit


def test_modictconfig_copy_and_merge_isolate_mutable_values():
    base = modictConfig(json_encoders={int: str})

    copy_cfg = base.copy()
    copy_cfg.json_encoders[float] = repr
    assert float not in base.json_encoders

    merged = base.merge(modictConfig(strict=True))
    merged.json_encoders[bytes] = bytes.hex
    assert bytes not in base.json_encoders


def test_instance_configs_do_not_share_mutable_fields():
    class WithEncoders(modict):
        _config = modict.config(json_encoders={int: str})

    left = WithEncoders()
    right = WithEncoders()

    assert left._config.json_encoders is not right._config.json_encoders

    left._config.json_encoders[float] = repr
    assert float not in right._config.json_encoders


def test_subclass_config_method_uses_subclass_config_as_base():
    class A(modict):
        _config = modict.config(strict=True, extra="forbid")

    class B(A):
        _config = A.config(extra="allow")

    assert A._config.strict is True
    assert A._config.extra == "forbid"
    assert B._config.strict is True
    assert B._config.extra == "allow"


def test_modict_views_reflect_mutations():
    m = modict(a=1, b=2)
    keys_view = m.keys()
    values_view = m.values()
    items_view = m.items()

    assert len(keys_view) == 2
    assert "a" in keys_view
    assert 2 in values_view
    assert ("a", 1) in items_view

    m["c"] = 3
    assert "c" in keys_view
    assert 3 in values_view
    assert ("c", 3) in items_view


def test_attr_declaration_bypasses_field_collection_and_is_inherited():
    class Base(modict):
        source = modict.attr("crm")
        label: str = modict.attr("customer")
        age: int = 1

    class Child(Base):
        region = modict.attr("eu")

    assert "source" not in Base.__fields__
    assert "label" not in Base.__fields__
    assert Base.__attributes__["source"] == "crm"
    assert Base.__attributes__["label"] == "customer"
    assert Base.source == "crm"
    assert Base.label == "customer"

    child = Child()
    assert child.source == "crm"
    assert child.label == "customer"
    assert child.region == "eu"
    assert "source" not in child
    assert "label" not in child
    assert "region" not in child


def test_attr_cannot_override_inherited_field():
    class Base(modict):
        age: int

    with pytest.raises(AttributeError, match="declared as a field"):
        Base(age=modict.attr("ignored"))

    base = Base(age=1)
    with pytest.raises(AttributeError, match="declared as a field"):
        base["age"] = modict.attr("nope")


@pytest.mark.parametrize("mode", ["before", "after"])
@pytest.mark.parametrize("parent_has_validator", [False, True])
def test_subclass_validators_do_not_leak_to_parent_or_siblings(mode, parent_has_validator):
    class Parent(modict):
        value: str

        if parent_has_validator:
            @modict.validator("value", mode=mode)
            def parent_value(self, value):
                return value + "P"

    existing = Parent(value="x")

    class Sibling(Parent):
        pass

    class Child(Parent):
        @modict.validator("value", mode=mode)
        def child_value(self, value):
            return value + "C"

    class Grandchild(Child):
        @modict.validator("value", mode=mode)
        def grandchild_value(self, value):
            return value + "G"

    class LaterSibling(Parent):
        @modict.validator("value", mode=mode)
        def sibling_value(self, value):
            return value + "S"

    prefix = "xP" if parent_has_validator else "x"
    for model, expected in (
        (Parent, prefix),
        (Sibling, prefix),
        (Child, prefix + "C"),
        (Grandchild, prefix + "CG"),
        (LaterSibling, prefix + "S"),
    ):
        instance = model(value="x")
        assert instance.value == expected
        instance.value = "y"
        assert instance.value == "y" + expected[1:]

    existing.value = "y"
    assert existing.value == "y" + prefix[1:]


def test_multiple_inheritance_owns_fields_and_keeps_leftmost_precedence():
    default = object()

    class Left(modict):
        value: str = modict.field(default=default, required="at_init")

        @modict.validator("value")
        def left_value(self, value):
            return value + "L"

    class Right(modict):
        value: str
        other: int = 1

        @modict.validator("value")
        def right_value(self, value):
            return value + "R"

    class Child(Left, Right):
        @modict.validator("value")
        def child_value(self, value):
            return value + "C"

    assert Child(value="x").value == "xLC"
    assert Left(value="x").value == "xL"
    assert Right(value="x").value == "xR"
    inherited = Child.__fields__["value"]
    original = Left.__fields__["value"]
    assert inherited is not original
    assert inherited.validators is not original.validators
    assert inherited.hint is original.hint
    assert inherited.default is default
    assert inherited.required == "at_init"
    assert Child.__fields__["other"] is not Right.__fields__["other"]
