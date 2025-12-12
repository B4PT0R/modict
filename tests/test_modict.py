import pytest

from typing import Protocol, TypedDict, TypeVar, runtime_checkable

import modict as modict_pkg
from modict import (
    CoercionError,
    TypeMismatchError,
    coerce,
    modict,
    typechecked,
)


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
    assert first_user.profile.city == "Paris"

    # set_nested should create missing levels
    data.set_nested("$.settings.theme", "dark")
    assert data.get_nested("$.settings.theme") == "dark"


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


def test_check_decorator_runs_and_transforms():
    class Profile(modict):
        email: str

        @modict.check("email")
        def normalize_email(self, value):
            return value.strip().lower()

    profile = Profile(email="  TEST@EMAIL.COM  ")
    assert profile.email == "test@email.com"
    profile.email = "NEW@MAIL.COM"
    assert profile.email == "new@mail.com"


def test_strict_and_allow_extra_enforced():
    class StrictModel(modict):
        _config = modict.config(strict=True, allow_extra=False)
        age: int

    sm = StrictModel(age=21)
    with pytest.raises(KeyError):
        sm["unexpected"] = 1

    with pytest.raises(TypeError):
        sm.age = "not-an-int"


def test_json_enforcement_blocks_non_serializable():
    class JSONOnly(modict):
        _config = modict.config(enforce_json=True)
        data: object

    with pytest.raises(ValueError):
        JSONOnly(data=set([1, 2, 3]))

    inst = JSONOnly(data={"ok": True})
    with pytest.raises(ValueError):
        inst.data = {1, 2, 3}  # set not JSON-serializable


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


def test_coercion_with_strict_type_checking_in_modict():
    class Person(modict):
        _config = modict.config(strict=True, coerce=True)
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
        _config = modict.config(strict=True)
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
        _config = modict.config(strict=True)
        user: UserTD

    ok = WithTD(user={"name": "Alice", "age": 30})
    assert ok.user["age"] == 30

    with pytest.raises(TypeError):
        ok.user = {"name": "MissingAge"}


def test_typevar_coercion_and_constraints():
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
        allow_extra=False,
        coerce=True
    )
    width: Literal["centered", "wide"] = "centered"
    initial_sidebar_state: Literal["auto", "expanded", "collapsed"] = "auto"
    menu_items: Optional[dict[str, str]] = None

class Config(modict):
    _config = modict.config(
        enforce_json=True,
        allow_extra=False,
        coerce=True
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
    _config = modict.config(coerce=True)
    value: int = 0

class Outer(modict):
    _config = modict.config(coerce=True)
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
        _config = modict.config(coerce=True)
        width: str = "centered"

    class Config(modict):
        _config = modict.config(coerce=True)
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
    from modict._typechecker import Coercer, TypeChecker, CoercionError

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
    _config = modict.config(coerce=True)
    mode: Literal["dev", "prod"] = "dev"
    debug: bool = False

class AppConfig(modict):
    _config = modict.config(coerce=True)
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
