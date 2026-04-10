import pytest

from typing import (
    Dict,
    List,
    Mapping,
    MutableMapping,
    MutableSequence,
    Protocol,
    Sequence,
    TypedDict,
    TypeVar,
    runtime_checkable,
)

import modict as modict_pkg
from modict import (
    CoercionError,
    TypeMismatchError,
    coerce,
    modict,
    typechecked,
)
from modict.model_api import Computed


def test_attribute_access_and_defaults():
    class User(modict):
        name: str
        age: int = 30

    user = User(name="Alice")

    assert user.name == "Alice"
    assert user["age"] == 30  # default injected

    user.email = "a@example.com"  # attribute-style set writes to dict
    assert user["email"] == "a@example.com"
    user["age"] = 31
    assert user.age == 31


def test_auto_convert_nested_structures():
    data = modict({"users": [{"profile": {"city": "Paris"}}]})

    # list elements should be converted to modict lazily
    first_user = data["users"][0]
    assert isinstance(first_user, modict)
    # With lazy conversion, we stop recursion at the newly-created modict
    assert isinstance(dict.__getitem__(first_user, "profile"), dict)
    assert first_user.profile.city == "Paris"
    assert isinstance(dict.__getitem__(first_user, "profile"), modict)

    # set_nested can create missing levels explicitly
    data.set_nested(
        "$.settings.theme",
        "dark",
        create_missing=True,
        container_factory=lambda path: {},
    )
    assert data.get_nested("$.settings.theme") == "dark"


def test_convert_recurse_flag_stops_at_modict_nodes():
    shallow = modict.convert({"a": {"b": {"c": 1}}}, recurse=False)
    assert isinstance(shallow, modict)
    assert isinstance(dict.__getitem__(shallow, "a"), dict)  # not converted yet

    # test auto-convert with lazy conversion
    deep = modict({"a": {"b": {"c": 1}}})
    assert isinstance(deep, modict)
    assert isinstance(dict.__getitem__(deep, "a"), dict) # not converted yet
    assert isinstance(deep.a, modict) # converted on access
    assert isinstance(dict.__getitem__(deep.a, "b"), dict) # not converted yet
    assert isinstance(deep.a.b, modict) # chains nicely


def test_convert_and_unconvert_roundtrip():
    original = {"a": {"b": [1, {"c": 2}]}}
    converted = modict.convert(original)

    assert isinstance(converted, modict)
    assert isinstance(converted.a, modict)
    assert isinstance(converted.a["b"][1], modict)
    assert converted.a.b[1].c == 2

    back_to_dict = modict.unconvert(converted)
    assert back_to_dict == original
    assert not isinstance(back_to_dict["a"], modict)


def test_computed_with_cache_and_invalidation():
    call_counter = {"count": 0}

    class Calc(modict):
        a: int = 1
        b: int = 2

        @modict.computed(cache=True, deps=["a", "b"])
        def total(self):
            call_counter["count"] += 1
            return self.a + self.b

    calc = Calc()
    assert calc.total == 3
    assert calc.total == 3  # cached
    assert call_counter["count"] == 1

    calc.a = 5  # invalidates cache via deps
    assert calc.total == 7
    assert call_counter["count"] == 2


def test_computed_annotation_hint_does_not_conflict_with_storage():
    """A computed field can be annotated (e.g. sum: int = modict.computed(...)).

    The stored value is a Computed object, but type checking must apply to the computed
    *result* on access, not to the stored Computed wrapper.
    """
    from modict.model_api import Computed

    class Calc(modict):
        a: int
        b: int
        sum: int = modict.computed(lambda m: m.a + m.b, cache=True, deps=["a", "b"])

    c = Calc({"a": 1, "b": 2})
    # Raw stored value is Computed (not int)
    assert isinstance(dict.__getitem__(c, "sum"), Computed)
    # Access validates computed result against the annotation hint (int)
    assert c.sum == 3
    assert isinstance(c.sum, int)

    class BadCalc(modict):
        a: int
        sum: int = modict.computed(lambda m: "not an int")

    bad = BadCalc({"a": 1})
    with pytest.raises(TypeError):
        _ = bad.sum


def test_dynamic_computed_on_declared_field_uses_model_hint_in_lax_mode():
    class WithDeclaredComputedSlot(modict):
        _config = modict.config(require_all="never")
        total: int

    m = WithDeclaredComputedSlot()
    m["total"] = modict.computed(lambda self: "3")

    assert m.total == 3
    assert isinstance(m.total, int)


def test_dynamic_computed_on_declared_field_uses_model_hint_in_strict_mode():
    class StrictComputedSlot(modict):
        _config = modict.config(strict=True, require_all="never")
        total: int

    m = StrictComputedSlot()
    m["total"] = modict.computed(lambda self: "3")

    with pytest.raises(TypeError, match="expected <class 'int'>"):
        _ = m.total


def test_dynamic_computed_on_undeclared_field_ignores_callable_return_annotation():
    class DynamicComputed(modict):
        pass

    def compute(self) -> int:
        return "3"

    m = DynamicComputed()
    m["total"] = modict.computed(compute)

    assert m.total == "3"
    assert isinstance(m.total, str)


def test_attribute_errors_for_missing_keys():
    m = modict(a=1)
    with pytest.raises(AttributeError):
        _ = m.missing
    with pytest.raises(AttributeError):
        del m.missing


def test_wrap_preserves_plain_dict_like_construction():
    class Payload(modict):
        count: int

    plain = Payload(count="1")
    wrapped = Payload.wrap()(count="1")

    assert plain.count == 1
    assert wrapped.count == 1
    assert isinstance(wrapped, Payload)


def test_wrap_allows_pre_and_post_logic_without_changing_init_signature():
    class Payload(modict):
        count: int

        @classmethod
        def __wrap_init__(cls, init, *, offset):
            def wrapped(*args, **kwargs):
                # Pre: normalize incoming dict payload before native construction.
                if args:
                    data = dict(args[0])
                    data["count"] = int(data["count"]) + offset
                    args = (data, *args[1:])
                else:
                    kwargs["count"] = int(kwargs["count"]) + offset
                obj = init(*args, **kwargs)
                # Post: attach runtime-only metadata outside the payload.
                obj.set_attr("offset", offset)
                return obj

            return wrapped

    wrapped = Payload.wrap(offset=2)
    payload = wrapped(count="3")

    assert payload.count == 5
    assert payload.offset == 2
    assert "offset" not in payload


def test_wrap_does_not_apply_parent_wrapper_unless_child_routes_to_it():
    class Base(modict):
        count: int

        @classmethod
        def __wrap_init__(cls, init, *, trace_id):
            def wrapped(*args, **kwargs):
                obj = init(*args, **kwargs)
                obj.set_attr("trace_id", trace_id)
                return obj

            return wrapped

    class Child(Base):
        @classmethod
        def __wrap_init__(cls, init, *, trace_id):
            def wrapped(*args, **kwargs):
                obj = init(*args, **kwargs)
                obj.set_attr("wrapped_by_child", True)
                return obj

            return wrapped

    payload = Child.wrap(trace_id="req_123")(count=1)

    assert payload.has_attr("trace_id") is False
    assert payload.wrapped_by_child is True


def test_wrap_supports_native_dict_constructor_shapes():
    class Payload(modict):
        count: int

        @classmethod
        def __wrap_init__(cls, init, *, offset):
            def wrapped(*args, **kwargs):
                if args:
                    data = dict(args[0])
                    data["count"] = int(data["count"]) + offset
                    args = (data, *args[1:])
                else:
                    kwargs["count"] = int(kwargs["count"]) + offset
                return init(*args, **kwargs)

            return wrapped

    wrapped = Payload.wrap(offset=2)

    from_mapping = wrapped({"count": "3"})
    from_pairs = wrapped([("count", "4")])
    from_kwargs = wrapped(count="5")

    assert from_mapping.count == 5
    assert from_pairs.count == 6
    assert from_kwargs.count == 7


def test_wrap_contexts_are_isolated_and_do_not_pollute_payload():
    class Payload(modict):
        count: int

        @classmethod
        def __wrap_init__(cls, init, *, trace_id):
            def wrapped(*args, **kwargs):
                obj = init(*args, **kwargs)
                obj.set_attr("trace_id", trace_id)
                return obj

            return wrapped

    first = Payload.wrap(trace_id="req_1")(count=1)
    second = Payload.wrap(trace_id="req_2")(count=1)

    assert first.trace_id == "req_1"
    assert second.trace_id == "req_2"
    assert "trace_id" not in first
    assert "trace_id" not in second
    assert first.dumps() == '{"count": 1}'


def test_wrap_allows_explicit_parameter_routing_to_parent_wrapper():
    calls = []

    class Base(modict):
        value: int

        @classmethod
        def __wrap_init__(cls, init, *, registry):
            def wrapped(*args, **kwargs):
                calls.append(f"base:before:{registry}")
                obj = init(*args, **kwargs)
                obj.set_attr("registry", registry)
                calls.append(f"base:after:{registry}")
                return obj

            return wrapped

    class Child(Base):
        @classmethod
        def __wrap_init__(cls, init, *, registry, renderer):
            init = Base.__wrap_init__(init, registry=registry)

            def wrapped(*args, **kwargs):
                calls.append(f"child:before:{renderer}")
                obj = init(*args, **kwargs)
                obj.set_attr("renderer", renderer)
                calls.append(f"child:after:{renderer}")
                return obj

            return wrapped

    payload = Child.wrap(registry="component-registry", renderer="html")(
        value=1
    )

    assert calls == [
        "child:before:html",
        "base:before:component-registry",
        "base:after:component-registry",
        "child:after:html",
    ]
    assert payload.registry == "component-registry"
    assert payload.renderer == "html"


def test_wrap_post_logic_sees_validated_and_coerced_object():
    class Payload(modict):
        count: int

        @classmethod
        def __wrap_init__(cls, init, *, label):
            def wrapped(*args, **kwargs):
                obj = init(*args, **kwargs)
                obj.set_attr("summary", f"{label}:{obj.count}:{type(obj.count).__name__}")
                return obj

            return wrapped

    payload = Payload.wrap(label="count")(count="3")

    assert payload.count == 3
    assert payload.summary == "count:3:int"


def test_auto_convert_disabled():
    class NoAuto(modict):
        _config = modict.config(auto_convert=False)

    m = NoAuto({"nested": {"x": 1}})
    nested = m.nested
    assert isinstance(nested, dict) and not isinstance(nested, modict)


def test_dump_and_load_roundtrip(tmp_path):
    m = modict({"a": 1, "b": [1, 2]})
    path = tmp_path / "data.json"

    m.dump(path)
    loaded = modict.load(path)
    assert isinstance(loaded, modict)
    assert loaded == m

    s = m.dumps()
    loaded2 = modict.loads(s)
    assert loaded2 == m


def test_translate_and_extract_exclude():
    class User(modict):
        name: str
        age: int

    user = User(name="Alice", age=30)

    translated = user.translate(name="full_name")
    assert type(translated) is modict
    assert "full_name" in translated and "name" not in translated
    assert translated.full_name == "Alice"
    assert "name" in user and user.name == "Alice"

    # extract/exclude proxies
    extracted = dict(translated.extract("full_name"))
    assert extracted == {"full_name": "Alice"}
    excluded = dict(translated.exclude("age"))
    assert excluded == {"full_name": "Alice"}


def test_computed_uses_return_annotation_as_hint():
    """Verify that computed fields use the return type annotation as hint."""

    # Cas 1: Décorateur avec annotation de retour (pas d'annotation de classe)
    class Calc(modict):
        a: int = 1
        b: int = 2

        @modict.computed(cache=True, deps=["a", "b"])
        def total(self) -> int:
            return self.a + self.b

    # Le hint devrait être int (annotation de retour)
    field = Calc.__fields__['total']
    assert field.hint is int

    # Cas 2: Annotation de classe ET annotation de retour différentes
    # L'annotation de classe l'emporte !
    class Calc2(modict):
        result: str  # annotation de classe

        @modict.computed()
        def result(self) -> int:  # annotation de retour différente
            return 42

    # Le hint devrait être str (annotation de classe), pas int (annotation de retour)
    field2 = Calc2.__fields__['result']
    assert field2.hint is str

    # Cas 3: Annotation de classe sans annotation de retour
    class Calc3(modict):
        computed_value: float

        @modict.computed()
        def computed_value(self):
            return 3.14

    # Le hint devrait être float (annotation de classe)
    field3 = Calc3.__fields__['computed_value']
    assert field3.hint is float

    # Cas 4: Pas d'annotation de classe, pas d'annotation de retour
    class Calc4(modict):
        @modict.computed()
        def no_hint(self):
            return "test"

    # Le hint devrait être None
    field4 = Calc4.__fields__['no_hint']
    assert field4.hint is None


def test_computed_instance_level_assignment():
    """Test assigning computed values at instance level with class annotation contract."""

    # Cas 1: Champ avec annotation de classe, computed assigné à l'instance
    class Calculator(modict):
        _config = modict.config(require_all="never")
        result: float  # Le contrat : result doit être un float
        a: int = 1
        b: int = 2

    calc1 = Calculator()
    calc1.result = modict.computed(lambda self: self.a + self.b, cache=True)

    # Le computed devrait fonctionner
    assert calc1.result == 3

    # Le hint de classe est préservé
    assert Calculator.__fields__['result'].hint is float

    # Cas 2: Instance avec computed directement au constructeur
    calc2 = Calculator(
        a=5,
        b=10,
        result=modict.computed(lambda self: self.a * self.b, cache=True)
    )

    assert calc2.result == 50

    # Cas 3: Différentes stratégies de calcul sur différentes instances
    def strategy_add(self):
        return self.a + self.b

    def strategy_multiply(self):
        return self.a * self.b

    calc3 = Calculator(a=3, b=4, result=modict.computed(strategy_add))
    calc4 = Calculator(a=3, b=4, result=modict.computed(strategy_multiply))

    assert calc3.result == 7
    assert calc4.result == 12

    # Les deux instances partagent le même contrat de classe
    assert Calculator.__fields__['result'].hint is float


def test_computed_dict_value_assignment():
    """Computed can be stored directly as a dict value and evaluated on access."""
    calls = {"n": 0}

    def compute_sum(self):
        calls["n"] += 1
        return self.a + self.b

    m = modict({"a": 1, "b": 2})
    m["sum"] = modict.computed(compute_sum, cache=True, deps=["a"])

    assert m.sum == 3
    assert m.sum == 3
    assert calls["n"] == 1  # cached

    # b is not a dependency: should not invalidate cache.
    m.b = 10
    assert m.sum == 3
    assert calls["n"] == 1

    # a is a dependency: should invalidate cache.
    m.a = 2
    assert m.sum == 12
    assert calls["n"] == 2


def test_evaluate_computed_false_returns_raw_computed_object():
    """When evaluate_computed=False, Computed fields are not evaluated on access."""
    from modict.model_api import Computed

    calls = {"n": 0}

    class M(modict):
        _config = modict.config(evaluate_computed=False)
        a: int = 1
        b: int = 2
        sum: int = modict.computed(lambda self: calls.__setitem__("n", calls["n"] + 1) or (self.a + self.b))

    m = M({})
    raw = m["sum"]
    assert isinstance(raw, Computed)
    assert calls["n"] == 0

    # Attribute access goes through __getitem__ as well
    assert isinstance(m.sum, Computed)
    assert calls["n"] == 0


def test_computed_override_is_blocked_by_default():
    m = modict({"a": 1, "b": 2})
    m["sum"] = modict.computed(lambda self: self.a + self.b)
    with pytest.raises(TypeError):
        m["sum"] = 123
    with pytest.raises(TypeError):
        m["sum"] = modict.computed(lambda self: self.a * self.b)
    with pytest.raises(TypeError):
        del m["sum"]


def test_computed_override_can_be_enabled():
    m = modict({"a": 1, "b": 2})
    m["sum"] = modict.computed(lambda self: self.a + self.b)
    m._config.override_computed = True
    m["sum"] = 123
    assert m["sum"] == 123
    del m["sum"]
    assert "sum" not in m


def test_computed_declared_by_target_model_override_input_at_init():
    class Calc(modict):
        a: int = 1

        @modict.computed()
        def doubled(self) -> int:
            return self.a * 2

    c = Calc({"a": 1, "doubled": 999})
    assert c.doubled == 2


def test_cast_reinstalls_target_computed_over_incoming_value():
    class Source(modict):
        a: int = 1

    class Target(modict):
        a: int = 1

        @modict.computed()
        def doubled(self) -> int:
            return self.a * 2

    source = Source({"a": 3, "doubled": 999})
    casted = Target(source)

    assert casted.a == 3
    assert casted.doubled == 6


def test_manual_invalidate_computed_for_deps_empty():
    calls = {"n": 0}

    def compute_sum(self):
        calls["n"] += 1
        return self.a + self.b

    m = modict({"a": 1, "b": 2})
    m["sum"] = modict.computed(compute_sum, cache=True, deps=[])

    assert m.sum == 3
    assert m.sum == 3
    assert calls["n"] == 1  # cached

    m.a = 10
    assert m.sum == 3  # deps=[] -> no auto invalidation
    assert calls["n"] == 1

    m.invalidate_computed("sum")
    assert m.sum == 12
    assert calls["n"] == 2


def test_field_required_via_modict_field_default_missing():
    from modict import MISSING

    class User(modict):
        name: str = modict.field(default=MISSING, required="always")

    with pytest.raises(KeyError):
        User({})

    u = User({"name": "Alice"})
    assert u.name == "Alice"


def test_field_required_never_with_require_all_never():
    """Field required="never" makes the field optional when require_all is also "never"."""
    from modict import MISSING

    class UserOptional(modict):
        _config = modict.config(require_all="never")
        name: str = modict.field(default=MISSING, required="never")

    u = UserOptional({})
    assert "name" not in u


def test_field_required_always_overrides_require_all_never():
    """Field required="always" wins over require_all="never" (stronger constraint wins)."""
    from modict import MISSING

    class UserStrict(modict):
        _config = modict.config(require_all="never")
        name: str = modict.field(default=MISSING, required="always")

    with pytest.raises(KeyError):
        UserStrict({})


def test_annotation_only_field_is_required_at_init_by_default():
    """Default require_all="at_init" makes annotation-only fields required at construction."""
    class User(modict):
        name: str

    with pytest.raises(KeyError):
        User({})

    u = User({"name": "Alice"})
    assert u.name == "Alice"


def test_annotation_only_field_not_required_when_require_all_never():
    """Setting require_all="never" makes annotation-only fields optional."""
    class User(modict):
        _config = modict.config(require_all="never")
        name: str

    u = User({})
    assert "name" not in u


def test_require_all_makes_annotation_only_fields_required():
    class User(modict):
        _config = modict.config(require_all="always")
        name: str
        age: int = 25  # defaulted -> still present after init

    with pytest.raises(KeyError):
        User({})

    u = User({"name": "Alice"})
    assert u.name == "Alice"
    assert u.age == 25


def test_require_all_prevents_deleting_computed_fields():
    class M(modict):
        _config = modict.config(require_all="always", override_computed=True)
        a: int = 1

        @modict.computed()
        def doubled(self) -> int:
            return self.a * 2

    m = M({"a": 2})
    assert m.doubled == 4
    with pytest.raises(TypeError):
        del m["doubled"]


def test_require_all_prevents_clear_and_translate_stays_safe():
    class M(modict):
        _config = modict.config(require_all="always", override_computed=True)
        a: int

        @modict.computed()
        def doubled(self) -> int:
            return self.a * 2

    m = M({"a": 1})
    with pytest.raises(TypeError):
        m.clear()

    m.extra = 123
    translated = m.translate(a="x", extra="extra2")
    assert type(translated) is modict
    assert translated["x"] == 1
    assert translated["extra2"] == 123
    assert isinstance(dict.__getitem__(translated, "doubled"), Computed)
    assert m.a == 1
    assert m.extra == 123


def test_clear_respects_frozen_and_computed_protection():
    class Frozen(modict):
        _config = modict.config(frozen=True)
        a: int = 1

    frozen = Frozen()
    with pytest.raises(TypeError, match="frozen"):
        frozen.clear()

    protected = modict({"a": 1})
    protected["sum"] = modict.computed(lambda self: self.a + 1)
    with pytest.raises(TypeError, match="override_computed=False"):
        protected.clear()


def test_replacing_computed_invalidates_dependants_when_allowed():
    m = modict({"a": 1})
    m["sum"] = modict.computed(lambda self: self.a + 1, cache=True, deps=["a"])
    m["double"] = modict.computed(lambda self: self.sum * 2, cache=True, deps=["sum"])

    assert m.double == 4

    m._config.override_computed = True
    m["sum"] = modict.computed(lambda self: self.a + 10, cache=True, deps=["a"])

    assert m.double == 22

def test_manual_invalidate_computed_cascades_to_dependants():
    calls = {"sum": 0, "double": 0}

    def compute_sum(self):
        calls["sum"] += 1
        return self.a + self.b

    def compute_double(self):
        calls["double"] += 1
        return 2 * self.sum

    m = modict({"a": 1, "b": 2})
    m["sum"] = modict.computed(compute_sum, cache=True, deps=[])
    m["double"] = modict.computed(compute_double, cache=True, deps=["sum"])

    assert m.double == 6
    assert m.double == 6
    assert calls["sum"] == 1
    assert calls["double"] == 1

    m.a = 10
    assert m.double == 6  # deps=[] on sum -> still cached, so double stays cached too
    assert calls["sum"] == 1
    assert calls["double"] == 1

    m.invalidate_computed("sum")
    assert m.double == 24
    assert calls["sum"] == 2
    assert calls["double"] == 2


def test_manual_invalidate_computed_after_external_nested_mutation():
    calls = {"n": 0}

    class Bag(modict):
        items: list[int]

        @modict.computed(cache=True, deps=[])
        def total(self):
            calls["n"] += 1
            return sum(self["items"])

    bag = Bag(items=[1, 2, 3])

    assert bag.total == 6
    assert bag.total == 6
    assert calls["n"] == 1

    bag["items"].append(4)  # external deep mutation; no assignment hook triggered
    assert bag.total == 6
    assert calls["n"] == 1

    bag.invalidate_computed("total")
    assert bag.total == 10
    assert calls["n"] == 2


def test_validator_mode_after_runs_after_coercion_and_typecheck():
    class User(modict):
        age: int

        @modict.validator("age", mode="after")
        def must_be_int(self, value):
            assert isinstance(value, int)
            return value

    user = User(age="30")
    assert user.age == 30


def test_model_validator_multi_field_invariant():
    class Range(modict):
        start: int
        end: int

        @modict.model_validator(mode="after")
        def validate_order(self):
            if self["start"] > self["end"]:
                raise ValueError("start must be <= end")
            return None

    Range(start=1, end=2)
    with pytest.raises(ValueError):
        Range(start=10, end=2)


def test_model_validate_mapping_to_typed_instance():
    class User(modict):
        name: str
        age: int = 25

    user = User({"name": "Alice", "age": "30"})
    assert isinstance(user, User)
    assert user.age == 30


def test_computed_class_annotation_overrides_return_annotation():
    """Test that class annotation takes precedence over function return annotation."""

    class TypeCoercion(modict):
        # Annotation de classe : on veut un float
        value: float

        # Mais la fonction retourne un int
        @modict.computed()
        def value(self) -> int:
            return 42

    # Le hint devrait être float (annotation de classe l'emporte)
    assert TypeCoercion.__fields__['value'].hint is float

    # La valeur computed fonctionne
    tc = TypeCoercion()
    assert tc.value == 42


def test_computed_field_with_deps_at_instance_level():
    """Test that computed fields with deps work when assigned at instance level."""

    call_counter = {"count": 0}

    class Report(modict):
        total: float
        tax_rate: float = 0.20
        tax: float  # Annotation de classe pour le contrat

    def calculate_tax(self):
        call_counter["count"] += 1
        return self.total * self.tax_rate

    # Assigner le computed avec deps au niveau instance
    report = Report(
        total=100,
        tax=modict.computed(calculate_tax, cache=True, deps=["total", "tax_rate"])
    )

    assert report.tax == 20.0
    assert call_counter["count"] == 1

    # Cache fonctionne
    assert report.tax == 20.0
    assert call_counter["count"] == 1

    # Modification d'une dépendance invalide le cache
    report.total = 200
    assert report.tax == 40.0
    assert call_counter["count"] == 2


def test_check_decorator_runs_and_transforms():
    class Profile(modict):
        _config = modict.config(validate_assignment=True)
        email: str

        @modict.validator("email")
        def normalize_email(self, value):
            return value.strip().lower()

    profile = Profile(email="  TEST@EMAIL.COM  ")
    assert profile.email == "test@email.com"
    profile.email = "NEW@MAIL.COM"
    assert profile.email == "new@mail.com"


def test_any_validator_runs_for_declared_and_extra_keys():
    class Payload(modict):
        _config = modict.config(validate_assignment=True)
        name: str

        @modict.any_validator
        def normalize_strings(self, key, value):
            if isinstance(value, str):
                return f"{key}:{value.strip().lower()}"
            return value

    payload = Payload(name="  Alice  ", city="  Paris  ")

    assert payload.name == "name:alice"
    assert payload.city == "city:paris"

    payload["role"] = "  Admin "
    assert payload.role == "role:admin"


def test_any_validator_mode_after_runs_after_coercion():
    class Event(modict):
        count: int

        @modict.any_validator(mode="after")
        def observe_typed_values(self, key, value):
            assert key == "count"
            assert isinstance(value, int)
            return value + 1

    event = Event(count="2")
    assert event.count == 3


def test_any_validator_cannot_mutate_instance_during_validation():
    class Payload(modict):
        name: str

        @modict.any_validator
        def mutate(self, key, value):
            self["seen"] = True
            return value

    with pytest.raises(TypeError, match="inside any_validator"):
        Payload(name="alice")


def test_any_validator_cannot_delete_during_validation():
    class Payload(modict):
        name: str

        @modict.any_validator
        def mutate(self, key, value):
            if "name" in self:
                del self["name"]
            return value

    with pytest.raises(TypeError, match="inside any_validator"):
        Payload(name="alice")


def test_strict_and_extra_enforced():
    class StrictModel(modict):
        _config = modict.config(strict=True, extra='forbid', validate_assignment=True)
        age: int

    sm = StrictModel(age=21)
    with pytest.raises(KeyError):
        sm["unexpected"] = 1

    with pytest.raises(TypeError):
        sm.age = "not-an-int"


def test_extra_modes():
    """Test all three 'extra' modes: 'allow', 'forbid', 'ignore'."""

    # Test 'allow' mode (default)
    class AllowExtra(modict):
        _config = modict.config(extra='allow')
        name: str

    allow = AllowExtra(name="Alice", extra_field="allowed")
    assert "extra_field" in allow
    assert allow.extra_field == "allowed"
    allow.another_extra = "also allowed"
    assert allow.another_extra == "also allowed"

    # Test 'forbid' mode
    class ForbidExtra(modict):
        _config = modict.config(extra='forbid')
        name: str

    with pytest.raises(KeyError):
        ForbidExtra(name="Bob", extra_field="not allowed")

    forbid = ForbidExtra(name="Bob")
    with pytest.raises(KeyError):
        forbid.extra_field = "not allowed"

    # Test 'ignore' mode
    class IgnoreExtra(modict):
        _config = modict.config(extra='ignore')
        name: str

    ignore = IgnoreExtra(name="Charlie", extra_field="ignored", another="also ignored")
    assert "extra_field" not in ignore
    assert "another" not in ignore
    assert "name" in ignore
    assert ignore.name == "Charlie"
    assert dict(ignore) == {"name": "Charlie"}

    # Setting extra fields after creation should also ignore them
    ignore.new_extra = "should be ignored"
    assert "new_extra" not in ignore


def test_merge_and_deep_equals():
    base = modict({"db": {"host": "localhost", "port": 5432}})
    base.merge({"db": {"port": 3306, "ssl": True}})

    assert base.db.port == 3306
    assert base.db.ssl is True

    other = modict({"db": {"host": "localhost", "port": 3306, "ssl": True}})
    assert base.deep_equals(other)


def test_computed_dependency_chain_invalidation():
    call_counter = {"sum": 0, "double": 0}

    class Chain(modict):
        a: int = 1
        b: int = 2

        @modict.computed(cache=True, deps=["a", "b"])
        def summed(self):
            call_counter["sum"] += 1
            return self.a + self.b

        @modict.computed(cache=True, deps=["summed"])
        def doubled(self):
            call_counter["double"] += 1
            return self.summed * 2

    c = Chain()
    assert c.doubled == 6
    assert c.doubled == 6  # cached
    assert call_counter == {"sum": 1, "double": 1}

    c.b = 10  # should invalidate summed and doubled
    assert c.doubled == 22
    assert call_counter == {"sum": 2, "double": 2}


def test_version_exposed():
    assert isinstance(modict_pkg.__version__, str)
    assert modict_pkg.__version__ != ""


def test_coerce_utility_handles_common_structures():
    assert coerce("42", int) == 42
    assert coerce(("1", "2"), list[int]) == [1, 2]
    assert coerce([("k", "v")], dict[str, str]) == {"k": "v"}


def test_coercion_nested_models_inside_collections():
    class Address(modict):
        city: str
        zip_code: int

    class Company(modict):
        _config = modict.config(strict=False, validate_assignment=True)
        name: str
        addresses: list[Address]
        address_book: dict[int, Address]
        tagged_addresses: dict[str, list[Address]]
        recent_moves: MutableSequence[Address]

    payload = {
        "name": "Acme",
        "addresses": [{"city": "Paris", "zip_code": "75001"}, {"city": "NYC", "zip_code": 10001}],
        "address_book": {"1": {"city": "Berlin", "zip_code": "10115"}},
        "tagged_addresses": {"hq": [{"city": "London", "zip_code": "10101"}]},
        "recent_moves": ({"city": "Rome", "zip_code": "00100"},),
    }

    company = Company(payload)

    assert isinstance(company.addresses[0], Address)
    assert company.addresses[0].zip_code == 75001
    assert 1 in company.address_book and isinstance(company.address_book[1], Address)
    assert company.address_book[1].zip_code == 10115
    assert isinstance(company.tagged_addresses["hq"][0], Address)
    assert company.tagged_addresses["hq"][0].city == "London"
    assert isinstance(company.recent_moves[0], Address)
    assert company.recent_moves[0].city == "Rome"

    company.recent_moves = [{"city": "Lyon", "zip_code": "69000"}]
    assert isinstance(company.recent_moves[0], Address)
    assert company.recent_moves[0].zip_code == 69000


def test_coercion_nested_models_with_typing_generics():
    class Address(modict):
        city: str
        zip_code: int

    class Company(modict):
        _config = modict.config(strict=False, validate_assignment=True)
        name: str
        addresses: List[Address]
        address_book: Dict[int, Address]
        tagged_addresses: Dict[str, List[Address]]
        recent_moves: MutableSequence[Address]

    payload = {
        "name": "Globex",
        "addresses": [{"city": "Paris", "zip_code": "75001"}],
        "address_book": {"5": {"city": "Berlin", "zip_code": "10115"}},
        "tagged_addresses": {"hq": [{"city": "London", "zip_code": "10101"}]},
        "recent_moves": ({"city": "Rome", "zip_code": "00100"},),
    }

    company = Company(payload)

    assert isinstance(company.addresses[0], Address)
    assert company.addresses[0].zip_code == 75001
    assert isinstance(company.address_book[5], Address)
    assert company.address_book[5].city == "Berlin"
    assert isinstance(company.tagged_addresses["hq"][0], Address)
    assert company.tagged_addresses["hq"][0].city == "London"
    assert isinstance(company.recent_moves[0], Address)

    company.recent_moves = [{"city": "Lyon", "zip_code": "69000"}]
    assert isinstance(company.recent_moves[0], Address)
    assert company.recent_moves[0].zip_code == 69000


def test_coercion_supports_abstract_collection_hints():
    class Item(modict):
        sku: str
        qty: int

    class Inventory(modict):
        _config = modict.config(strict=False)
        backlog: MutableSequence[Item]
        overrides: MutableMapping[str, Item]
        shipped: Mapping[str, Sequence[Item]]

    inv = Inventory(
        backlog=({"sku": "abc", "qty": "1"}, {"sku": "def", "qty": 2}),
        overrides=[("main", {"sku": "zzz", "qty": "3"})],
        shipped={"eu": [{"sku": "a", "qty": "4"}], "us": ()},
    )

    assert [item.qty for item in inv.backlog] == [1, 2]
    assert isinstance(inv.overrides["main"], Item)
    assert inv.overrides["main"].qty == 3
    assert isinstance(inv.shipped["eu"][0], Item)
    assert inv.shipped["eu"][0].qty == 4
    assert isinstance(inv.shipped["us"], (list, tuple))


def test_coercion_with_strict_type_checking_in_modict():
    class Person(modict):
        _config = modict.config(strict=False, validate_assignment=True)
        age: int

    p = Person(age="5")
    assert p.age == 5 and isinstance(p.age, int)

    with pytest.raises(TypeError):
        p.age = "not-a-number"


def test_typechecked_decorator_checks_args_and_return():
    @typechecked
    def add(a: int, b: int) -> int:
        return a + b

    @typechecked
    def bad_return(a: int) -> int:
        return str(a)

    assert add(1, 2) == 3

    with pytest.raises(TypeMismatchError):
        add("x", 2)  # wrong arg type

    with pytest.raises(TypeMismatchError):
        bad_return(1)  # wrong return type


def test_protocol_validation_in_modict():
    @runtime_checkable
    class HasName(Protocol):
        name: str
        def greet(self) -> str: ...

    class Greeter:
        def __init__(self, name: str) -> None:
            self.name = name
        def greet(self) -> str:
            return f"hi {self.name}"

    class Wrapper(modict):
        _config = modict.config(strict=True, validate_assignment=True)
        user: HasName

    w = Wrapper(user=Greeter("Alice"))
    assert w.user.greet() == "hi Alice"

    with pytest.raises(TypeError):
        w.user = {"name": "Bob"}  # missing greet()


def test_typed_dict_validation():
    class UserTD(TypedDict):
        name: str
        age: int

    class WithTD(modict):
        _config = modict.config(strict=True, validate_assignment=True)
        user: UserTD

    ok = WithTD(user={"name": "Alice", "age": 30})
    assert ok.user["age"] == 30

    with pytest.raises(TypeError):
        ok.user = {"name": "MissingAge"}


def test_typevar_coercion_and_bound():
    TBound = TypeVar("TBound", bound=int)
    assert coerce("5", TBound) == 5
    with pytest.raises(CoercionError):
        coerce("abc", TBound)


def test_forward_reference_coercion_with_future_annotations():
    """Test que la coercion fonctionne avec from __future__ import annotations.

    Ce test vérifie que les forward references (annotations stockées comme strings)
    sont correctement résolues lors de la coercion.
    """
    # Créer un module temporaire avec from __future__ import annotations
    import sys
    from types import ModuleType

    # Code du module avec from __future__ import annotations
    module_code = '''
from __future__ import annotations
from modict import modict
from typing import Literal, Optional

class Layout(modict):
    _config = modict.config(
        enforce_json=True,
        extra='forbid',
        strict=False
    )
    width: Literal["centered", "wide"] = "centered"
    initial_sidebar_state: Literal["auto", "expanded", "collapsed"] = "auto"
    menu_items: Optional[dict[str, str]] = None

class Config(modict):
    _config = modict.config(
        enforce_json=True,
        extra='forbid',
        strict=False
    )
    title: str = "default"
    layout: Layout = modict.factory(Layout)
'''

    # Exécuter le code dans un namespace
    namespace = {}
    exec(module_code, namespace)

    Layout = namespace['Layout']
    Config = namespace['Config']

    # Vérifier que les annotations sont bien des strings (forward references)
    assert Config.__annotations__['layout'] == 'Layout'
    assert isinstance(Config.__fields__['layout'].hint, str)

    # Test 1: Coercion avec dict vide
    config = Config(layout={})
    assert isinstance(config.layout, Layout)
    assert type(config.layout).__name__ == 'Layout'

    # Test 2: Coercion avec dict contenant des données
    config2 = Config(layout={'width': 'wide'})
    assert isinstance(config2.layout, Layout)
    assert config2.layout.width == 'wide'

    # Test 3: Vérifier que les valeurs par défaut sont appliquées
    assert config.layout.width == 'centered'
    assert config.layout.initial_sidebar_state == 'auto'


def test_forward_reference_with_nested_modict_subclasses():
    """Test la coercion de sous-classes de modict imbriquées avec forward references."""
    import sys
    from types import ModuleType

    module_code = '''
from __future__ import annotations
from modict import modict

class Inner(modict):
    _config = modict.config(strict=False)
    value: int = 0

class Outer(modict):
    _config = modict.config(strict=False)
    inner: Inner = modict.factory(Inner)
    name: str = "test"
'''

    namespace = {}
    exec(module_code, namespace)

    Inner = namespace['Inner']
    Outer = namespace['Outer']

    # Test avec dict imbriqué
    outer = Outer(inner={'value': 42})
    assert isinstance(outer.inner, Inner)
    assert outer.inner.value == 42

    # Test avec dict vide
    outer2 = Outer(inner={})
    assert isinstance(outer2.inner, Inner)
    assert outer2.inner.value == 0  # valeur par défaut


def test_forward_reference_coercion_without_future_annotations():
    """Test que la coercion fonctionne aussi SANS from __future__ import annotations.

    Ce test assure la non-régression : le comportement existant doit continuer
    à fonctionner quand les annotations sont des classes directes.
    """
    class Layout(modict):
        _config = modict.config(strict=False)
        width: str = "centered"

    class Config(modict):
        _config = modict.config(strict=False)
        layout: Layout = modict.factory(Layout)

    # Sans from __future__, l'annotation est une référence de classe
    assert Config.__annotations__['layout'] is Layout
    assert Config.__fields__['layout'].hint is Layout

    # La coercion doit toujours fonctionner
    config = Config(layout={})
    assert isinstance(config.layout, Layout)
    assert config.layout.width == "centered"


def test_forward_reference_resolution_failure():
    """Test que les forward references non résolvables lèvent une erreur appropriée."""
    from typechecker import Coercer, TypeChecker, CoercionError

    coercer = Coercer(TypeChecker())

    # Tenter de coercer avec une forward reference non résolvable
    with pytest.raises(CoercionError) as exc_info:
        coercer.coerce({}, "NonExistentClass")

    assert "Cannot resolve forward reference" in str(exc_info.value)
    assert "NonExistentClass" in str(exc_info.value)


def test_forward_reference_with_complex_types():
    """Test les forward references avec des types complexes (Optional, Literal, etc.).

    Note: Ce test est simplifié car avec from __future__ import annotations,
    Optional[Settings] devient la string "Optional[Settings]" et nécessite une
    résolution complète qui dépend du contexte d'exécution.
    """
    module_code = '''
from __future__ import annotations
from modict import modict
from typing import Literal

class Settings(modict):
    _config = modict.config(strict=False)
    mode: Literal["dev", "prod"] = "dev"
    debug: bool = False

class AppConfig(modict):
    _config = modict.config(strict=False)
    settings: Settings = modict.factory(Settings)
'''

    namespace = {}
    exec(module_code, namespace)

    Settings = namespace['Settings']
    AppConfig = namespace['AppConfig']

    # Test avec dict et Literal
    app = AppConfig(settings={'mode': 'prod', 'debug': True})
    assert isinstance(app.settings, Settings)
    assert app.settings.mode == 'prod'
    assert app.settings.debug is True

    # Test avec valeur par défaut
    app2 = AppConfig(settings={})
    assert isinstance(app2.settings, Settings)
    assert app2.settings.mode == 'dev'  # valeur par défaut


def test_generic_default_key_and_value_hints_apply_to_undeclared_items():
    class Fibers(modict[str, int]):
        pass

    fibers = Fibers({1: "2"})

    assert list(fibers.keys()) == ["1"]
    assert fibers["1"] == 2


def test_generic_default_key_hint_is_checked_when_check_values_is_disabled():
    class Fibers(modict[int, str]):
        _config = modict.config(check_values=False, check_keys=True)

    fibers = Fibers({"1": "raw"})
    assert list(fibers.keys()) == [1]
    assert fibers[1] == "raw"

    with pytest.raises(TypeError, match="expected <class 'int'>"):
        Fibers({"bad": "raw"})


def test_generic_default_key_hint_is_checked_after_model_validator_after():
    class Fibers(modict[int, str]):
        @modict.model_validator(mode="after")
        def rewrite_key(self):
            if "1" in self:
                self[1] = self.pop("1")

    fibers = Fibers({"1": "raw"})
    assert list(fibers.keys()) == [1]
    assert fibers[1] == "raw"


def test_assignment_with_model_validator_sees_raw_key_before_final_key_normalization():
    class Fibers(modict[int, str]):
        @modict.model_validator(mode="after")
        def rewrite_key(self):
            if "2" in self:
                self[3] = self.pop("2")

    fibers = Fibers()
    fibers["2"] = "raw"

    assert list(fibers.keys()) == [3]
    assert fibers[3] == "raw"


def test_generic_default_value_hint_and_field_hint_errors_are_distinguished():
    class Animal:
        pass

    class Dog(Animal):
        pass

    class Kennel(modict[str, Animal]):
        lead: Dog

    kennel = Kennel(lead=Dog())
    assert isinstance(kennel.lead, Dog)

    with pytest.raises(TypeError, match="incompatible hints"):
        Kennel(lead=Animal())

    class InvalidKennel(modict[str, Animal]):
        count: int

    with pytest.raises(TypeError, match="expected <class .*Animal"):
        InvalidKennel(count=1)
