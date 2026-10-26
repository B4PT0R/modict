"""Durable contract: explicit field requirements override model defaults."""

import pytest

from modict import MISSING, modict
from modict.model_api import Field


LEVELS = ("never", "at_init", "always")


@pytest.mark.parametrize("default", LEVELS)
@pytest.mark.parametrize("required", (MISSING, *LEVELS, True, False))
def test_field_requirement_overrides_default_for_presence_and_mutation(default, required):
    class Model(modict):
        _config = modict.config(default_required=default)
        value: int = modict.field(required=required)

    effective = default if required is MISSING else required
    if effective is True:
        effective = "always"
    elif effective is False:
        effective = "never"

    if effective == "never":
        assert Model() == {}
    else:
        with pytest.raises(KeyError, match="value"):
            Model()

    for operation in (lambda m: m.pop("value"), lambda m: m.__delitem__("value"), lambda m: m.clear()):
        model = Model(value=1)
        if effective == "always":
            with pytest.raises(TypeError):
                operation(model)
            assert model == {"value": 1}
        else:
            operation(model)
            assert model == {}
            if effective == "at_init":
                with pytest.raises(KeyError, match="value"):
                    model.validate()
            else:
                model.validate()


@pytest.mark.parametrize("declaration", (lambda: modict.field(), lambda: Field(), lambda: modict.field(required=MISSING)))
def test_unspecified_field_requirement_inherits_default(declaration):
    class Model(modict):
        _config = modict.config(default_required="always")
        value: int = declaration()

    with pytest.raises(KeyError, match="value"):
        Model()
    with pytest.raises(TypeError):
        Model(value=1).pop("value")


def test_config_inheritance_keeps_unspecified_and_explicit_fields_distinct():
    class Base(modict):
        inherited: int
        optional: int = modict.field(required="never")
        mandatory: int = modict.field(required="always")

    class Child(Base):
        _config = modict.config(default_required="never")

    assert Child(mandatory=1) == {"mandatory": 1}
    with pytest.raises(KeyError, match="inherited"):
        Base(mandatory=1)
    with pytest.raises(TypeError):
        Child(mandatory=1).pop("mandatory")

    class Override(Base):
        mandatory: int = modict.field(required="never")

    assert Override(inherited=1) == {"inherited": 1}


@pytest.mark.parametrize("default", LEVELS)
@pytest.mark.parametrize("required", (MISSING, *LEVELS))
def test_ignore_none_defaults_follow_effective_requirement(default, required):
    class Model(modict):
        _config = modict.config(default_required=default, ignore_none=True)
        value: int | None = modict.field(default=None, required=required)

    effective = default if required is MISSING else required
    assert Model() == ({} if effective == "never" else {"value": None})


@pytest.mark.parametrize("local", (MISSING, *LEVELS))
@pytest.mark.parametrize("inherited", (MISSING, *LEVELS))
def test_field_merge_prefers_explicit_local_requirement(local, inherited):
    merged = Field(required=local).merge(Field(required=inherited))
    assert merged.required == (inherited if local is MISSING else local)


def test_old_config_option_is_rejected():
    with pytest.raises(TypeError, match="require_all"):
        modict.config(require_all="always")


@pytest.mark.parametrize("default, normalized", ((True, "always"), (False, "never")))
def test_boolean_model_defaults_keep_their_meaning(default, normalized):
    class Model(modict):
        _config = modict.config(default_required=default)
        value: int
        optional: int = modict.field(required="never")

    assert Model._config.default_required == normalized
    if default:
        with pytest.raises(KeyError, match="value"):
            Model()
        with pytest.raises(TypeError):
            Model(value=1).pop("value")
    else:
        assert Model() == {}
