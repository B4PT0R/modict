"""Basic coverage for the public typechecker/coercer utilities."""

import pytest
import modict.typechecker.src._public_api as public_api

from typing import (
    TypedDict,
    Protocol,
    runtime_checkable,
    Iterator,
    Iterable,
    Annotated,
    Literal,
    LiteralString,
    Union,
    Optional,
    MutableMapping,
    MutableSequence,
    MutableSet,
    Collection,
    Container,
    KeysView,
    ValuesView,
    ItemsView,
    Deque,
    NewType,
    Type,
    TypeVar,
    TypeAlias,
    ForwardRef,
    Generic,
    Required,
    NotRequired,
    Never,
    NoReturn,
    Iterator as TypingIterator,
    Generator as TypingGenerator,
    Final,
)
from collections import UserDict, UserList, deque
import collections.abc

from typechecker import (
    check_type,
    coerce,
    can_coerce,
    typechecked,
    coerced,
    TypeMismatchError,
    TypeCheckError,
    CoercionError,
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


def test_reset_global_typechecker_also_resets_global_coercer():
    checker_before = public_api._get_global_typechecker()
    coercer_before = public_api._get_global_coercer()

    assert coercer_before.type_checker is checker_before

    public_api.reset_global_typechecker()

    checker_after = public_api._get_global_typechecker()
    coercer_after = public_api._get_global_coercer()

    assert checker_after is not checker_before
    assert coercer_after is not coercer_before
    assert coercer_after.type_checker is checker_after


def test_reset_global_coercer_only_rebuilds_coercer_singleton():
    checker_before = public_api._get_global_typechecker()
    coercer_before = public_api._get_global_coercer()

    public_api.reset_global_coercer()

    coercer_after = public_api._get_global_coercer()

    assert coercer_after is not coercer_before
    assert coercer_after.type_checker is checker_before


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


def test_unannotated_callable_objects_are_left_untouched_by_decorators():
    class PlainCallable:
        def __call__(self, value):
            return value

    plain = PlainCallable()

    assert typechecked(plain) is plain
    assert coerced(plain) is plain


def test_typechecked_decorator_handles_varargs_and_kwargs():
    @typechecked
    def collect(*values: int, **items: int) -> tuple[tuple[int, ...], dict[str, int]]:
        return values, items

    assert collect(1, 2, a=3) == ((1, 2), {"a": 3})

    with pytest.raises(TypeMismatchError):
        collect("x")  # type: ignore[arg-type]

    with pytest.raises(TypeMismatchError):
        collect(a="x")  # type: ignore[arg-type]


def test_check_type_union_optional_literal():
    assert check_type(Optional[int], 1)
    assert check_type(Optional[int], None)
    assert check_type(Union[int, str], "x")
    with pytest.raises(TypeMismatchError):
        check_type(Literal["a", "b"], "c")


def test_literal_matches_exact_runtime_value_and_type():
    assert check_type(Literal[1], 1)
    assert check_type(Literal[False], False)
    with pytest.raises(TypeMismatchError):
        check_type(Literal[1], True)
    with pytest.raises(TypeMismatchError):
        check_type(Literal[False], 0)


def test_check_type_typevar_and_alias():
    T = TypeVar("T")
    Alias: TypeAlias = list[int]

    assert check_type(T, 1)
    assert check_type(T, "s")

    assert check_type(Alias, [1, 2, 3])
    with pytest.raises(TypeMismatchError):
        check_type(Alias, ["a", "b"])


def test_check_type_type_hint():
    class Base:
        pass

    class Child(Base):
        pass

    assert check_type(Type[Base], Base)
    assert check_type(Type[Base], Child)
    assert check_type(type[Base], Child)

    with pytest.raises(TypeMismatchError):
        check_type(Type[Child], Base)

    with pytest.raises(TypeMismatchError):
        check_type(Type[Base], Base())


def test_check_type_forwardref_object_and_type_alias_type():
    NodeRef = ForwardRef("Node")

    class Node:
        pass

    assert check_type(NodeRef, Node())

    if hasattr(__import__("typing"), "TypeAliasType"):
        import typing

        Alias = typing.TypeAliasType("Alias", list[int])
        assert check_type(Alias, [1, 2, 3])
        with pytest.raises(TypeMismatchError):
            check_type(Alias, ["1"])


def test_check_type_iterables_and_iterators():
    assert check_type(Iterable[int], [1, 2, 3])
    assert check_type(Iterator[int], iter([1, 2]))
    with pytest.raises(TypeMismatchError):
        check_type(Iterable[int], [1, "x"])


def test_iterator_and_iterator_backed_iterable_checks_are_shape_only():
    def gen_bad():
        yield 1
        yield "x"

    # Iterators are intentionally treated leniently to avoid consuming them.
    assert check_type(Iterator[int], gen_bad())
    assert check_type(Iterable[int], gen_bad())


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
    with pytest.raises(TypeMismatchError):
        check_type(HasX, {"x": 5, "y": 6})

    @runtime_checkable
    class HasXY(Protocol):
        def __call__(self, x: int, y: int) -> int: ...

    def adder(x: int, y: int) -> int:
        return x + y

    assert check_type(HasXY, adder)


def test_typed_dict_required_and_not_required_wrappers():
    class Payload(TypedDict, total=False):
        user_id: Required[int]
        nickname: NotRequired[str]

    assert check_type(Payload, {"user_id": 1})
    assert check_type(Payload, {"user_id": 1, "nickname": "ada"})

    with pytest.raises(TypeMismatchError):
        check_type(Payload, {"nickname": "ada"})

    with pytest.raises(TypeMismatchError):
        check_type(Payload, {"user_id": "1"})


def test_container_and_mapping_view_checks_are_interface_only():
    sample = {"a": 1, "b": 2}

    # Container[T] cannot verify the accepted membership domain at runtime.
    assert check_type(Container[int], {"x", "y"})

    # Mapping views are validated by interface shape only, not by element inspection.
    assert check_type(KeysView[int], sample.keys())
    assert check_type(ValuesView[str], sample.values())
    assert check_type(ItemsView[int, str], sample.items())


def test_protocol_structural_methods_and_runtime_attrs_are_checked():
    @runtime_checkable
    class HasX(Protocol):
        x: int

    class HasXOk:
        x = 3

    class HasXBad:
        x = "3"

    class RunnerProto(Protocol):
        def run(self, x: int) -> str: ...

    class RunnerOk:
        def run(self, x: int) -> str:
            return str(x)

    class RunnerBadArg:
        def run(self, x: str) -> str:
            return x

    class RunnerBadReturn:
        def run(self, x: int) -> int:
            return x

    assert check_type(HasX, HasXOk())
    with pytest.raises(TypeMismatchError):
        check_type(HasX, HasXBad())

    assert check_type(RunnerProto, RunnerOk())
    with pytest.raises(TypeMismatchError):
        check_type(RunnerProto, RunnerBadArg())
    with pytest.raises(TypeMismatchError):
        check_type(RunnerProto, RunnerBadReturn())


def test_protocol_property_annotations_are_checked_structurally():
    @runtime_checkable
    class HasName(Protocol):
        @property
        def name(self) -> str: ...

    class Good:
        @property
        def name(self) -> str:
            return "Ada"

    class Bad:
        @property
        def name(self) -> int:
            return 42

    assert check_type(HasName, Good())

    with pytest.raises(TypeMismatchError):
        check_type(HasName, Bad())


def test_check_type_callable_signature():
    def func(a: int, b: str) -> bool:
        return True

    from typing import Callable

    assert check_type(Callable[[int, str], bool], func)
    with pytest.raises(TypeMismatchError):
        check_type(Callable[[int, str], bool], lambda a: True)


def test_check_type_callable_variance():
    from typing import Callable

    def accepts_object(x: object) -> int:
        return 1

    def accepts_int(x: int) -> int:
        return 1

    def returns_bool(x: int) -> bool:
        return True

    def returns_object(x: int) -> object:
        return 1

    assert check_type(Callable[[int], int], accepts_object)
    assert check_type(Callable[[int], int], returns_bool)

    with pytest.raises(TypeMismatchError):
        check_type(Callable[[object], int], accepts_int)

    with pytest.raises(TypeMismatchError):
        check_type(Callable[[int], int], returns_object)


def test_check_type_callable_with_ellipsis_checks_return_annotation_only():
    from typing import Callable

    def typed_return(x: int) -> str:
        return str(x)

    def wrong_return(x: int) -> int:
        return x

    def unannotated_return(x: int):
        return str(x)

    assert check_type(Callable[..., str], typed_return)
    assert check_type(Callable[..., str], unannotated_return)

    with pytest.raises(TypeMismatchError):
        check_type(Callable[..., str], wrong_return)


def test_check_type_newtype_and_annotated():
    UserId = NewType("UserId", int)
    assert check_type(UserId, UserId(1))
    with pytest.raises(TypeMismatchError):
        check_type(UserId, "1")

    Hint = Annotated[int, "meta"]
    assert check_type(Hint, 5)
    with pytest.raises(TypeMismatchError):
        check_type(Hint, "5")


def test_check_type_literal_string_and_uninhabited_forms():
    assert check_type(LiteralString, "hello")
    with pytest.raises(TypeMismatchError):
        check_type(LiteralString, 123)

    for hint in (Never, NoReturn):
        with pytest.raises(TypeMismatchError):
            check_type(hint, "nope")


def test_coerce_nested_collections_and_unions():
    result = coerce(["1", "2"], list[int])
    assert result == [1, 2]
    res2 = coerce("3", Union[int, str])
    assert res2 in (3, "3")
    assert coerce("3", Union[str, int]) == "3"

    with pytest.raises(Exception):
        coerce("abc", int)


def test_coerce_type_hint_is_conservative():
    class Base:
        pass

    class Child(Base):
        pass

    assert coerce(Child, Type[Base]) is Child

    with pytest.raises(CoercionError):
        coerce(Base, Type[Child])

    with pytest.raises(CoercionError):
        coerce(Base(), Type[Base])


def test_coerce_forwardref_object_and_type_alias_type():
    NodeRef = ForwardRef("Node")

    class Node:
        pass

    assert isinstance(coerce(Node(), NodeRef), Node)

    if hasattr(__import__("typing"), "TypeAliasType"):
        import typing

        Alias = typing.TypeAliasType("Alias", list[int])
        assert coerce(["1", "2"], Alias) == [1, 2]


def test_coerce_literal_uses_exact_runtime_value():
    assert coerce("1", Literal[1]) == 1
    with pytest.raises(CoercionError):
        coerce(True, Literal[1])
    with pytest.raises(CoercionError):
        coerce(0, Literal[False])


def test_can_coerce_with_mixed_iterables():
    assert can_coerce([1, 2, 3], list[str]) is True
    assert can_coerce(["a", "b"], list[int]) is False


def test_coerce_prefers_canonical_containers_for_abcs():
    seq = coerce((1, "2"), MutableSequence[int])
    assert isinstance(seq, list)
    assert seq == [1, 2]

    mapping = coerce([("a", "1")], MutableMapping[str, int])
    assert isinstance(mapping, dict)
    assert mapping == {"a": 1}

    s = coerce(["1", "2"], MutableSet[int])
    assert isinstance(s, set)
    assert s == {1, 2}


def test_coerce_consumes_iterator_when_materializing():
    def gen():
        yield "1"
        yield "2"

    it = gen()
    result = coerce(it, MutableSequence[int])
    assert result == [1, 2]
    assert list(it) == []


def test_coerce_preserves_iterator_when_hint_is_iterator():
    def gen():
        yield "1"
        yield "2"

    it = gen()
    same_it = coerce(it, TypingIterator[str])
    assert same_it is it
    assert list(same_it) == ["1", "2"]


def test_coerce_keeps_instance_when_it_already_matches_interface():
    seq = UserList([1, 2])
    assert coerce(seq, MutableSequence[int]) is seq

    mapping = UserDict({"a": 1})
    assert coerce(mapping, MutableMapping[str, int]) is mapping

    s = {1, 2}
    assert coerce(s, MutableSet[int]) is s


def test_coerce_wraps_iterable_into_generator_with_coercion():
    gen = coerce(["1", "2"], TypingGenerator[int, None, None])
    collected = list(gen)
    assert collected == [1, 2]


def test_coerce_preserves_generator_instance():
    def g():
        yield 1
        yield 2

    original = g()
    coerced_gen = coerce(original, TypingGenerator[int, None, None])
    assert coerced_gen is original
    assert list(coerced_gen) == [1, 2]


def test_coerce_handles_annotated_hint():
    assert coerce("5", Annotated[int, "meta"]) == 5


def test_coerce_optional_final_and_typevars():
    Constrained = TypeVar("Constrained", int, str)
    Bound = TypeVar("Bound", bound=int)
    coercer = public_api._get_global_coercer()

    assert coerce(None, Optional[int]) is None
    assert coerce("4", Final[int]) == 4
    assert coerce("5", Constrained) == "5"
    assert coerce("6", Bound) == 6
    assert coercer._coerce_optional("3", Optional[int]) == 3


def test_coerce_pep604_optional_behaves_like_optional():
    assert coerce(None, int | None) is None
    assert coerce("3", int | None) == 3


def test_coerce_iterable_and_collection_materialize():
    iterable_res = coerce(("1", "2"), Iterable[int])
    assert iterable_res == (1, 2)

    collection_res = coerce({"1", "2"}, Collection[int])
    assert sorted(collection_res) == [1, 2]

    container_res = coerce(["1", "2"], Container[int])
    assert container_res == ["1", "2"]


def test_coerce_newtype_and_typeddict():
    UserId = NewType("UserId", int)
    assert coerce("42", UserId) == 42

    class Payload(TypedDict):
        name: str
        age: int

    coerced_payload = coerce({"name": "Alice", "age": "30", "extra": "ok"}, Payload)
    assert coerced_payload["age"] == 30
    assert coerced_payload["extra"] == "ok"

    with pytest.raises(CoercionError):
        coerce({"name": "Alice"}, Payload)


def test_coerce_typed_dict_required_and_not_required_wrappers():
    class Payload(TypedDict, total=False):
        user_id: Required[int]
        nickname: NotRequired[str]

    assert coerce({"user_id": "1"}, Payload) == {"user_id": 1}
    assert coerce({"user_id": "1", "nickname": 2}, Payload) == {
        "user_id": 1,
        "nickname": "2",
    }

    with pytest.raises(CoercionError):
        coerce({"nickname": "ada"}, Payload)


def test_coerce_literal_string_and_uninhabited_forms():
    assert coerce(123, LiteralString) == "123"
    for hint in (Never, NoReturn):
        with pytest.raises(CoercionError):
            coerce("nope", hint)


def test_coerce_rejects_protocol_and_callable():
    @runtime_checkable
    class HasRun(Protocol):
        def run(self) -> int: ...

    with pytest.raises(CoercionError):
        coerce({"run": lambda: 1}, HasRun)

    from typing import Callable

    with pytest.raises(CoercionError):
        coerce("not callable", Callable[[int], int])


def test_coerce_tuple_variants_and_length_errors():
    coercer = public_api._get_global_coercer()

    assert coerce((), tuple[()]) == ()
    assert coerce(["1", "2"], tuple[int, ...]) == (1, 2)
    assert coerce(("1", 2), tuple[int, str]) == (1, "2")

    with pytest.raises(public_api.CoercionError, match="Expected empty tuple"):
        coercer._coerce_tuple_like((1,), tuple[()], tuple, ((),))

    with pytest.raises(CoercionError, match="Expected tuple of length 3"):
        coerce((1, 2), tuple[int, str, bool])


def test_coerce_scalar_helpers_cover_edge_cases():
    coercer = public_api._get_global_coercer()

    assert coerce("123.0", int) == 123
    assert coerce(" YES ", bool) is True
    assert coerce("off", bool) is False
    assert coerce(3.0, int) == 3

    with pytest.raises(public_api.CoercionError, match="non-integer float"):
        coercer._str_to_int("123.4")

    with pytest.raises(public_api.CoercionError, match="Empty string"):
        coercer._str_to_int("   ")

    with pytest.raises(public_api.CoercionError, match="Empty string"):
        coercer._str_to_float("   ")

    with pytest.raises(public_api.CoercionError, match="Cannot convert 'maybe' to bool"):
        coercer._str_to_bool("maybe")

    with pytest.raises(public_api.CoercionError, match="decimal part"):
        coercer._float_to_int(3.5)


def test_coerce_string_sequences_and_forward_ref_failures():
    assert coerce("ab", list[str]) == ["a", "b"]
    assert coerce("ab", tuple[str, ...]) == ("a", "b")

    with pytest.raises(CoercionError, match="Cannot coerce string"):
        coerce("ab", Deque[str])

    with pytest.raises(CoercionError, match="Cannot resolve forward reference"):
        coerce(1, "DefinitelyMissingType")


def test_hostile_iterables_and_mappings_raise_coercionerror_instead_of_leaking():
    class BadIterable:
        def __iter__(self):
            raise RuntimeError("boom iter")

    class BadMapping:
        def items(self):
            raise RuntimeError("boom items")

    with pytest.raises(CoercionError, match="Cannot coerce .* to sequence"):
        coerce(BadIterable(), list[int])

    with pytest.raises(CoercionError, match="Cannot coerce .* to mapping"):
        coerce(BadMapping(), dict[str, int])

    assert can_coerce(BadIterable(), list[int]) is False


def test_coerced_decorator_coerces_args_and_return():
    @coerced
    def add(a: int, b: int) -> int:
        return a + b

    assert add("1", "2") == 3

    @coerced
    def returns_str(x: int) -> int:
        return "5"

    assert returns_str(1) == 5

    @coerced
    def no_coercion_on_failure(x: int) -> str:
        return f"{x}"

    with pytest.raises(TypeMismatchError):
        no_coercion_on_failure("abc")


def test_coerced_decorator_skips_unannotated_parameters():
    @coerced
    def mix(a: int, b, *, c: int) -> tuple[int, object, int]:
        return a, b, c

    assert mix("1", "kept", c="2") == (1, "kept", 2)


def test_coerced_decorator_handles_varargs_kwargs():
    @coerced
    def collect(*values: int, **items: int) -> list[int]:
        return list(values) + list(items.values())

    assert collect("1", "2", a="3", b=4) == [1, 2, 3, 4]


def test_coerced_decorator_rejects_invalid_varargs_and_kwargs_after_failed_coercion():
    @coerced
    def collect(*values: int, **items: int) -> list[int]:
        return list(values) + list(items.values())

    with pytest.raises(TypeMismatchError):
        collect("bad")

    with pytest.raises(TypeMismatchError):
        collect(a="bad")


def test_coerce_preserves_container_type_when_elements_change():
    seq = UserList(["1", "2"])
    coerced_seq = coerce(seq, MutableSequence[int])
    assert isinstance(coerced_seq, UserList)
    assert list(coerced_seq) == [1, 2]
    assert coerced_seq is not seq

    mapping = UserDict({"a": "1"})
    coerced_mapping = coerce(mapping, MutableMapping[str, int])
    assert isinstance(coerced_mapping, UserDict)
    assert coerced_mapping["a"] == 1
    assert coerced_mapping is not mapping

    s = {"1", "2"}
    coerced_set = coerce(s, MutableSet[int])
    assert isinstance(coerced_set, set)
    assert coerced_set == {1, 2}

    dq = deque(["1", "2"], maxlen=3)
    coerced_dq = coerce(dq, Deque[int])
    assert isinstance(coerced_dq, deque)
    assert list(coerced_dq) == [1, 2]
    assert coerced_dq.maxlen == 3


def test_recursive_type_alias_checks_without_infinite_recursion():
    RecursiveList: TypeAlias = list["RecursiveList"]

    value = []
    value.append(value)

    assert check_type(RecursiveList, value)


def test_recursive_coercion_fails_safely_instead_of_looping():
    RecursiveList: TypeAlias = list["RecursiveList"]

    inner = []
    value = (inner,)
    inner.append(value)

    with pytest.raises(CoercionError):
        coerce(value, RecursiveList)


def test_generic_instance_uses_runtime_type_arguments_when_available():
    T = TypeVar("T")

    class Box(Generic[T]):
        def __init__(self, value: T):
            self.value = value

    assert check_type(Box[int], Box[int](1))
    with pytest.raises(TypeMismatchError):
        check_type(Box[int], Box[str]("x"))


def test_generic_inheritance_substitutes_typevars_from_orig_bases():
    T = TypeVar("T")
    U = TypeVar("U")
    V = TypeVar("V")

    class MultiBox(Generic[T, U, V]):
        first: T
        second: U
        third: V

        def __init__(self, first: T, second: U, third: V):
            self.first = first
            self.second = second
            self.third = third

    class SubBox(MultiBox[T, str, bool], Generic[T]):
        pass

    assert check_type(SubBox[int], SubBox(1, "ok", True))

    with pytest.raises(TypeMismatchError):
        check_type(SubBox[int], SubBox("1", "ok", True))

    with pytest.raises(TypeMismatchError):
        check_type(SubBox[int], SubBox(1, 2, True))


def test_custom_generic_sequence_uses_abc_checker_paths():
    T = TypeVar("T")

    class FrozenSeq(collections.abc.Sequence, Generic[T]):
        def __init__(self, values):
            self._values = tuple(values)

        def __getitem__(self, index):
            return self._values[index]

        def __len__(self):
            return len(self._values)

    value = FrozenSeq([1, 2, 3])

    assert check_type(FrozenSeq[int], value)
    with pytest.raises(TypeMismatchError):
        check_type(FrozenSeq[str], value)


def test_typechecked_decorator_false_result_branches_raise_clear_errors(monkeypatch):
    class FakeChecker:
        def check_type(self, hint, value):
            return False

    monkeypatch.setattr(public_api, "_get_global_typechecker", lambda: FakeChecker())

    @public_api.typechecked
    def takes_one(a: int) -> int:
        return a

    @public_api.typechecked
    def takes_many(*values: int) -> int:
        return len(values)

    @public_api.typechecked
    def takes_kwargs(**items: int) -> int:
        return len(items)

    @public_api.typechecked
    def bad_return() -> int:
        return 1

    with pytest.raises(public_api.TypeMismatchError, match="Argument 'a' has invalid type"):
        takes_one(1)

    with pytest.raises(public_api.TypeMismatchError, match="Argument 'values' has invalid item"):
        takes_many(1)

    with pytest.raises(public_api.TypeMismatchError, match="Argument 'items\\[a\\]' has invalid type"):
        takes_kwargs(a=1)

    with pytest.raises(public_api.TypeMismatchError, match="Return value has invalid type"):
        bad_return()


def test_coerced_decorator_false_result_branches_raise_clear_errors(monkeypatch):
    class FakeCoercer:
        def coerce(self, value, hint):
            raise public_api.CoercionError("nope")

    class FakeChecker:
        def check_type(self, hint, value):
            return False

    monkeypatch.setattr(public_api, "_get_global_coercer", lambda: FakeCoercer())
    monkeypatch.setattr(public_api, "_get_global_typechecker", lambda: FakeChecker())

    @public_api.coerced
    def takes_one(a: int) -> int:
        return a

    @public_api.coerced
    def takes_many(*values: int) -> int:
        return len(values)

    @public_api.coerced
    def takes_kwargs(**items: int) -> int:
        return len(items)

    @public_api.coerced
    def bad_return() -> int:
        return "x"

    with pytest.raises(public_api.TypeMismatchError, match="Argument 'a' has invalid type"):
        takes_one(1)

    with pytest.raises(public_api.TypeMismatchError, match="Argument 'values' has invalid item"):
        takes_many(1)

    with pytest.raises(public_api.TypeMismatchError, match="Argument 'items\\[a\\]' has invalid type"):
        takes_kwargs(a=1)

    with pytest.raises(public_api.TypeMismatchError, match="Return value has invalid type"):
        bad_return()


def test_coercer_private_error_paths_and_fallbacks():
    coercer = public_api._get_global_coercer()

    with pytest.raises(public_api.CoercionError, match="Cannot coerce to special form"):
        original = coercer.type_checker._get_special_form_name
        coercer.type_checker._get_special_form_name = lambda hint: "Weird"
        try:
            coercer._coerce_special_form("x", object())
        finally:
            coercer.type_checker._get_special_form_name = original

    with pytest.raises(public_api.CoercionError, match="Cannot coerce .* any type in"):
        coercer._coerce_union(object(), Union[bytes, complex])

    with pytest.raises(public_api.CoercionError, match="Cannot coerce .* to mapping"):
        coercer._coerce_mapping_like(object(), dict[str, int], dict, (str, int))

    with pytest.raises(public_api.CoercionError, match="Cannot coerce .* to TypedDict"):
        class Payload(TypedDict):
            name: str

        coercer._coerce_typeddict(object(), Payload)

    with pytest.raises(public_api.CoercionError, match="Cannot coerce .* to container"):
        coercer._coerce_container_like(1, Container[int], collections.abc.Container, (int,))

    with pytest.raises(public_api.CoercionError, match="Cannot coerce .* to iterator"):
        coercer._coerce_iterator_like(1, TypingIterator[int], collections.abc.Iterator, (int,))

    with pytest.raises(public_api.CoercionError, match="Cannot coerce .* to <class 'int'>"):
        coercer._generic_basic_coercion(object(), int)

    with pytest.raises(public_api.CoercionError, match="Cannot coerce .* any literal value"):
        coercer._coerce_literal("x", Literal[1, 2])

    with pytest.raises(public_api.CoercionError, match="Cannot convert 'abc' to float"):
        coercer._str_to_float("abc")

    Unreachable = TypeVar("Unreachable", bytes, complex)
    with pytest.raises(public_api.CoercionError, match="any constraint"):
        coercer._coerce_typevar(object(), Unreachable)
