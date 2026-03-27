from __future__ import annotations

from typing import Any

import pytest

from modict.model_api import (
    Field,
    build_fields_and_model_validators,
    check_json_serializable,
    get_annotations,
    is_field,
    is_locally_defined_class,
    is_locally_defined_descriptor,
    maybe_coerce,
)


def test_maybe_coerce_handles_none_and_failed_coercions():
    assert maybe_coerce("1", int) == 1
    assert maybe_coerce("abc", int) == "abc"
    sentinel = object()
    assert maybe_coerce(sentinel, None) is sentinel


def test_check_json_serializable_accepts_custom_encoders_and_rejects_bad_values():
    class Custom:
        pass

    check_json_serializable(Custom(), key="payload", allow_nan=True, encoders={Custom: lambda value: "ok"})

    with pytest.raises(ValueError, match="payload"):
        check_json_serializable(Custom(), key="payload", allow_nan=True)

    with pytest.raises(ValueError, match="score"):
        check_json_serializable(float("nan"), key="score", allow_nan=False)


def test_get_annotations_supports_annotations_and_annotate_func():
    assert get_annotations({"__annotations__": {"x": int}}, "Sample", ()) == {"x": int}

    def annotate_func(version: int = 1) -> dict[str, Any]:
        return {"y": str}

    assert get_annotations({"__annotate_func__": annotate_func}, "Sample", ()) == {"y": str}


def test_get_annotations_returns_empty_dict_when_annotate_func_fails():
    def broken(*args, **kwargs):
        raise RuntimeError("boom")

    assert get_annotations({"__annotate_func__": broken}, "Sample", ()) == {}


def test_local_class_and_descriptor_detection_helpers():
    inner = type("Inner", (), {"__module__": __name__})
    inner.__qualname__ = "Sample.Inner"

    def title(self) -> str:
        return "ok"

    def helper() -> int:
        return 1

    title.__module__ = __name__
    title.__qualname__ = "Sample.title"
    helper.__module__ = __name__
    helper.__qualname__ = "Sample.helper"

    dct = {
        "__module__": __name__,
        "title": property(title),
        "helper": staticmethod(helper),
    }

    assert is_locally_defined_class("Inner", inner, "Sample", dct) is True
    assert is_locally_defined_descriptor("title", dct["title"], "Sample", dct) is True
    assert is_locally_defined_descriptor("helper", dct["helper"], "Sample", dct) is True


def test_is_field_excludes_local_classes_descriptors_and_base_attributes():
    class Base:
        inherited = 1

    inner = type("Inner", (), {"__module__": __name__})
    inner.__qualname__ = "Sample.Inner"

    def title(self) -> str:
        return "ok"

    title.__module__ = __name__
    title.__qualname__ = "Sample.title"

    dct = {
        "__module__": __name__,
        "title": property(title),
    }

    assert is_field("plain", 1, "Sample", (), {"__module__": __name__}) is True
    assert is_field("Inner", inner, "Sample", (), dct) is False
    assert is_field("title", dct["title"], "Sample", (), dct) is False
    assert is_field("inherited", 2, "Child", (Base,), {"__module__": __name__}) is False


def test_build_fields_and_model_validators_collects_computed_and_validators():
    def total(self) -> int:
        return self["count"] + 1

    total._is_computed = True
    total._computed_cache = True
    total._computed_deps = ["count"]

    def validate_name(self, value):
        return str(value).strip()

    validate_name._is_validator = True
    validate_name._validator_field = "name"
    validate_name._validator_mode = "after"

    def normalize(self, values):
        values["ready"] = True
        return values

    normalize._is_model_validator = True
    normalize._model_validator_mode = "before"

    dct = {
        "__module__": __name__,
        "__annotations__": {"count": int, "total": int},
        "count": Field(default=0),
        "total": total,
        "validate_name": validate_name,
        "normalize": normalize,
        "plain": "value",
    }

    fields, model_validators, attributes = build_fields_and_model_validators("Demo", (), dct)

    assert fields["count"].hint is int
    assert fields["plain"].default == "value"
    assert fields["total"].hint is int
    assert fields["total"].default.cache is True
    assert fields["name"].validators[0].mode == "after"
    assert attributes == {}
    assert model_validators[0].mode == "before"
    assert "total" not in dct
    assert "validate_name" not in dct
    assert "normalize" not in dct
