from __future__ import annotations

from dataclasses import dataclass

import pytest

from path_utils import Path, PathNode, find_paths
from path_utils.src.path import ResolutionError


@dataclass
class User:
    name: str


def test_bind_and_resolve_dict_list():
    data = {"users": [{"name": "Ada"}, {"name": "Grace"}]}
    path = Path(["users", 1, "name"], root=data)
    assert path.resolve() == "Grace"
    assert str(path) == "$.users[1].name"
    assert path.nodes[0].parent_node is None
    assert path.nodes[1].parent_node is path.nodes[0]
    assert path.nodes[2].parent_node is path.nodes[1]


def test_bind_accepts_jsonpath_string():
    data = {"users": [{"name": "Ada"}, {"name": "Grace"}]}
    path = Path("$.users[0].name", root=data)
    assert path.keys == ("users", 0, "name")
    assert path.resolve() == "Ada"


def test_bind_without_keys_is_root_path():
    data = {"a": 1}
    root = Path(root=data)
    assert root.resolve() is data
    assert root.keys == ()


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


def test_set_and_delete_inplace_dict():
    data = {"a": {"b": 1}}
    path = Path(["a", "b"], root=data)
    path.set_inplace(2)
    assert data["a"]["b"] == 2
    path.delete_inplace()
    assert "b" not in data["a"]


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
    assert p.keys == ("users", 0, "name")
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
    assert p.keys == ("a", "b")
    assert p.resolve(data) == 1

    p2 = Path(("a",)) + Path(("b",))
    assert p2.keys == ("a", "b")
    assert p2.resolve(data) == 1


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


def test_pathnode_resolution_failure_raises_resolutionerror():
    node = PathNode(key="missing", container={"a": 1})
    with pytest.raises(ResolutionError):
        node.resolve()


def test_pathnode_container_mismatch_raises():
    node = PathNode(key="a", container={"a": 1})
    with pytest.raises(ResolutionError):
        node.resolve({"a": 1})


def test_empty_path_requires_root():
    with pytest.raises(ResolutionError):
        Path().resolve()
