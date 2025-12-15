"""Basic coverage for the public typechecker/coercer utilities."""

import pytest

from typing import (
    TypedDict,
    Protocol,
    runtime_checkable,
    Iterator,
    Iterable,
    Annotated,
    Literal,
    Union,
    Optional,
    NewType,
    TypeVar,
    TypeAlias,
)

import pytest

from modict import (
    check_type,
    coerce,
    can_coerce,
    typechecked,
    TypeMismatchError,
    TypeCheckError,
)


def test_check_type_success_and_failure():
    assert check_type(int, 1) is True
    with pytest.raises(TypeMismatchError):
        check_type(int, "not an int")


def test_coerce_and_can_coerce():
    assert coerce("42", int) == 42
    assert coerce(("a", "b"), list[str]) == ["a", "b"]
    assert can_coerce("123", int) is True
    assert can_coerce("abc", int) is False


def test_typechecked_decorator_checks_args_and_return():
    @typechecked
    def add(a: int, b: int) -> int:
        return a + b

    assert add(1, 2) == 3

    with pytest.raises(TypeMismatchError):
        add("1", 2)  # type: ignore[arg-type]

    @typechecked
    def bad_return() -> int:
        return "oops"  # type: ignore[return-value]

    with pytest.raises(TypeMismatchError):
        bad_return()


def test_check_type_union_optional_literal():
    assert check_type(Optional[int], 1)
    assert check_type(Optional[int], None)
    assert check_type(Union[int, str], "x")
    with pytest.raises(TypeMismatchError):
        check_type(Literal["a", "b"], "c")


def test_check_type_typevar_and_alias():
    T = TypeVar("T")
    Alias: TypeAlias = list[int]

    # TypeVar without constraints should accept any
    assert check_type(T, 1)
    assert check_type(T, "s")

    assert check_type(Alias, [1, 2, 3])
    with pytest.raises(TypeMismatchError):
        check_type(Alias, ["a", "b"])


def test_check_type_iterables_and_iterators():
    assert check_type(Iterable[int], [1, 2, 3])
    assert check_type(Iterator[int], iter([1, 2]))
    with pytest.raises(TypeMismatchError):
        check_type(Iterable[int], [1, "x"])


def test_check_type_typed_dict_and_protocol():
    class Point(TypedDict):
        x: int
        y: int

    @runtime_checkable
    class HasX(Protocol):
        x: int

    assert check_type(Point, {"x": 1, "y": 2})
    with pytest.raises(TypeMismatchError):
        check_type(Point, {"x": 1})  # missing y
    # Protocol support is limited; expect failure for structural dict
    with pytest.raises(TypeMismatchError):
        check_type(HasX, {"x": 5, "y": 6})

    @runtime_checkable
    class HasXY(Protocol):
        def __call__(self, x: int, y: int) -> int: ...

    def adder(x: int, y: int) -> int:
        return x + y

    # Callable protocol is accepted for callable with matching signature
    assert check_type(HasXY, adder)
    with pytest.raises(TypeMismatchError):
        check_type(HasX, {"y": 6})


def test_check_type_callable_signature():
    def func(a: int, b: str) -> bool:
        return True

    # Typed callable
    from typing import Callable

    assert check_type(Callable[[int, str], bool], func)
    with pytest.raises(TypeMismatchError):
        check_type(Callable[[int, str], bool], lambda a: True)


def test_check_type_newtype_and_annotated():
    UserId = NewType("UserId", int)
    assert check_type(UserId, UserId(1))
    with pytest.raises(TypeMismatchError):
        check_type(UserId, "1")

    Hint = Annotated[int, "meta"]
    # Annotated currently unsupported → expect mismatch
    with pytest.raises(TypeMismatchError):
        check_type(Hint, 5)


def test_coerce_nested_collections_and_unions():
    result = coerce(["1", "2"], list[int])
    assert result == [1, 2]
    # Union coercion: depends on implementation; ensure one branch succeeds
    res2 = coerce("3", Union[int, str])
    assert res2 in (3, "3")

    with pytest.raises(Exception):
        coerce("abc", int)


def test_can_coerce_with_mixed_iterables():
    assert can_coerce([1, 2, 3], list[str]) is True  # ints can become str
    assert can_coerce(["a", "b"], list[int]) is False
