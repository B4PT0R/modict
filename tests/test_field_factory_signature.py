import pytest

from modict import modict, MISSING


def test_modict_field_factory_does_not_expose_pydantic_bucket():
    with pytest.raises(TypeError):
        modict.field(default=MISSING, _pydantic={})

