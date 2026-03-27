import modict as modict_pkg
from modict import MISSING


def test_missing_exported():
    assert MISSING is not None


def test_root_exports_stay_focused_on_convenience_api():
    assert hasattr(modict_pkg, "modict")
    assert hasattr(modict_pkg, "Path")
    assert hasattr(modict_pkg, "Query")
    assert hasattr(modict_pkg, "MISSING")
    assert hasattr(modict_pkg, "check_type")
    assert hasattr(modict_pkg, "coerce")

    assert not hasattr(modict_pkg, "PathNode")
    assert not hasattr(modict_pkg, "Field")
    assert not hasattr(modict_pkg, "Factory")
    assert not hasattr(modict_pkg, "Attribute")
    assert not hasattr(modict_pkg, "Computed")
    assert not hasattr(modict_pkg, "Validator")
    assert not hasattr(modict_pkg, "ModelValidator")
    assert not hasattr(modict_pkg, "modictConfig")
    assert not hasattr(modict_pkg, "TypeChecker")
    assert not hasattr(modict_pkg, "Coercer")
