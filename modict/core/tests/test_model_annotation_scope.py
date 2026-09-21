import sys
from types import ModuleType

import pytest


@pytest.fixture
def models(monkeypatch):
    module = ModuleType("_modict_annotation_models")
    monkeypatch.setitem(sys.modules, module.__name__, module)
    exec('''from __future__ import annotations
from modict import modict

class Token:
    pass

class Record(modict):
    _config = modict.config(strict=True)
    token: Token | None = None
    children: tuple[Record, ...] = ()

class Coerced(modict):
    record: Record
''', module.__dict__)
    return module


def test_deferred_types_resolve_outside_the_declaration_module(models):
    token = models.Token()
    record = models.Record(token=token)
    assert record.token is token
    assert models.Record(children=(record,)).children[0] is record
    with pytest.raises(TypeError):
        models.Record(token=object())


def test_coercion_uses_the_same_declaration_namespace(models):
    assert isinstance(models.Coerced(record={}).record, models.Record)


def test_inherited_annotation_keeps_its_owner_namespace(models):
    class Child(models.Record):
        pass

    token = models.Token()
    assert Child(token=token).token is token
    with pytest.raises(TypeError):
        Child(token=object())
