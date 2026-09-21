from typing import Callable

import pytest

from modict.typechecker import TypeMismatchError, check_type


def test_callable_accepts_variadic_and_optional_parameters():
    def variadic(*args):
        raise AssertionError("type checking must not invoke callbacks")

    def optional(first, second=None, *, option=False):
        raise AssertionError("type checking must not invoke callbacks")

    async def asynchronous(*args):
        raise AssertionError("type checking must not invoke callbacks")

    assert check_type(Callable[[int, str], object], variadic)
    assert check_type(Callable[[int, str], object], asynchronous)
    assert check_type(Callable[[int], object], optional)


def test_callable_checks_variadic_annotation_contravariantly():
    def broad(*args: object) -> int:
        return 1

    def narrow(*args: int) -> int:
        return 1

    assert check_type(Callable[[int, str], int], broad)
    assert check_type(Callable[[int, int], int], narrow)
    with pytest.raises(TypeMismatchError):
        check_type(Callable[[int, str], int], narrow)


def test_callable_rejects_unsatisfied_keyword_only_and_required_parameters():
    def keyword_only(*, value):
        pass

    def required(first, second):
        pass

    for callback in (keyword_only, required):
        with pytest.raises(TypeMismatchError):
            check_type(Callable[[int], object], callback)
