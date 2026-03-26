"""Tests for modict.find / found (deep via Query)."""
import pytest
from modict import modict, Query, Path, MISSING


# ---------------------------------------------------------------------------
# find / found — deep via Query
# ---------------------------------------------------------------------------

NESTED = modict({
    "users": [
        {"name": "Alice", "age": 30},
        {"name": "Bob",   "age": 25},
    ],
    "config": {"debug": False, "timeout": 30},
})


def test_find_returns_generator():
    import types
    result = NESTED.find(Query("$.users[*].name"))
    assert isinstance(result, types.GeneratorType)


def test_find_with_query_object():
    results = list(NESTED.find(Query("$.users[*].name")))
    assert [v for _, v in results] == ["Alice", "Bob"]


def test_find_inline_path_constraint_jsonpath():
    results = list(NESTED.find(path_constraint="$.users[*].age"))
    assert sorted(v for _, v in results) == [25, 30]


def test_find_inline_value_constraint():
    results = list(NESTED.find(value_constraint=30))
    assert len(results) == 2  # users[0].age and config.timeout
    assert all(v == 30 for _, v in results)


def test_find_inline_both_constraints():
    results = list(NESTED.find(
        path_constraint="$.users[*].age",
        value_constraint=lambda v: v >= 30,
    ))
    assert [v for _, v in results] == [30]


def test_find_mixing_query_and_constraints_raises():
    with pytest.raises(TypeError):
        list(NESTED.find(Query("$.users[*].name"), value_constraint="Alice"))


def test_find_no_args_finds_all_leaves():
    m = modict(a=1, b=2)
    results = list(m.find())
    values = {v for _, v in results}
    assert values == {1, 2}


def test_found_returns_modict():
    result = NESTED.found(Query("$.users[*].name"))
    assert isinstance(result, modict)


def test_found_keys_are_paths():
    result = NESTED.found(Query("$.users[*].name"))
    assert all(isinstance(k, Path) for k in result.keys())


def test_found_values_correct():
    result = NESTED.found(Query("$.users[*].name"))
    assert set(result.values()) == {"Alice", "Bob"}


def test_found_inline_constraints():
    result = NESTED.found(value_constraint=False)
    assert list(result.values()) == [False]


def test_found_empty_query():
    m = modict(a=1)
    result = m.found(Query(value="nonexistent"))
    assert isinstance(result, modict)
    assert len(result) == 0


# ---------------------------------------------------------------------------
# found + unwalk round-trip
# ---------------------------------------------------------------------------

def test_found_unwalk_reconstructs_subtree():
    """found() gives {Path: value}; unwalk() reconstructs the matched sub-structure."""
    from modict.collections_utils import unwalk
    m = modict({"users": [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]})
    ages = m.found(path_constraint="$.users[*].age")
    reconstructed = unwalk(ages)
    assert reconstructed["users"][0]["age"] == 30
    assert reconstructed["users"][1]["age"] == 25


# ---------------------------------------------------------------------------
# Advanced: find on typed modict with validators
# ---------------------------------------------------------------------------

def test_find_on_typed_modict():
    class User(modict):
        name: str
        age: int

    users = modict(
        alice=User(name="Alice", age=30),
        bob=User(name="Bob", age=17),
    )
    results = list(users.find(
        path_constraint=lambda p: p.keys[-1] == "age",
        value_constraint=lambda v: v < 18,
    ))
    assert len(results) == 1
    assert results[0][1] == 17


def test_find_path_objects_resolve_correctly():
    m = modict({"a": {"b": {"c": 99}}})
    results = list(m.find(value_constraint=99))
    assert len(results) == 1
    path, value = results[0]
    assert path.resolve() == 99
    assert path.keys == ("a", "b", "c")
