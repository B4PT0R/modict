from __future__ import annotations

from dataclasses import dataclass

import pytest

from path_utils import Path, PathNode, ensure_absolute, find_paths
from path_utils.src.path import ResolutionError


@dataclass
class User:
    name: str


def test_bind_and_resolve_dict_list():
    data = {"users": [{"name": "Ada"}, {"name": "Grace"}]}
    path = Path(["users", 1, "name"], root=data)
    assert path.resolve() == "Grace"
    assert str(path) == "$.users[1].name"
    assert repr(path) == "Path($.users[1].name)"
    assert path.nodes[0].parent_node is None
    assert path.nodes[1].parent_node is path.nodes[0]
    assert path.nodes[2].parent_node is path.nodes[1]


def test_bind_accepts_jsonpath_string():
    data = {"users": [{"name": "Ada"}, {"name": "Grace"}]}
    path = Path("$.users[0].name", root=data)
    assert tuple(path) == ("users", 0, "name")
    assert path.resolve() == "Ada"


def test_bind_accepts_relative_dotted_path_string():
    data = {"users": [{"name": "Ada"}, {"name": "Grace"}]}
    path = Path("users[1].name", root=data)
    assert tuple(path) == ("users", 1, "name")
    assert path.resolve() == "Grace"


def test_bind_without_keys_is_root_path():
    data = {"a": 1}
    root = Path(root=data)
    assert root.resolve() is data
    assert tuple(root) == ()


def test_bind_and_resolve_object_attribute():
    data = {"user": User(name="Ada")}
    path = Path(["user", "name"], root=data)
    assert path.resolve() == "Ada"


def test_pathnode_hash_ignores_container():
    a = PathNode(key="x", container={"x": 1})
    b = PathNode(key="x", container={"x": 2})
    assert a == b
    assert hash(a) == hash(b)


def test_parent_and_child_roundtrip():
    data = {"users": [{"name": "Ada"}]}
    path = Path(["users", 0, "name"], root=data)
    parent = path.parent()
    assert parent.resolve() == {"name": "Ada"}
    assert parent.child("name").resolve() == "Ada"


def test_parent_handles_zero_negative_and_overflow_levels():
    path = Path(("users", 0, "name"))

    assert path.parent(0) is path
    assert tuple(path.parent(10)) == ()

    with pytest.raises(ValueError, match="levels must be >= 0"):
        path.parent(-1)


def test_path_prefix_slice_preserves_binding():
    data = {"users": [{"name": "Ada"}]}
    path = Path(["users", 0, "name"], root=data)

    prefix = path[:2]

    assert tuple(prefix) == ("users", 0)
    assert prefix.resolve() == {"name": "Ada"}


def test_path_suffix_slice_preserves_cached_containers():
    data = {"users": [{"name": "Ada"}]}
    path = Path(["users", 0, "name"], root=data)

    suffix = path[1:]

    assert tuple(suffix) == (0, "name")
    assert suffix.resolve() == "Ada"


def test_empty_slices_preserve_root_only_for_prefixes():
    data = {"users": [{"name": "Ada"}]}
    path = Path(["users", 0, "name"], root=data)

    assert path[:0].resolve() is data

    with pytest.raises(ResolutionError):
        path[3:].resolve()


def test_set_and_delete_inplace_dict():
    data = {"a": {"b": 1}}
    path = Path(["a", "b"], root=data)
    path.set_inplace(2)
    assert data["a"]["b"] == 2
    path.delete_inplace()
    assert "b" not in data["a"]


def test_empty_path_set_and_delete_raise_value_error():
    path = Path()

    with pytest.raises(ValueError, match="empty Path"):
        path.set_inplace(1)

    with pytest.raises(ValueError, match="empty Path"):
        path.delete_inplace()


def test_find_paths_with_jsonpath_ng():
    data = {"users": [{"name": "Ada"}, {"name": "Grace"}]}
    paths = find_paths(data, "$.users[*].name")
    assert [p.resolve() for p in paths] == ["Ada", "Grace"]


def test_to_jsonpath_quotes_non_identifier():
    data = {"a-b": {"c d": 1}}
    path = Path(["a-b", "c d"], root=data)
    assert str(path) == "$['a-b']['c d']"

def test_jsonpath_like_attr_and_item_access():
    data = {"users": [{"name": "Ada"}], "a-b": {"c d": 1}, "keys": 123}
    root = Path(root=data)

    assert root.users[0].name.resolve() == "Ada"
    assert root["a-b"]["c d"].resolve() == 1
    assert root["keys"].resolve() == 123


def test_from_tuple_without_root_is_symbolic_and_binds():
    data = {"users": [{"name": "Ada"}]}
    p = Path(("users", 0, "name"))
    assert str(p) == "$.users[0].name"
    assert Path(p, root=data).resolve() == "Ada"


def test_from_jsonpath_without_root_is_symbolic_and_binds():
    data = {"users": [{"name": "Ada"}]}
    p = Path("$.users[0].name")
    assert tuple(p) == ("users", 0, "name")
    assert Path(p, root=data).resolve() == "Ada"


def test_symbolic_path_can_resolve_with_explicit_container():
    data = {"users": [{"name": "Ada"}]}
    p = Path(("users", 0, "name"))
    assert p.resolve(data) == "Ada"


def test_symbolic_path_resolve_without_container_raises():
    p = Path(("users", 0, "name"))
    with pytest.raises(ResolutionError):
        p.resolve()


def test_resolve_from_parameter_checks_against_stored_containers():
    data = {"users": [{"name": "Ada"}]}
    other = {"users": [{"name": "Grace"}]}
    p = Path(("users", 0, "name"), root=data)
    with pytest.raises(ResolutionError):
        p.resolve(other)


def test_symbolic_path_caches_containers_after_resolve():
    data = {"users": [{"name": "Ada"}]}
    other = {"users": [{"name": "Grace"}]}
    p = Path(("users", 0, "name"))
    assert p.resolve(data) == "Ada"
    assert p.resolve() == "Ada"
    with pytest.raises(ResolutionError):
        p.resolve(other)


def test_constructing_from_path_preserves_cached_containers():
    data = {"users": [{"name": "Ada"}]}
    other = {"users": [{"name": "Grace"}]}
    original = Path(("users", 0, "name"))
    assert original.resolve(data) == "Ada"

    cloned = Path(original)

    assert cloned.resolve() == "Ada"
    with pytest.raises(ResolutionError):
        cloned.resolve(other)


def test_exists_for_bound_and_symbolic_paths():
    data = {"a": {"b": 1}}
    bound_ok = Path(("a", "b"), root=data)
    bound_ko = Path(("a",), root=data)
    assert bound_ok.exists() is True
    assert bound_ko.exists() is True
    assert (bound_ko + "missing").exists() is False

    symbolic = Path(("a", "b"))
    assert symbolic.exists() is False
    assert symbolic.exists(data) is True


def test_add_concatenates_paths_and_keys():
    data = {"a": {"b": 1}}
    p = Path(("a",)) + ("b",)
    assert tuple(p) == ("a", "b")
    assert p.resolve(data) == 1

    p2 = Path(("a",)) + Path(("b",))
    assert tuple(p2) == ("a", "b")
    assert p2.resolve(data) == 1


def test_radd_treats_string_and_int_as_single_keys():
    assert tuple("user" + Path(("name",))) == ("user", "name")
    assert str("user" + Path(("name",))) == "$.user.name"
    assert tuple(0 + Path(("name",))) == (0, "name")
    assert str(0 + Path(("name",))) == "$[0].name"


def test_path_iterates_over_keys():
    path = Path(("users", 0, "name"))
    assert tuple(path) == ("users", 0, "name")
    assert len(path) == 3


def test_starts_with_and_is_ancestor_of():
    path = Path(("users", 0, "name"))

    assert path.starts_with(("users",))
    assert path.starts_with(Path(("users", 0)))
    assert not path.starts_with(("users", 1))

    parent = Path(("users",))
    assert parent.is_ancestor_of(path)
    assert parent.is_ancestor_of(path, strict=True)
    assert not path.is_ancestor_of(path, strict=True)


def test_relative_to_returns_suffix_path():
    data = {"users": [{"name": "Ada"}]}
    path = Path(("users", 0, "name"), root=data)

    relative = path.relative_to(("users",))

    assert tuple(relative) == (0, "name")
    assert relative.resolve() == "Ada"


def test_relative_to_raises_when_prefix_does_not_match():
    path = Path(("users", 0, "name"))
    with pytest.raises(ValueError):
        path.relative_to(("accounts",))


def test_walk_yields_leaf_paths_and_values():
    data = {"a": {"b": 1}, "c": [2, {"d": 3}], "e": []}
    results = list(Path.walk(data))
    by_jsonpath = {str(p): v for p, v in results}

    assert by_jsonpath["$.a.b"] == 1
    assert by_jsonpath["$.c[0]"] == 2
    assert by_jsonpath["$.c[1].d"] == 3
    assert by_jsonpath["$.e"] == []

    for p, v in results:
        assert p.resolve() == v


def test_walk_objects_traverses_object_attributes():
    data = {"user": User(name="Ada")}
    without = {str(p) for p, _ in Path.walk(data)}
    assert "$.user.name" not in without

    with_objects = {str(p): v for p, v in Path.walk(data, walk_objects=True)}
    assert with_objects["$.user.name"] == "Ada"


def test_invalidate_clears_cached_containers():
    data = {"a": {"b": 1}}
    p = Path(("a", "b"))
    assert p.resolve(data) == 1
    p.invalidate()
    with pytest.raises(ResolutionError):
        p.resolve()

    bound = Path(("a", "b"), root=data)
    assert bound.resolve() == 1
    bound.invalidate()
    assert bound.resolve() == 1


def test_set_root_rebinds_path_inplace():
    data1 = {"a": {"b": 1}}
    data2 = {"a": {"b": 2}}
    p = Path(("a", "b"))
    p.set_root(data1)
    assert p.resolve() == 1
    p.set_root(data2)
    assert p.resolve() == 2


def test_with_root_returns_rebound_copy():
    data1 = {"a": {"b": 1}}
    data2 = {"a": {"b": 2}}
    original = Path(("a", "b"), root=data1)

    rebound = original.with_root(data2)

    assert original.resolve() == 1
    assert rebound.resolve() == 2
    assert original is not rebound


def test_pathnode_resolution_failure_raises_resolutionerror():
    node = PathNode(key="missing", container={"a": 1})
    with pytest.raises(ResolutionError):
        node.resolve()


def test_pathnode_container_mismatch_raises():
    node = PathNode(key="a", container={"a": 1})
    with pytest.raises(ResolutionError):
        node.resolve({"a": 1})


def test_pathnode_invalid_container_error_is_stable_for_int_keys():
    with pytest.raises(TypeError, match="PathNode container must be"):
        PathNode(key=1, container=object())


def test_pathnode_mutation_requires_container():
    node = PathNode(key="a")

    with pytest.raises(ResolutionError, match="Missing container reference"):
        node.set_inplace(1)

    with pytest.raises(ResolutionError, match="Missing container reference"):
        node.delete_inplace()


def test_path_rejects_invalid_key_types():
    with pytest.raises(TypeError, match="Path keys must be int or str"):
        Path((object(),))


def test_empty_path_requires_root():
    with pytest.raises(ResolutionError):
        Path().resolve()


def test_ensure_absolute_accepts_absolute_and_rejects_relative_paths():
    assert ensure_absolute("$.users[0].name") == "$.users[0].name"
    with pytest.raises(ValueError, match="absolute"):
        ensure_absolute("users[0].name")
