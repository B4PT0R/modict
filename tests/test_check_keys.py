import pytest

from modict import modict


def test_check_keys_enforces_required_even_when_check_values_false():
    class Req(modict):
        _config = modict.config(check_values=False)
        x: int = modict.field(required=True)

    with pytest.raises(KeyError):
        Req({})


def test_check_keys_can_bypass_required():
    class ReqNoKeys(modict):
        _config = modict.config(check_values=False, check_keys=False)
        x: int = modict.field(required=True)

    m = ReqNoKeys({})
    assert "x" not in m


def test_check_keys_enforces_extra_policy_even_when_check_values_false():
    class ForbidExtra(modict):
        _config = modict.config(check_values=False, extra="forbid")
        a: int = 1

    with pytest.raises(KeyError):
        ForbidExtra({"a": 1, "oops": 2})


def test_check_keys_can_bypass_extra_policy():
    class ForbidExtraNoKeys(modict):
        _config = modict.config(check_values=False, check_keys=False, extra="forbid")
        a: int = 1

    m = ForbidExtraNoKeys({"a": 1, "oops": 2})
    assert m["oops"] == 2


def test_check_keys_bypasses_require_all_deletion_guards():
    class StrictKeys(modict):
        _config = modict.config(require_all=True)
        a: int = 1

    s = StrictKeys({})
    with pytest.raises(TypeError):
        del s["a"]

    class LooseKeys(modict):
        _config = modict.config(require_all=True, check_keys=False)
        a: int = 1

    m = LooseKeys({})
    del m["a"]
    assert "a" not in m


def test_check_keys_bypasses_computed_override_protection():
    m = modict({"a": 1, "b": 2})
    m["sum"] = modict.computed(lambda self: self.a + self.b)

    # Baseline: protected by default
    with pytest.raises(TypeError):
        m["sum"] = 123

    # With check_keys=False: protection is bypassed.
    m._config.check_keys = False
    m["sum"] = 123
    assert m["sum"] == 123


def test_frozen_is_never_bypassed_by_check_keys():
    class FrozenNoKeys(modict):
        _config = modict.config(frozen=True, check_keys=False)

    m = FrozenNoKeys({"a": 1})
    with pytest.raises(TypeError):
        m["a"] = 2
    with pytest.raises(TypeError):
        del m["a"]

