"""Tests for Query — combined path + value constraint."""
import pytest
from modict.collections_utils import Query, Path, MISSING


DATA = {
    "users": [
        {"name": "Alice", "age": 30, "email": "alice@example.com"},
        {"name": "Bob",   "age": 25, "email": "bob@example.com"},
        {"name": "Carol", "age": 30, "email": "carol@example.com"},
    ],
    "config": {"debug": False, "version": 3},
}


# ---------------------------------------------------------------------------
# Query() — no constraints
# ---------------------------------------------------------------------------

def test_no_constraints_finds_all_leaves():
    data = {"a": 1, "b": 2}
    results = Query().find(data)
    values = {v for _, v in results}
    assert values == {1, 2}


# ---------------------------------------------------------------------------
# path constraint — JSONPath string (wildcard)
# ---------------------------------------------------------------------------

def test_jsonpath_wildcard_no_value_constraint():
    results = Query("$.users[*].name").find(DATA)
    assert [v for _, v in results] == ["Alice", "Bob", "Carol"]


def test_jsonpath_wildcard_with_value_predicate():
    results = Query("$.users[*].age", lambda v: v > 28).find(DATA)
    assert [v for _, v in results] == [30, 30]


def test_jsonpath_wildcard_with_exact_value():
    results = Query("$.users[*].name", "Bob").find(DATA)
    assert len(results) == 1
    assert results[0][1] == "Bob"


def test_jsonpath_no_matches_returns_empty():
    results = Query("$.users[*].missing_key").find(DATA)
    assert results == []


def test_jsonpath_nested_scalar():
    results = Query("$.config.version").find(DATA)
    assert results[0][1] == 3


# ---------------------------------------------------------------------------
# path constraint — exact Path / tuple
# ---------------------------------------------------------------------------

def test_exact_tuple_path_match():
    results = Query(("users", 0, "name")).find(DATA)
    assert len(results) == 1
    assert results[0][1] == "Alice"


def test_exact_tuple_path_no_match():
    results = Query(("users", 99, "name")).find(DATA)
    assert results == []


def test_exact_path_object_match():
    p = Path(("config", "debug"))
    results = Query(p).find(DATA)
    assert results[0][1] is False


# ---------------------------------------------------------------------------
# path constraint — callable predicate
# ---------------------------------------------------------------------------

def test_path_predicate_last_key():
    results = Query(lambda p: p.keys[-1] == "email").find(DATA)
    assert len(results) == 3
    assert all("@" in v for _, v in results)


def test_path_predicate_depth():
    # depth 3: ("users", i, field)
    results = Query(lambda p: len(p.keys) == 3).find(DATA)
    assert len(results) > 0
    assert all(len(p.keys) == 3 for p, _ in results)


# ---------------------------------------------------------------------------
# value constraint only
# ---------------------------------------------------------------------------

def test_value_predicate_only():
    # ages: 30, 25, 30 — version: 3 (excluded), debug: False (not int)
    results = Query(value=lambda v: isinstance(v, int) and v >= 25).find(DATA)
    values = sorted(v for _, v in results)
    assert values == [25, 30, 30]


def test_value_exact_match_only():
    results = Query(value=False).find(DATA)
    assert len(results) == 1
    assert results[0][1] is False


def test_value_none_matches_none_leaves():
    """Query(value=None) should find leaves whose value IS None, not match everything."""
    data = {"a": None, "b": 1, "c": None}
    results = Query(value=None).find(data)
    assert len(results) == 2
    assert all(v is None for _, v in results)


def test_missing_value_constraint_matches_all():
    """Query() with no value arg uses MISSING, meaning no constraint."""
    data = {"a": 1, "b": None, "c": "x"}
    results = Query().find(data)
    assert len(results) == 3


def test_value_no_match():
    results = Query(value="nonexistent").find(DATA)
    assert results == []


# ---------------------------------------------------------------------------
# matches() — single pair testing
# ---------------------------------------------------------------------------

def test_matches_exact_path_and_value():
    q = Query(("users", 0, "name"), "Alice")
    assert q.matches(Path(("users", 0, "name")), "Alice")
    assert not q.matches(Path(("users", 0, "name")), "Bob")
    assert not q.matches(Path(("users", 1, "name")), "Alice")


def test_matches_callable_value():
    q = Query(value=lambda v: v > 10)
    assert q.matches(Path(("x",)), 42)
    assert not q.matches(Path(("x",)), 5)


def test_matches_no_constraints():
    q = Query()
    assert q.matches(Path(("anything",)), "anything")


# ---------------------------------------------------------------------------
# Results are Path objects
# ---------------------------------------------------------------------------

def test_find_results_are_path_objects():
    results = Query("$.users[*].age").find(DATA)
    assert all(isinstance(p, Path) for p, _ in results)


def test_found_paths_resolve_correctly():
    results = Query("$.users[*].name").find(DATA)
    # each Path should resolve back to the same value
    for path, value in results:
        assert path.resolve() == value


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_empty_structure():
    assert Query().find({}) == []
    assert Query().find([]) == []


def test_query_on_list_root():
    data = [1, 2, 3, 4]
    results = Query(value=lambda v: v % 2 == 0).find(data)
    assert [v for _, v in results] == [2, 4]


def test_deeply_nested():
    data = {"a": {"b": {"c": {"d": 42}}}}
    results = Query(value=42).find(data)
    assert len(results) == 1
    assert results[0][0].keys == ("a", "b", "c", "d")


def test_repr():
    q = Query("$.users[*].age", lambda v: v > 0)
    assert "Query" in repr(q)
