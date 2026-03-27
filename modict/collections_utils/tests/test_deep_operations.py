"""Test suite for deep operations in collections_utils: merge, diff, deep_equals, unwalk."""

from __future__ import annotations

import pytest

from modict.collections_utils import deep_merge, diff_nested, deep_equals, MISSING, Path, unwalk


class TestDeepMerge:
    def test_simple_merge_dict(self):
        target = {"a": 1, "b": 2}
        src = {"b": 3, "c": 4}
        deep_merge(target, src)
        assert target == {"a": 1, "b": 3, "c": 4}

    def test_nested_merge_dict(self):
        target = {"a": 1, "b": {"x": 10, "y": 20}}
        src = {"b": {"y": 30, "z": 40}, "c": 3}
        deep_merge(target, src)
        assert target == {"a": 1, "b": {"x": 10, "y": 30, "z": 40}, "c": 3}

    def test_merge_list(self):
        target = [1, 2, 3]
        src = [10, 20]
        deep_merge(target, src)
        assert target == [10, 20, 3]

    def test_merge_list_append(self):
        target = [1, 2]
        src = [10, 20, 30, 40]
        deep_merge(target, src)
        assert target == [10, 20, 30, 40]

    def test_merge_nested_list_dict(self):
        target = {"items": [{"a": 1}, {"b": 2}]}
        src = {"items": [{"a": 10}, {"b": 20, "c": 30}]}
        deep_merge(target, src)
        assert target == {"items": [{"a": 10}, {"b": 20, "c": 30}]}

    def test_merge_list_rejects_text_like_sequences(self):
        for src in ("ab", b"ab", bytearray(b"ab")):
            target = [1, 2, 3]
            with pytest.raises(TypeError):
                deep_merge(target, src)


class TestDeepMergeWithMISSING:
    def test_delete_key_with_missing(self):
        target = {"a": 1, "b": 2, "c": 3}
        src = {"b": MISSING, "d": 4}
        deep_merge(target, src)
        assert target == {"a": 1, "c": 3, "d": 4}
        assert "b" not in target

    def test_delete_nested_key_with_missing(self):
        target = {"a": 1, "b": {"x": 10, "y": 20, "z": 30}}
        src = {"b": {"y": MISSING}}
        deep_merge(target, src)
        assert target == {"a": 1, "b": {"x": 10, "z": 30}}
        assert "y" not in target["b"]

    def test_delete_from_list_with_missing(self):
        target = [1, 2, 3, 4, 5]
        src = [MISSING, 10, MISSING]
        deep_merge(target, src)
        assert target == [10, 4, 5]


class TestDiffNested:
    def test_diff_identical_dicts(self):
        dict1 = {"a": 1, "b": 2}
        dict2 = {"a": 1, "b": 2}
        diffs = diff_nested(dict1, dict2)
        assert diffs == {}

    def test_diff_simple_change(self):
        dict1 = {"a": 1, "b": 2}
        dict2 = {"a": 1, "b": 3}
        diffs = diff_nested(dict1, dict2)
        assert len(diffs) == 1
        assert Path("$.b") in diffs
        assert diffs[Path("$.b")] == (2, 3)

    def test_diff_added_and_removed_key(self):
        dict1 = {"a": 1, "b": 2}
        dict2 = {"a": 1, "c": 3}
        diffs = diff_nested(dict1, dict2)
        assert Path("$.b") in diffs
        assert Path("$.c") in diffs


class TestDeepEquals:
    def test_deep_equals_identical(self):
        dict1 = {"a": [1, 2, {"b": 3}], "c": 4}
        dict2 = {"a": [1, 2, {"b": 3}], "c": 4}
        assert deep_equals(dict1, dict2)

    def test_deep_equals_different(self):
        dict1 = {"a": [1, 2, {"b": 3}]}
        dict2 = {"a": [1, 2, {"b": 4}]}
        assert not deep_equals(dict1, dict2)


class TestUnwalkIgnoreTypes:
    def test_unwalk_with_ignore_types(self):
        walked = {
            Path("$.x"): 1,
            Path("$.y.z"): 2,
        }

        result_with_types = unwalk(walked, ignore_types=False)
        assert "x" in result_with_types

        result_without_types = unwalk(walked, ignore_types=True)
        assert "x" in result_without_types
        assert isinstance(result_without_types, dict)
