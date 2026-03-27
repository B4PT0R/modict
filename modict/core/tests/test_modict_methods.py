"""Tests for modict-specific methods: nested ops, attribute access,
deepcopy, rename/exclude/extract, JSON helpers, walk/walked/unwalk.
"""
import copy
import json
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
# Attribute access  (__getattr__ / __setattr__ / __delattr__)
# ---------------------------------------------------------------------------

class TestAttributeAccess:
    def test_getattr_reads_key(self):
        m = modict(a=1)
        assert m.a == 1

    def test_setattr_writes_key(self):
        m = modict()
        m.a = 42
        assert m["a"] == 42

    def test_setattr_cannot_shadow_method_name(self):
        m = modict()
        with pytest.raises(AttributeError, match="Use item assignment instead"):
            m.copy = 42
        m["copy"] = 42
        assert m["copy"] == 42
        assert callable(m.copy)

    def test_delattr_removes_key(self):
        m = modict(a=1, b=2)
        del m.a
        assert "a" not in m

    def test_delattr_missing_raises_attribute_error(self):
        m = modict(a=1)
        with pytest.raises(AttributeError):
            del m.z

    def test_method_not_shadowed_by_key(self):
        """A key named 'get' should not shadow the method via attribute access."""
        m = modict()
        m["get"] = "value"
        # m.get should still be the method
        assert callable(m.get)
        # but item access works
        assert m["get"] == "value"

    def test_setattr_routes_through_validation(self):
        t = Typed(x=1)
        t.x = "5"        # coerced to int
        assert t["x"] == 5
        assert type(t["x"]) is int

    def test_getattr_missing_raises_attribute_error(self):
        m = modict(a=1)
        with pytest.raises(AttributeError):
            _ = m.nonexistent


# ---------------------------------------------------------------------------
# get_nested / set_nested / has_nested / del_nested / pop_nested
# ---------------------------------------------------------------------------

class TestNestedOps:
    def setup_method(self):
        self.m = modict({
            "users": [
                {"name": "Alice", "age": 30},
                {"name": "Bob",   "age": 25},
            ],
            "config": {"debug": True, "timeout": 10},
        })

    def test_get_nested_jsonpath(self):
        assert self.m.get_nested("$.users[0].name") == "Alice"

    def test_get_nested_tuple(self):
        assert self.m.get_nested(("users", 1, "age")) == 25

    def test_get_nested_missing_with_default(self):
        assert self.m.get_nested("$.users[0].email", default=None) is None

    def test_get_nested_missing_no_default_raises(self):
        with pytest.raises((KeyError, Exception)):
            self.m.get_nested("$.users[0].email")

    def test_set_nested_existing(self):
        self.m.set_nested("$.config.debug", False)
        assert self.m.get_nested("$.config.debug") is False

    def test_set_nested_missing_intermediate_raises_by_default(self):
        with pytest.raises(KeyError, match="Missing intermediate container"):
            self.m.set_nested("$.meta.version", "1.0")

    def test_set_nested_creates_intermediate_with_factory(self):
        self.m.set_nested(
            "$.meta.version",
            "1.0",
            create_missing=True,
            container_factory=lambda path: {},
        )
        assert self.m.get_nested("$.meta.version") == "1.0"

    def test_has_nested_true(self):
        assert self.m.has_nested("$.users[0].name") is True

    def test_has_nested_false(self):
        assert self.m.has_nested("$.users[0].email") is False

    def test_del_nested(self):
        self.m.del_nested("$.config.debug")
        assert not self.m.has_nested("$.config.debug")
        assert self.m.has_nested("$.config.timeout")

    def test_pop_nested_returns_value(self):
        v = self.m.pop_nested("$.config.timeout")
        assert v == 10
        assert not self.m.has_nested("$.config.timeout")

    def test_pop_nested_missing_with_default(self):
        assert self.m.pop_nested("$.config.missing", default=99) == 99

    def test_pop_nested_missing_no_default_raises(self):
        with pytest.raises((KeyError, Exception)):
            self.m.pop_nested("$.config.missing")


# ---------------------------------------------------------------------------
# translate / exclude / extract
# ---------------------------------------------------------------------------

class TestTranslateExcludeExtract:
    def test_translate_kwargs(self):
        m = modict(a=1, b=2, c=3)
        translated = m.translate(a="x", b="y")
        assert translated == {"x": 1, "y": 2, "c": 3}
        assert m == {"a": 1, "b": 2, "c": 3}

    def test_translate_dict_arg(self):
        m = modict(a=1, b=2)
        translated = m.translate({"a": "alpha"})
        assert translated == {"alpha": 1, "b": 2}
        assert m == {"a": 1, "b": 2}

    def test_translate_preserves_order(self):
        m = modict(a=1, b=2, c=3)
        translated = m.translate(b="B")
        assert list(translated.keys()) == ["a", "B", "c"]

    def test_translate_preserves_raw_values(self):
        """translate() must not evaluate computed fields."""
        m = modict(a=1)
        m["double"] = Computed(lambda m: m.a * 2)
        translated = m.translate(double="twice")
        # 'twice' should still be the Computed object, not the evaluated result
        assert isinstance(dict.__getitem__(translated, "twice"), Computed)
        assert "double" in m
        assert "twice" not in m

    def test_translate_returns_plain_modict_for_typed_model(self):
        typed = Typed(x=1, y=2)
        translated = typed.translate(x="X")

        assert type(translated) is modict
        assert translated == {"X": 1, "y": 2}

    def test_exclude_returns_plain_modict(self):
        m = modict(a=1, b=2, c=3)
        result = m.exclude("b")
        assert isinstance(result, modict)
        assert result == {"a": 1, "c": 3}

    def test_exclude_multiple(self):
        m = modict(a=1, b=2, c=3, d=4)
        assert m.exclude("b", "d") == {"a": 1, "c": 3}

    def test_exclude_nonexistent_key_ignored(self):
        m = modict(a=1, b=2)
        assert m.exclude("z") == {"a": 1, "b": 2}

    def test_extract_returns_plain_modict(self):
        m = modict(a=1, b=2, c=3)
        result = m.extract("a", "c")
        assert isinstance(result, modict)
        assert result == {"a": 1, "c": 3}

    def test_extract_single(self):
        m = modict(a=1, b=2, c=3)
        assert m.extract("b") == {"b": 2}

    def test_exclude_does_not_modify_original(self):
        m = modict(a=1, b=2)
        m.exclude("a")
        assert "a" in m

    def test_extract_does_not_modify_original(self):
        m = modict(a=1, b=2)
        m.extract("a")
        assert "b" in m


# ---------------------------------------------------------------------------
# deepcopy
# ---------------------------------------------------------------------------

class TestDeepcopy:
    def test_deepcopy_returns_same_type(self):
        t = Typed(x=1, y=2)
        c = t.deepcopy()
        assert type(c) is Typed

    def test_deepcopy_is_independent(self):
        m = modict(a=modict(b=1))
        c = m.deepcopy()
        c["a"]["b"] = 99
        assert m["a"]["b"] == 1   # original unchanged

    def test_deepcopy_plain_modict(self):
        m = modict(a=1, b=[1, 2, 3])
        c = m.deepcopy()
        c["b"].append(4)
        assert len(m["b"]) == 3

    def test_deepcopy_preserves_computed_placeholders(self):
        class Calc(modict):
            a: int

            @modict.computed(cache=True, deps=["a"])
            def doubled(self):
                return self.a * 2

        m = Calc(a=2)
        c = m.deepcopy()

        assert type(c) is Calc
        assert isinstance(dict.__getitem__(c, "doubled"), Computed)
        assert dict.__getitem__(c, "doubled") is not dict.__getitem__(m, "doubled")
        assert c["doubled"] == 4

    def test_copy_deepcopy_preserves_self_reference(self):
        m = modict()
        m["self"] = m

        c = copy.deepcopy(m)

        assert c is not m
        assert c["self"] is c

    def test_deepcopy_preserves_shared_alias_topology(self):
        shared = modict(value=1)
        m = modict(left=shared, right=shared)

        c = m.deepcopy()

        assert c is not m
        assert c["left"] is c["right"]
        assert c["left"] is not shared
        c["left"]["value"] = 2
        assert m["left"]["value"] == 1

    def test_deepcopy_preserves_instance_config(self):
        m = modict(a=1)
        m._config.strict = True
        m._config.auto_convert = False

        c = m.deepcopy()

        assert c._config is not m._config
        assert c._config.strict is True
        assert c._config.auto_convert is False


# ---------------------------------------------------------------------------
# walk / walked / unwalk
# ---------------------------------------------------------------------------

class TestWalkWalkedUnwalk:
    def test_walk_yields_leaf_pairs(self):
        m = modict(a=1, b=modict(c=2, d=3))
        pairs = list(m.walk())
        values = {v for _, v in pairs}
        assert values == {1, 2, 3}

    def test_walked_returns_dict(self):
        m = modict(a=1, b=2)
        result = m.walked()
        assert isinstance(result, dict)
        values = set(result.values())
        assert values == {1, 2}

    def test_walk_with_callback(self):
        m = modict(a=1, b=2)
        pairs = list(m.walk(callback=lambda v: v * 10))
        values = {v for _, v in pairs}
        assert values == {10, 20}

    def test_walk_with_filter(self):
        m = modict(a=1, b=2, c=3)
        pairs = list(m.walk(filter=lambda p, v: v > 1))
        values = {v for _, v in pairs}
        assert values == {2, 3}

    def test_unwalk_roundtrip(self):
        m = modict(a=modict(b=1), c=2)
        snapshot = m.walked()
        restored = modict.unwalk(snapshot)
        assert restored["a"]["b"] == 1
        assert restored["c"] == 2

    def test_unwalk_ignore_types_avoids_subclass_defaults(self):
        """ignore_types=True prevents reconstructing modict subclasses with defaults,
        so merging the result won't re-inject default field values."""
        class Config(modict):
            debug: bool = True

        c = Config(debug=False)
        snapshot = c.walked()
        # Without ignore_types, unwalk would reconstruct a Config — injecting debug=True default
        restored = modict.unwalk(snapshot, ignore_types=True)
        # With ignore_types=True, the result is a plain modict (not Config) — no defaults injected
        assert isinstance(restored, modict)
        assert type(restored) is modict  # not Config
        assert restored["debug"] is False


# ---------------------------------------------------------------------------
# dumps / dump / loads / load
# ---------------------------------------------------------------------------

class TestJsonMethods:
    def test_dumps_basic(self):
        m = modict(a=1, b="hello")
        s = m.dumps()
        assert json.loads(s) == {"a": 1, "b": "hello"}

    def test_dumps_indent(self):
        m = modict(a=1)
        s = m.dumps(indent=2)
        assert "\n" in s

    def test_dumps_sort_keys(self):
        m = modict(b=2, a=1)
        s = m.dumps(sort_keys=True)
        assert s.index('"a"') < s.index('"b"')

    def test_dumps_exclude_none(self):
        m = modict(a=1, b=None, c=3)
        s = m.dumps(exclude_none=True)
        data = json.loads(s)
        assert "b" not in data
        assert data == {"a": 1, "c": 3}

    def test_dumps_custom_encoders(self):
        from datetime import date
        m = modict(d=date(2024, 1, 1))
        s = m.dumps(encoders={date: lambda d: d.isoformat()})
        assert json.loads(s) == {"d": "2024-01-01"}

    def test_loads_returns_modict(self):
        m = modict.loads('{"a": 1, "b": 2}')
        assert isinstance(m, modict)
        assert m == {"a": 1, "b": 2}

    def test_loads_subclass(self):
        t = Typed.loads('{"x": 1}')
        assert isinstance(t, Typed)
        assert t.x == 1

    def test_loads_invalid_json_raises(self):
        with pytest.raises(json.JSONDecodeError):
            modict.loads("not json")

    def test_dump_load_file_roundtrip(self, tmp_path):
        m = modict(a=1, b=[1, 2, 3])
        path = tmp_path / "test.json"
        m.dump(path)
        loaded = modict.load(path)
        assert loaded == m
        assert isinstance(loaded, modict)

    def test_dump_load_fileobj_roundtrip(self, tmp_path):
        m = modict(x=42)
        path = tmp_path / "test2.json"
        with open(path, "w") as f:
            m.dump(f)
        with open(path) as f:
            loaded = modict.load(f)
        assert loaded == m


# ---------------------------------------------------------------------------
# convert / unconvert / to_dict / to_modict
# ---------------------------------------------------------------------------

class TestConversion:
    def test_to_dict_flattens_nested(self):
        m = modict(a=modict(b=1))
        d = m.to_dict()
        assert not isinstance(d["a"], modict)
        assert d["a"]["b"] == 1

    def test_to_dict_mutates_nested_containers_in_place(self):
        child = modict(b=1)
        nested_list = [child]
        m = modict(a=nested_list)

        d = m.to_dict()

        assert d == {"a": [{"b": 1}]}
        assert d["a"] is nested_list
        assert nested_list[0] is not child
        assert isinstance(nested_list[0], dict)
        assert not isinstance(nested_list[0], modict)

    def test_to_modict_converts_nested(self):
        m = modict.__new__(modict)
        dict.__init__(m)
        dict.__setitem__(m, "a", {"b": 1})  # raw nested dict
        m.to_modict()
        assert isinstance(m["a"], modict)

    def test_to_modict_mutates_nested_containers_in_place(self):
        child = {"b": 1}
        nested_list = [child]
        m = modict.__new__(modict)
        dict.__init__(m)
        dict.__setitem__(m, "a", nested_list)

        converted = m.to_modict()

        assert converted is m
        assert dict.__getitem__(m, "a") is nested_list
        assert nested_list[0] is not child
        assert isinstance(nested_list[0], modict)

    def test_convert_classmethod(self):
        d = {"a": {"b": 1}, "c": [{"d": 2}]}
        m = modict.convert(d)
        assert isinstance(m, modict)
        assert isinstance(m["a"], modict)
        assert isinstance(m["c"][0], modict)

    def test_convert_mutates_nested_containers_in_place(self):
        child = {"b": 1}
        nested_list = [child]
        data = {"a": nested_list}

        m = modict.convert(data)

        assert isinstance(m, modict)
        assert m["a"] is nested_list
        assert nested_list[0] is not child
        assert isinstance(nested_list[0], modict)

    def test_convert_preserves_shared_references_and_cycles(self):
        shared = {"value": 1}
        data = {"left": shared, "right": shared}
        data["self"] = data

        converted = modict.convert(data)

        assert isinstance(converted, modict)
        assert converted["left"] is converted["right"]
        assert converted["self"] is converted
        assert isinstance(converted["left"], modict)

    def test_unconvert_classmethod(self):
        m = modict(a=modict(b=1))
        d = modict.unconvert(m)
        assert not isinstance(d, modict)
        assert not isinstance(d["a"], modict)

    def test_unconvert_mutates_nested_containers_in_place(self):
        child = modict(b=1)
        nested_list = [child]
        m = modict(a=nested_list)

        d = modict.unconvert(m)

        assert d == {"a": [{"b": 1}]}
        assert d["a"] is nested_list
        assert nested_list[0] is not child
        assert isinstance(nested_list[0], dict)
        assert not isinstance(nested_list[0], modict)

    def test_unconvert_preserves_shared_references_and_cycles(self):
        shared = modict(value=1)
        m = modict(left=shared, right=shared)
        m["self"] = m

        plain = modict.unconvert(m)

        assert isinstance(plain, dict)
        assert plain["left"] is plain["right"]
        assert plain["self"] is plain
        assert isinstance(plain["left"], dict)
        assert not isinstance(plain["left"], modict)
