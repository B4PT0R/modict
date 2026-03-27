"""Tests for native dict method compatibility on modict.

Covers every method in the dict interface, verifying:
- Correct return values and side effects
- Validation/coercion routes through __setitem__ where applicable
- Subclass identity is preserved (copy, fromkeys, |)
- Views (keys/values/items) reflect current state and read through __getitem__
"""
import copy
import pytest
from modict import modict, MISSING
from modict.model_api import Computed


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class Typed(modict):
    x: int
    y: int = 0

    _config = modict.config(validate_assignment=True)


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

class TestInit:
    def test_empty(self):
        assert modict() == {}

    def test_from_dict(self):
        assert modict({"a": 1}) == {"a": 1}

    def test_from_kwargs(self):
        assert modict(a=1, b=2) == {"a": 1, "b": 2}

    def test_from_iterable_of_pairs(self):
        assert modict([("a", 1), ("b", 2)]) == {"a": 1, "b": 2}

    def test_nested_dict_auto_converted(self):
        m = modict({"a": {"b": 1}})
        assert isinstance(m["a"], modict)

    def test_subclass_preserved_on_construction(self):
        t = Typed(x=1)
        assert isinstance(t, Typed)
        assert t.x == 1


# ---------------------------------------------------------------------------
# __setitem__ / __getitem__ / __delitem__
# ---------------------------------------------------------------------------

class TestItemAccess:
    def test_setitem_getitem(self):
        m = modict()
        m["a"] = 1
        assert m["a"] == 1

    def test_delitem(self):
        m = modict(a=1, b=2)
        del m["a"]
        assert "a" not in m
        assert m == {"b": 2}

    def test_delitem_missing_raises(self):
        m = modict(a=1)
        with pytest.raises(KeyError):
            del m["z"]

    def test_setitem_triggers_validation(self):
        t = Typed(x=1)
        t["x"] = "42"          # coerced to int
        assert t["x"] == 42
        assert type(t["x"]) is int

    def test_setitem_validation_rejects_bad_type(self):
        t = Typed(x=1)
        with pytest.raises(Exception):
            t["x"] = "not_a_number"


# ---------------------------------------------------------------------------
# __contains__ / __len__ / __iter__
# ---------------------------------------------------------------------------

class TestContainerProtocol:
    def test_contains(self):
        m = modict(a=1)
        assert "a" in m
        assert "z" not in m

    def test_len(self):
        m = modict(a=1, b=2, c=3)
        assert len(m) == 3

    def test_iter(self):
        m = modict(a=1, b=2)
        assert set(m) == {"a", "b"}

    def test_iter_order(self):
        m = modict()
        for k in ("c", "a", "b"):
            m[k] = k
        assert list(m) == ["c", "a", "b"]


# ---------------------------------------------------------------------------
# __eq__ / __ne__
# ---------------------------------------------------------------------------

class TestEquality:
    def test_eq_plain_dict(self):
        m = modict(a=1, b=2)
        assert m == {"a": 1, "b": 2}

    def test_ne(self):
        assert modict(a=1) != modict(a=2)

    def test_eq_ignores_subclass(self):
        # native dict __eq__: modict == dict with same content
        assert modict(a=1) == {"a": 1}

    def test_eq_different_keys(self):
        assert modict(a=1) != modict(b=1)


# ---------------------------------------------------------------------------
# __repr__
# ---------------------------------------------------------------------------

class TestRepr:
    def test_repr_contains_class_name(self):
        m = modict(a=1)
        assert "modict" in repr(m) or "{" in repr(m)

    def test_repr_roundtrip_keys(self):
        m = modict(a=1, b=2)
        r = repr(m)
        assert "'a'" in r and "'b'" in r

    def test_repr_marks_computed_with_current_value(self):
        m = modict(a=2)
        m["double"] = Computed(lambda m: m.a * 2)

        r = repr(m)

        assert "'double': Computed(4)" in r


# ---------------------------------------------------------------------------
# keys / values / items views
# ---------------------------------------------------------------------------

class TestViews:
    def test_keys(self):
        m = modict(a=1, b=2)
        assert set(m.keys()) == {"a", "b"}

    def test_values(self):
        m = modict(a=1, b=2)
        assert set(m.values()) == {1, 2}

    def test_items(self):
        m = modict(a=1, b=2)
        assert set(m.items()) == {("a", 1), ("b", 2)}

    def test_keys_len(self):
        m = modict(a=1, b=2, c=3)
        assert len(m.keys()) == 3

    def test_values_len(self):
        m = modict(a=1, b=2)
        assert len(m.values()) == 2

    def test_items_len(self):
        m = modict(a=1, b=2)
        assert len(m.items()) == 2

    def test_keys_contains(self):
        m = modict(a=1)
        assert "a" in m.keys()
        assert "z" not in m.keys()

    def test_values_contains(self):
        m = modict(a=1, b=2)
        assert 1 in m.values()
        assert 99 not in m.values()

    def test_items_contains(self):
        m = modict(a=1)
        assert ("a", 1) in m.items()

    def test_views_read_through_getitem(self):
        """Values view should evaluate computed fields."""
        m = modict(a=2)
        m["double"] = Computed(lambda m: m.a * 2)
        assert 4 in m.values()
        assert ("double", 4) in m.items()

    def test_views_reflect_mutations(self):
        m = modict(a=1)
        keys_view = m.keys()
        m["b"] = 2
        assert "b" in keys_view


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------

class TestGet:
    def test_get_existing(self):
        m = modict(a=1)
        assert m.get("a") == 1

    def test_get_missing_default_none(self):
        m = modict(a=1)
        assert m.get("z") is None

    def test_get_missing_custom_default(self):
        m = modict(a=1)
        assert m.get("z", 99) == 99

    def test_get_reads_through_getitem(self):
        """get() should evaluate computed fields."""
        m = modict(a=3)
        m["triple"] = Computed(lambda m: m.a * 3)
        assert m.get("triple") == 9


# ---------------------------------------------------------------------------
# pop
# ---------------------------------------------------------------------------

class TestPop:
    def test_pop_existing(self):
        m = modict(a=1, b=2)
        v = m.pop("a")
        assert v == 1
        assert "a" not in m

    def test_pop_missing_with_default(self):
        m = modict(a=1)
        assert m.pop("z", 99) == 99

    def test_pop_missing_no_default_raises(self):
        m = modict(a=1)
        with pytest.raises(KeyError):
            m.pop("z")


# ---------------------------------------------------------------------------
# popitem
# ---------------------------------------------------------------------------

class TestPopitem:
    def test_popitem_returns_last(self):
        m = modict(a=1, b=2, c=3)
        k, v = m.popitem()
        assert k == "c"
        assert v == 3
        assert "c" not in m

    def test_popitem_empty_raises(self):
        m = modict()
        with pytest.raises(KeyError):
            m.popitem()


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------

class TestUpdate:
    def test_update_from_dict(self):
        m = modict(a=1)
        m.update({"b": 2})
        assert m == {"a": 1, "b": 2}

    def test_update_from_kwargs(self):
        m = modict(a=1)
        m.update(b=2, c=3)
        assert m == {"a": 1, "b": 2, "c": 3}

    def test_update_from_iterable(self):
        m = modict(a=1)
        m.update([("b", 2), ("c", 3)])
        assert m == {"a": 1, "b": 2, "c": 3}

    def test_update_overwrites(self):
        m = modict(a=1, b=2)
        m.update({"b": 99})
        assert m["b"] == 99

    def test_update_routes_through_validation(self):
        t = Typed(x=1, y=0)
        t.update({"x": "5"})   # coerced to int
        assert t["x"] == 5
        assert type(t["x"]) is int

    def test_update_key_named_other(self):
        """'other' is positional-only, so it must be settable as a key via kwargs."""
        m = modict()
        m.update(other="value")
        assert m["other"] == "value"

    def test_update_no_args(self):
        m = modict(a=1)
        m.update()
        assert m == {"a": 1}


# ---------------------------------------------------------------------------
# setdefault
# ---------------------------------------------------------------------------

class TestSetdefault:
    def test_setdefault_missing_key(self):
        m = modict(a=1)
        v = m.setdefault("b", 99)
        assert v == 99
        assert m["b"] == 99

    def test_setdefault_existing_key(self):
        m = modict(a=1)
        v = m.setdefault("a", 99)
        assert v == 1
        assert m["a"] == 1

    def test_setdefault_default_is_none(self):
        m = modict()
        v = m.setdefault("x")
        assert v is None
        assert m["x"] is None

    def test_setdefault_returns_stored_coerced_value(self):
        class PartialTyped(modict):
            x: int
            z: int
            _config = modict.config(validate_assignment=True)

        m = PartialTyped(x=1)
        v = m.setdefault("z", "5")
        assert v == 5
        assert type(v) is int
        assert m["z"] == 5


# ---------------------------------------------------------------------------
# clear
# ---------------------------------------------------------------------------

class TestClear:
    def test_clear_empties(self):
        m = modict(a=1, b=2)
        m.clear()
        assert m == {}
        assert len(m) == 0

    def test_clear_plain_modict(self):
        m = modict(a=1)
        m.clear()
        assert len(m) == 0


# ---------------------------------------------------------------------------
# copy
# ---------------------------------------------------------------------------

class TestCopy:
    def test_copy_returns_same_type(self):
        t = Typed(x=1, y=2)
        c = t.copy()
        assert type(c) is Typed

    def test_copy_is_shallow(self):
        inner = modict(z=1)
        m = modict(a=inner)
        c = m.copy()
        assert c["a"] is m["a"]

    def test_copy_is_independent(self):
        m = modict(a=1)
        c = m.copy()
        c["b"] = 2
        assert "b" not in m

    def test_copy_plain_modict(self):
        m = modict(a=1, b=2)
        c = m.copy()
        assert c == m
        assert type(c) is modict

    def test_copy_preserves_computed_placeholders(self):
        class Calc(modict):
            a: int

            @modict.computed(cache=True, deps=["a"])
            def doubled(self):
                return self.a * 2

        m = Calc(a=2)
        c = m.copy()

        assert type(c) is Calc
        assert isinstance(dict.__getitem__(c, "doubled"), Computed)
        assert dict.__getitem__(c, "doubled") is not dict.__getitem__(m, "doubled")
        assert c["doubled"] == 4

    def test_copy_keeps_computed_protection_state_consistent_after_deletion(self):
        class Calc(modict):
            a: int

            @modict.computed(cache=True, deps=["a"])
            def doubled(self):
                return self.a * 2

        m = Calc(a=2)
        c = m.copy()

        c._config.override_computed = True
        del c["doubled"]
        c._config.override_computed = False

        c.clear()
        assert c == {}

    def test_copy_module_preserves_computed_placeholders(self):
        class Calc(modict):
            a: int

            @modict.computed(cache=True, deps=["a"])
            def doubled(self):
                return self.a * 2

        m = Calc(a=2)
        c = copy.copy(m)

        assert type(c) is Calc
        assert isinstance(dict.__getitem__(c, "doubled"), Computed)
        assert c["doubled"] == 4

    def test_copy_preserves_instance_config(self):
        m = modict(a=1)
        m._config.strict = True
        m._config.auto_convert = False

        c = m.copy()

        assert c._config is not m._config
        assert c._config.strict is True
        assert c._config.auto_convert is False


# ---------------------------------------------------------------------------
# fromkeys
# ---------------------------------------------------------------------------

class TestFromkeys:
    def test_fromkeys_default_none(self):
        m = modict.fromkeys(["a", "b", "c"])
        assert m == {"a": None, "b": None, "c": None}

    def test_fromkeys_custom_value(self):
        m = modict.fromkeys(["x", "y"], 0)
        assert m == {"x": 0, "y": 0}

    def test_fromkeys_returns_modict(self):
        m = modict.fromkeys(["a"])
        assert isinstance(m, modict)

    def test_fromkeys_subclass(self):
        t = Typed.fromkeys(["x"], 1)
        assert isinstance(t, Typed)


# ---------------------------------------------------------------------------
# | and |= operators
# ---------------------------------------------------------------------------

class TestMergeOperators:
    def test_or_returns_new_modict(self):
        m = modict(a=1)
        result = m | {"b": 2}
        assert result == {"a": 1, "b": 2}
        assert "b" not in m  # original unchanged

    def test_or_preserves_subclass(self):
        t = Typed(x=1, y=0)
        result = t | {"y": 5}
        assert isinstance(result, Typed)

    def test_ior_modifies_in_place(self):
        m = modict(a=1)
        m |= {"b": 2}
        assert m == {"a": 1, "b": 2}

    def test_ior_routes_through_validation(self):
        t = Typed(x=1, y=0)
        t |= {"x": "7"}
        assert t["x"] == 7
        assert type(t["x"]) is int

    def test_or_non_mapping_returns_not_implemented(self):
        m = modict(a=1)
        result = m.__or__(42)
        assert result is NotImplemented

    def test_or_on_frozen_instance_returns_new_value(self):
        class Frozen(modict):
            _config = modict.config(frozen=True)
            a: int = 1

        original = Frozen()
        merged = original | {"b": 2}

        assert isinstance(merged, Frozen)
        assert merged == {"a": 1, "b": 2}
        assert original == {"a": 1}
        with pytest.raises(TypeError, match="frozen"):
            merged["c"] = 3


# ---------------------------------------------------------------------------
# __reversed__
# ---------------------------------------------------------------------------

class TestReversed:
    def test_reversed(self):
        m = modict()
        for k in ("a", "b", "c"):
            m[k] = k
        assert list(reversed(m)) == ["c", "b", "a"]
