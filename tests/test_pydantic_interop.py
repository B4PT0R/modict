"""Tests for Pydantic interoperability.

These tests require Pydantic to be installed.
If Pydantic is not available, tests will be skipped.
"""

import pytest
import sys
from typing import get_origin, get_args, List, Dict

# Try to import pydantic
try:
    from pydantic import BaseModel, Field, ValidationError
    PYDANTIC_AVAILABLE = True

    # Detect Pydantic version
    try:
        from pydantic import __version__ as pydantic_version
        PYDANTIC_V2 = pydantic_version.startswith('2.')
    except:
        PYDANTIC_V2 = hasattr(BaseModel, 'model_validate')

except ImportError:
    PYDANTIC_AVAILABLE = False
    PYDANTIC_V2 = False

from modict import modict, Field as ModictField
from modict._collections_utils import MISSING as MODICT_MISSING

# Skip all tests if Pydantic is not available
pytestmark = pytest.mark.skipif(
    not PYDANTIC_AVAILABLE,
    reason="Pydantic not installed"
)


class TestFromModel:
    """Tests for modict.from_model() - converting Pydantic to modict"""

    def test_basic_conversion(self):
        """Test basic conversion from Pydantic model to modict class"""
        class UserModel(BaseModel):
            name: str
            age: int

        User = modict.from_model(UserModel)

        # Check class name
        assert User.__name__ == "UserModel"

        # Check fields exist
        assert 'name' in User.__fields__
        assert 'age' in User.__fields__

        # Create instance
        user = User(name="Alice", age=30)
        assert user.name == "Alice"
        assert user.age == 30

    def test_default_values(self):
        """Test that default values are preserved"""
        class UserModel(BaseModel):
            name: str
            age: int = 25
            email: str = "default@example.com"

        User = modict.from_model(UserModel)

        # Create with minimal args
        user = User(name="Bob")
        assert user.name == "Bob"
        assert user.age == 25
        assert user.email == "default@example.com"

    def test_optional_fields(self):
        """Test Optional fields are handled correctly"""
        class UserModel(BaseModel):
            name: str
            email: str | None = None

        User = modict.from_model(UserModel)

        user = User(name="Charlie")
        assert user.name == "Charlie"
        assert user.email is None

    def test_custom_class_name(self):
        """Test custom class name for converted modict"""
        class UserModel(BaseModel):
            name: str

        User = modict.from_model(UserModel, name="CustomUser")
        assert User.__name__ == "CustomUser"

    def test_with_modict_config(self):
        """Test that modict config options are applied"""
        class UserModel(BaseModel):
            name: str
            age: int

        User = modict.from_model(UserModel, strict=False)

        user = User(name="Diana", age="30")  # String should be coerced to int
        assert user.age == 30
        assert isinstance(user.age, int)

    def test_nested_models(self):
        """Test conversion with nested Pydantic models"""
        class AddressModel(BaseModel):
            city: str
            country: str = "France"

        class UserModel(BaseModel):
            name: str
            address: AddressModel

        User = modict.from_model(UserModel)

        # Check that nested model type is preserved in annotations
        assert 'address' in User.__fields__

    def test_dict_of_models_converts_annotations_and_instances(self):
        """Dict fields containing models are converted."""
        class AddressModel(BaseModel):
            city: str

        class CompanyModel(BaseModel):
            offices: dict[str, AddressModel]

        Company = modict.from_model(CompanyModel)
        offices_type = Company.__annotations__['offices']

        assert get_origin(offices_type) in (dict, Dict)
        inner = get_args(offices_type)[1]
        assert isinstance(inner, type)
        assert issubclass(inner, modict)

        company = Company(offices={"paris": {"city": "Paris"}})
        assert isinstance(company.offices["paris"], modict)
        assert company.offices["paris"].city == "Paris"

    def test_list_fields(self):
        """Test fields with list types"""
        class UserModel(BaseModel):
            name: str
            tags: list[str] = []

        User = modict.from_model(UserModel)

        user = User(name="Eve")
        assert user.tags == []

        user2 = User(name="Frank", tags=["python", "coding"])
        assert user2.tags == ["python", "coding"]

    def test_with_field_default_factory(self):
        """Test Pydantic fields with default_factory"""
        class UserModel(BaseModel):
            name: str
            tags: list[str] = Field(default_factory=list)

        User = modict.from_model(UserModel)

        user1 = User(name="George")
        user2 = User(name="Hannah")

        # Each instance should have its own list
        user1.tags.append("tag1")
        assert "tag1" in user1.tags
        assert "tag1" not in user2.tags

    def test_pydantic_field_metadata_imported_into_modict(self):
        """Pydantic Field metadata should be captured into modict Field metadata."""
        class UserModel(BaseModel):
            name: str = Field(alias="full_name", description="Full name")
            age: int = Field(ge=0, description="Age in years")

        User = modict.from_model(UserModel)

        name_field = User.__fields__["name"]
        age_field = User.__fields__["age"]

        assert name_field.aliases["alias"] == "full_name"
        assert name_field.metadata["description"] == "Full name"
        assert age_field.constraints["ge"] == 0
        assert age_field.metadata["description"] == "Age in years"

    @pytest.mark.skipif(not PYDANTIC_V2, reason="Relies on Pydantic v2 FieldInfo features")
    def test_pydantic_field_metadata_preserved_non_destructive_bucket(self):
        class M(BaseModel):
            x: int = Field(
                multiple_of=2,
                json_schema_extra={"x": 1},
                validation_alias="xin",
                serialization_alias="xout",
                repr=False,
            )

        Mod = modict.from_model(M)
        field = Mod.__fields__["x"]
        md = field.metadata
        assert field.constraints["multiple_of"] == 2
        assert field._pydantic["json_schema_extra"] == {"x": 1}
        assert field.aliases["validation_alias"] == "xin"
        assert field.aliases["serialization_alias"] == "xout"
        assert field._pydantic["repr"] is False
        assert any(c["type"] == "MultipleOf" for c in field._pydantic["constraints"])


class TestToModel:
    """Tests for modict.to_model() - converting modict to Pydantic"""

    def test_basic_conversion(self):
        """Test basic conversion from modict class to Pydantic model"""
        class User(modict):
            name: str
            age: int

        UserModel = User.to_model()

        # Check class name
        assert UserModel.__name__ == "User"

        # Create Pydantic instance
        user = UserModel(name="Alice", age=30)
        assert user.name == "Alice"
        assert user.age == 30

    def test_default_values(self):
        """Test that default values are preserved"""
        class User(modict):
            name: str
            age: int = 25
            email: str = "default@example.com"

        UserModel = User.to_model()

        # Create with minimal args
        user = UserModel(name="Bob")
        assert user.name == "Bob"
        assert user.age == 25
        assert user.email == "default@example.com"

    def test_optional_fields(self):
        """Test Optional fields are handled correctly"""
        class User(modict):
            name: str
            email: str | None = None

        UserModel = User.to_model()

        user = UserModel(name="Charlie")
        assert user.name == "Charlie"
        assert user.email is None

    def test_optional_nested_modict(self):
        """Optional nested modict converts to optional Pydantic model."""
        class Address(modict):
            city: str

        class User(modict):
            name: str
            address: Address | None = None

        UserModel = User.to_model()

        user = UserModel(name="Dana")
        assert user.address is None

        user2 = UserModel(name="Eve", address={"city": "Nice"})
        assert user2.address.city == "Nice"

    def test_round_trip_preserves_check_keys_config(self):
        """modict -> Pydantic -> modict should preserve modict-specific check_keys."""

        class Loose(modict):
            _config = modict.config(check_keys=False)
            a: int = ModictField(required=True)

        P = Loose.to_model()
        assert getattr(P, "__modict__", {}).get("config", {}).get("check_keys") is False

        Loose2 = modict.from_model(P)
        assert getattr(Loose2, "_config").check_keys is False

        # check_keys=False bypasses required enforcement at init
        m = Loose2({})
        assert "a" not in m

    def test_custom_class_name(self):
        """Test custom class name for converted Pydantic model"""
        class User(modict):
            name: str

        UserModel = User.to_model(name="CustomUserModel")
        assert UserModel.__name__ == "CustomUserModel"

    def test_factory_fields(self):
        """Test that Factory fields are converted to default_factory"""
        class User(modict):
            name: str
            tags: list[str] = modict.factory(list)

        UserModel = User.to_model()

        user1 = UserModel(name="Diana")
        user2 = UserModel(name="Eve")

        # Each instance should have its own list
        user1.tags.append("tag1")
        assert "tag1" in user1.tags
        assert "tag1" not in user2.tags

    def test_pydantic_validation(self):
        """Test that Pydantic validation works on converted model"""
        class User(modict):
            name: str
            age: int

        UserModel = User.to_model()

        # Valid data should work
        user = UserModel(name="Frank", age=30)
        assert user.age == 30

        # Invalid data should raise ValidationError
        with pytest.raises(ValidationError):
            UserModel(name="George", age="not a number")

    def test_with_pydantic_config(self):
        """Test passing Pydantic config options"""
        class User(modict):
            name: str
            age: int

        if PYDANTIC_V2:
            UserModel = User.to_model(arbitrary_types_allowed=True)
        else:
            UserModel = User.to_model(arbitrary_types_allowed=True)

        # Should create successfully with config
        user = UserModel(name="Hannah", age=25)
        assert user.name == "Hannah"

    def test_modict_field_metadata_roundtrip_to_pydantic(self):
        """modict.Field metadata should be forwarded to Pydantic Field()."""
        class User(modict):
            name: str = ModictField(
                default=MODICT_MISSING,
                metadata={"description": "Full name"},
                aliases={"alias": "full_name"},
            )
            age: int = ModictField(default=0, metadata={"description": "Age in years"}, constraints={"ge": 0})

        UserModel = User.to_model()

        user = UserModel(full_name="Alice", age=1)
        assert user.name == "Alice"
        assert user.age == 1

        with pytest.raises(ValidationError):
            UserModel(full_name="Alice", age=-1)

        assert UserModel.model_fields["name"].alias == "full_name"
        assert UserModel.model_fields["name"].description == "Full name"

    @pytest.mark.skipif(not PYDANTIC_V2, reason="Relies on Pydantic v2 FieldInfo features")
    def test_modict_pydantic_raw_bucket_is_re_emitted(self):
        class M(modict):
            x: int = ModictField(
                default=MODICT_MISSING,
                constraints={"multiple_of": 2},
                aliases={"validation_alias": "xin", "serialization_alias": "xout"},
                _pydantic={"json_schema_extra": {"x": 1}, "repr": False},
            )

        P = M.to_model()
        fi = P.model_fields["x"]
        assert fi.json_schema_extra == {"x": 1}
        assert fi.validation_alias == "xin"
        assert fi.serialization_alias == "xout"
        assert fi.repr is False


class TestRoundTrip:
    """Tests for round-trip conversions"""

    def test_pydantic_to_modict_to_pydantic(self):
        """Test converting Pydantic -> modict -> Pydantic"""
        class OriginalModel(BaseModel):
            name: str
            age: int = 25

        # Convert to modict
        ModictClass = modict.from_model(OriginalModel)

        # Convert back to Pydantic
        NewModel = ModictClass.to_model()

        # Test they work the same
        original = OriginalModel(name="Alice")
        new = NewModel(name="Alice")

        assert original.name == new.name
        assert original.age == new.age

    def test_modict_to_pydantic_to_modict(self):
        """Test converting modict -> Pydantic -> modict"""
        class OriginalModict(modict):
            name: str
            age: int = 25

        # Convert to Pydantic
        PydanticClass = OriginalModict.to_model()

        # Convert back to modict
        NewModict = modict.from_model(PydanticClass)

        # Test they work the same
        original = OriginalModict(name="Bob")
        new = NewModict(name="Bob")

        assert original.name == new.name
        assert original.age == new.age

    def test_pydantic_to_modict_to_pydantic_preserves_default_factory(self):
        """default_factory should survive a Pydantic -> modict -> Pydantic round-trip."""
        class UserModel(BaseModel):
            name: str
            tags: list[str] = Field(default_factory=list)

        Mod = modict.from_model(UserModel)
        UserModel2 = Mod.to_model()

        if PYDANTIC_V2:
            assert UserModel2.model_fields["tags"].default_factory is list
        else:
            assert UserModel2.__fields__["tags"].default_factory is list

        u1 = UserModel2(name="a")
        u2 = UserModel2(name="b")
        u1.tags.append("x")
        assert u1.tags == ["x"]
        assert u2.tags == []

    def test_modict_to_pydantic_to_modict_preserves_factory_semantics(self):
        """Factory defaults should survive a modict -> Pydantic -> modict round-trip."""
        from modict._modict_meta import Factory

        class User(modict):
            tags: list[str] = ModictField(default=Factory(list))

        P = User.to_model()
        User2 = modict.from_model(P)

        u1 = User2()
        u2 = User2()
        u1.tags.append("x")
        assert u1.tags == ["x"]
        assert u2.tags == []

    def test_round_trip_schema_modict_to_model_to_modict(self):
        """modict.json_schema() should be stable across modict -> Model -> modict."""
        class Address(modict):
            city: str = ModictField(
                default=MODICT_MISSING,
                metadata={"description": "City name"},
                constraints={"min_length": 2, "max_length": 10, "pattern": r"^[A-Za-z]+$"},
            )

        class User(modict):
            name: str
            age: int = ModictField(default=25, constraints={"ge": 0, "lt": 130})
            address: Address

        s1 = User.json_schema()
        P = User.to_model()
        User2 = modict.from_model(P)
        s2 = User2.json_schema()

        # Normalize a couple of order-sensitive parts
        s1["required"] = sorted(s1.get("required", []))
        s2["required"] = sorted(s2.get("required", []))
        assert s1 == s2

    def test_round_trip_schema_model_to_modict_to_model(self):
        """Pydantic JSON schema should be stable across Model -> modict -> Model."""
        def normalize(obj):
            if isinstance(obj, dict):
                out = {k: normalize(v) for k, v in obj.items()}
                if "required" in out and isinstance(out["required"], list):
                    out["required"] = sorted(out["required"])
                for k in ("anyOf", "oneOf", "allOf"):
                    if k in out and isinstance(out[k], list):
                        out[k] = sorted(out[k], key=lambda x: str(x))
                return out
            if isinstance(obj, list):
                return [normalize(v) for v in obj]
            return obj

        class AddressModel(BaseModel):
            city: str = Field(description="City name", min_length=2, max_length=10, pattern=r"^[A-Za-z]+$")

        class UserModel(BaseModel):
            name: str
            age: int = Field(default=25, ge=0, lt=130)
            address: AddressModel

        Mod = modict.from_model(UserModel)
        UserModel2 = Mod.to_model()

        if PYDANTIC_V2:
            s1 = normalize(UserModel.model_json_schema())
            s2 = normalize(UserModel2.model_json_schema())
        else:
            s1 = normalize(UserModel.schema())
            s2 = normalize(UserModel2.schema())

        assert s1 == s2


class TestSchemaEquivalence:
    """Schema equivalence checks (modict -> Pydantic)."""

    @pytest.mark.skipif(not PYDANTIC_V2, reason="Targets Pydantic v2 JSON Schema shape")
    def test_modict_json_schema_is_subset_of_pydantic_model_json_schema(self):
        """Pydantic schema should include the standard subset emitted by modict.json_schema()."""

        def normalize(obj):
            if isinstance(obj, dict):
                out = {k: normalize(v) for k, v in obj.items()}
                # Pydantic may emit default JSON Schema keywords explicitly; modict keeps schemas minimal.
                if out.get("additionalProperties") is True:
                    out.pop("additionalProperties", None)
                if "required" in out and isinstance(out["required"], list):
                    out["required"] = sorted(out["required"])
                return out
            if isinstance(obj, list):
                return [normalize(v) for v in obj]
            return obj

        def assert_subset(expected, actual, *, path="$"):
            if isinstance(expected, dict):
                assert isinstance(actual, dict), f"{path}: expected dict, got {type(actual).__name__}"
                for k, v in expected.items():
                    if k == "$schema":
                        # Pydantic typically omits $schema; ignore for equivalence.
                        continue
                    assert k in actual, f"{path}: missing key {k!r}"
                    assert_subset(v, actual[k], path=f"{path}.{k}")
                return

            if isinstance(expected, list):
                assert isinstance(actual, list), f"{path}: expected list, got {type(actual).__name__}"
                # Only list we currently emit is 'required' (order-insensitive after normalization).
                assert expected == actual, f"{path}: list differs"
                return

            assert expected == actual, f"{path}: {expected!r} != {actual!r}"

        class Address(modict):
            city: str = ModictField(
                default=MODICT_MISSING,
                metadata={"description": "City name"},
                constraints={"min_length": 2, "max_length": 10, "pattern": r"^[A-Za-z]+$"},
            )

        class User(modict):
            name: str
            age: int = ModictField(default=25, constraints={"ge": 0, "lt": 130})
            address: Address

        modict_schema = normalize(User.json_schema())
        pydantic_schema = normalize(User.to_model().model_json_schema())
        assert_subset(modict_schema, pydantic_schema)

    @pytest.mark.skipif(not PYDANTIC_V2, reason="Targets Pydantic v2 JSON Schema shape")
    def test_modict_json_schema_additional_properties_forbid_matches_pydantic(self):
        """extra='forbid' should materialize as additionalProperties=false in both schemas."""

        def normalize(obj):
            if isinstance(obj, dict):
                out = {k: normalize(v) for k, v in obj.items()}
                if out.get("additionalProperties") is True:
                    out.pop("additionalProperties", None)
                if "required" in out and isinstance(out["required"], list):
                    out["required"] = sorted(out["required"])
                return out
            if isinstance(obj, list):
                return [normalize(v) for v in obj]
            return obj

        class User(modict):
            _config = modict.config(extra="forbid")
            name: str

        s_modict = normalize(User.json_schema())
        s_pyd = normalize(User.to_model().model_json_schema())
        assert s_modict.get("additionalProperties") is False
        assert s_pyd.get("additionalProperties") is False

    def test_instance_data_compatibility(self):
        """Test that instance data is compatible between modict and Pydantic"""
        class User(modict):
            name: str
            age: int
            email: str | None = None

        UserModel = User.to_model()

        # Create modict instance
        modict_user = User(name="Charlie", age=30)

        # Create Pydantic instance from modict's data
        if PYDANTIC_V2:
            pydantic_user = UserModel.model_validate(dict(modict_user))
        else:
            pydantic_user = UserModel.parse_obj(dict(modict_user))

        assert pydantic_user.name == modict_user.name
        assert pydantic_user.age == modict_user.age
        assert pydantic_user.email == modict_user.email


class TestModelValidators:
    """Tests for model-level validators conversion."""

    @pytest.mark.skipif(not PYDANTIC_V2, reason="Model validators mapping focuses on Pydantic v2")
    def test_pydantic_model_validator_after_imported_into_modict(self):
        from pydantic import model_validator

        class M(BaseModel):
            a: int
            b: int

            @model_validator(mode="after")
            def validate_sum(self):
                if self.a + self.b != 3:
                    raise ValueError("bad sum")
                return self

        Mod = modict.from_model(M)
        Mod(a=1, b=2)
        with pytest.raises(ValueError):
            Mod(a=1, b=1)

    @pytest.mark.skipif(not PYDANTIC_V2, reason="Model validators mapping focuses on Pydantic v2")
    def test_modict_model_validator_exported_to_pydantic(self):
        class M(modict):
            a: int
            b: int

            @modict.model_validator(mode="after")
            def validate_sum(self, values):
                if values["a"] + values["b"] != 3:
                    raise ValueError("bad sum")

        P = M.to_model()
        P(a=1, b=2)
        with pytest.raises(ValidationError):
            P(a=1, b=1)


class TestErrorHandling:
    """Tests for error handling"""

    def test_from_model_requires_pydantic(self):
        """Test that from_model raises ImportError if Pydantic not available"""
        # This test is a bit meta - we can't really test it when Pydantic IS available
        # But we can at least verify the method exists
        assert hasattr(modict, 'from_model')

    def test_from_model_invalid_input(self):
        """Test that from_model raises TypeError for non-Pydantic class"""
        class NotAPydanticModel:
            name: str

        with pytest.raises(TypeError):
            modict.from_model(NotAPydanticModel)

    def test_to_model_requires_pydantic(self):
        """Test that to_model method exists"""
        class User(modict):
            name: str

        assert hasattr(User, 'to_model')


class TestComputedFields:
    """Tests for computed fields support"""

    @pytest.mark.skipif(not PYDANTIC_V2, reason="Computed fields require Pydantic v2")
    def test_computed_field_conversion(self):
        """Test that computed fields are converted to Pydantic @computed_field"""
        class Person(modict):
            first_name: str
            last_name: str

            @modict.computed()
            def full_name(self):
                return f"{self.first_name} {self.last_name}"

        PersonModel = Person.to_model()

        # Create instance
        person = PersonModel(first_name="Alice", last_name="Smith")
        assert person.first_name == "Alice"
        assert person.last_name == "Smith"
        assert person.full_name == "Alice Smith"

    @pytest.mark.skipif(not PYDANTIC_V2, reason="Computed fields require Pydantic v2")
    def test_computed_field_with_type_hint(self):
        """Test computed field with type annotation"""
        class Calculator(modict):
            a: float
            b: float

            @modict.computed()
            def sum(self) -> float:
                return self.a + self.b

        CalcModel = Calculator.to_model()

        calc = CalcModel(a=10.5, b=20.3)
        assert calc.sum == pytest.approx(30.8)

    @pytest.mark.skipif(not PYDANTIC_V2, reason="Computed fields require Pydantic v2")
    def test_multiple_computed_fields(self):
        """Test multiple computed fields"""
        class Rectangle(modict):
            width: float
            height: float

            @modict.computed()
            def area(self) -> float:
                return self.width * self.height

            @modict.computed()
            def perimeter(self) -> float:
                return 2 * (self.width + self.height)

        RectModel = Rectangle.to_model()

        rect = RectModel(width=5, height=3)
        assert rect.area == 15
        assert rect.perimeter == 16

    @pytest.mark.skipif(not PYDANTIC_V2, reason="Computed fields require Pydantic v2")
    def test_round_trip_computed_fields(self):
        """Computed fields should survive a modict -> Pydantic -> modict -> Pydantic round-trip."""
        class Calculator(modict):
            a: float
            b: float

            @modict.computed()
            def sum(self) -> float:
                return self.a + self.b

        P1 = Calculator.to_model()
        M2 = modict.from_model(P1)
        P2 = M2.to_model()

        m = M2(a=1.5, b=2.5)
        assert m.sum == pytest.approx(4.0)

        p = P2(a=1.5, b=2.5)
        assert p.sum == pytest.approx(4.0)

    def test_modict_computed_cache_and_deps(self):
        """Computed cache + deps should work on modict instances."""
        calls = {"n": 0}

        class M(modict):
            a: int
            b: int = 0

            @modict.computed(cache=True, deps=["a"])
            def double(self) -> int:
                calls["n"] += 1
                return self.a * 2

        m = M(a=2, b=1)
        assert m.double == 4
        assert m.double == 4
        assert calls["n"] == 1  # cached

        # Changing an unrelated dependency should not invalidate.
        m.b = 2
        assert m.double == 4
        assert calls["n"] == 1

        # Changing a dependency should invalidate.
        m.a = 3
        assert m.double == 6
        assert calls["n"] == 2

    @pytest.mark.skipif(not PYDANTIC_V2, reason="Computed fields require Pydantic v2")
    def test_round_trip_modict_computed_cache_and_deps(self):
        """Computed cache + deps should survive a modict -> Pydantic -> modict round-trip (best-effort)."""
        calls = {"n": 0}

        class M(modict):
            a: int
            b: int = 0

            @modict.computed(cache=True, deps=["a"])
            def double(self) -> int:
                calls["n"] += 1
                return self.a * 2

        P = M.to_model()
        M2 = modict.from_model(P)

        m = M2(a=2, b=1)
        assert m.double == 4
        assert m.double == 4
        assert calls["n"] == 1  # cached

        m.b = 2
        assert m.double == 4
        assert calls["n"] == 1

        m.a = 3
        assert m.double == 6
        assert calls["n"] == 2

    @pytest.mark.skipif(not PYDANTIC_V2, reason="Computed fields require Pydantic v2")
    def test_round_trip_modict_computed_cache_and_deps_without_getter_attrs(self):
        """deps/cache metadata should survive even if getter attributes are stripped."""
        calls = {"n": 0}

        class M(modict):
            a: int
            b: int = 0

            @modict.computed(cache=True, deps=["a"])
            def double(self) -> int:
                calls["n"] += 1
                return self.a * 2

        P = M.to_model()

        # Simulate a situation where function attributes are lost (e.g. re-wrapping).
        cf = P.model_computed_fields["double"]
        getter = cf.wrapped_property.fget
        for attr in ("_modict_computed_cache", "_modict_computed_deps"):
            if hasattr(getter, attr):
                delattr(getter, attr)

        M2 = modict.from_model(P)

        m = M2(a=2, b=1)
        assert m.double == 4
        assert m.double == 4
        assert calls["n"] == 1  # cached

        m.b = 2
        assert m.double == 4
        assert calls["n"] == 1

        m.a = 3
        assert m.double == 6
        assert calls["n"] == 2

    @pytest.mark.skipif(not PYDANTIC_V2, reason="Computed fields require Pydantic v2")
    def test_round_trip_modict_computed_deps_preserved_explicitly(self):
        """Round-trip should preserve deps at the metadata level (not just behavior)."""

        class M(modict):
            a: int

            @modict.computed(cache=True, deps=["a"])
            def double(self) -> int:
                return self.a * 2

        P = M.to_model()

        cf = P.model_computed_fields["double"]
        extra = getattr(cf, "json_schema_extra", None) or {}
        assert extra.get("x-modict-computed", {}).get("deps") == ["a"]
        assert extra.get("x-modict-computed", {}).get("cache") is True

        M2 = modict.from_model(P)
        f = M2.__fields__["double"]
        assert getattr(f.default, "deps", None) == ["a"]
        assert getattr(f.default, "cache", None) is True

    @pytest.mark.skipif(not PYDANTIC_V2, reason="Computed fields require Pydantic v2")
    def test_from_model_computed_deps_from_x_modict_computed(self):
        """from_model() should read deps/cache from Pydantic computed_field json_schema_extra."""
        from pydantic import computed_field

        calls = {"n": 0}

        class P(BaseModel):
            a: int

            @computed_field(json_schema_extra={"x-modict-computed": {"deps": ["a"], "cache": True}})
            @property
            def double(self) -> int:
                calls["n"] += 1
                return self.a * 2

        M = modict.from_model(P)
        f = M.__fields__["double"]
        assert getattr(f.default, "deps", None) == ["a"]
        assert getattr(f.default, "cache", None) is True

        m = M(a=2)
        assert m.double == 4
        assert m.double == 4
        assert calls["n"] == 1  # cached

        m.a = 3
        assert m.double == 6
        assert calls["n"] == 2  # invalidated by deps=["a"]


class TestValidators:
    """Tests for validator conversion"""

    def test_modict_to_pydantic_validator(self):
        """Test converting modict @check to Pydantic validator"""
        class User(modict):
            email: str

            @modict.validator('email')
            def validate_email(self, value):
                return value.lower().strip()

        UserModel = User.to_model()

        # Validator should work
        user = UserModel(email="  ALICE@EXAMPLE.COM  ")
        assert user.email == "alice@example.com"

    def test_modict_to_pydantic_validator_mode_after(self):
        """mode='after' should run after Pydantic parsing/coercion."""
        class User(modict):
            age: int

            @modict.validator("age", mode="after")
            def ensure_int(self, value):
                if not isinstance(value, int):
                    raise ValueError("age must be int after parsing")
                return value

        UserModel = User.to_model()

        user = UserModel(age="30")
        assert user.age == 30

    def test_pydantic_to_modict_validator(self):
        """Test converting Pydantic validator to modict @check"""
        if PYDANTIC_V2:
            from pydantic import field_validator

            class UserModel(BaseModel):
                email: str

                @field_validator('email')
                @classmethod
                def validate_email(cls, value):
                    return value.lower().strip()
        else:
            from pydantic import validator

            class UserModel(BaseModel):
                email: str

                @validator('email')
                def validate_email(cls, value):
                    return value.lower().strip()

        User = modict.from_model(UserModel)

        # Validator should work
        user = User(email="  BOB@EXAMPLE.COM  ")
        assert user.email == "bob@example.com"

    def test_multiple_validators(self):
        """Test multiple validators on same field"""
        class Product(modict):
            name: str

            @modict.validator('name')
            def strip_name(self, value):
                return value.strip()

            @modict.validator('name')
            def uppercase_name(self, value):
                return value.upper()

        ProductModel = Product.to_model()

        product = ProductModel(name="  laptop  ")
        assert product.name == "LAPTOP"

    def test_validator_with_validation_error(self):
        """Test that validators can raise errors"""
        class User(modict):
            age: int

            @modict.validator('age')
            def validate_age(self, value):
                if value < 0:
                    raise ValueError("Age must be positive")
                return value

        UserModel = User.to_model()

        # Valid age
        user = UserModel(age=25)
        assert user.age == 25

        # Invalid age should raise error
        with pytest.raises(ValidationError):
            UserModel(age=-5)

    def test_round_trip_validators(self):
        """Test validators survive round-trip conversion"""
        class Person(modict):
            name: str

            @modict.validator('name')
            def validate_name(self, value):
                return value.strip().title()

        # modict -> Pydantic
        PersonModel = Person.to_model()

        # Pydantic -> modict
        NewPerson = modict.from_model(PersonModel)

        # Validator should still work
        person = NewPerson(name="  alice smith  ")
        assert person.name == "Alice Smith"

    @pytest.mark.skipif(not PYDANTIC_V2, reason="Model validators mapping focuses on Pydantic v2")
    def test_round_trip_pydantic_field_and_model_validators(self):
        """Field + model validators should survive a Pydantic -> modict -> Pydantic round-trip."""
        from pydantic import field_validator, model_validator

        class M(BaseModel):
            a: int
            b: int
            name: str

            @field_validator("name")
            @classmethod
            def strip_name(cls, value):
                return value.strip()

            @model_validator(mode="after")
            def validate_sum(self):
                if self.a + self.b != 3:
                    raise ValueError("bad sum")
                return self

        Mod = modict.from_model(M)
        M2 = Mod.to_model()

        ok = M2(a=1, b=2, name=" Alice ")
        assert ok.name == "Alice"

        with pytest.raises(ValidationError):
            M2(a=1, b=1, name="Bob")


class TestComplexScenarios:
    """Tests for more complex conversion scenarios"""

    def test_nested_pydantic_model_converts_to_nested_modict(self):
        """Nested Pydantic models become nested modict classes."""
        class AddressModel(BaseModel):
            street: str
            city: str

        class UserModel(BaseModel):
            name: str
            address: AddressModel

        User = modict.from_model(UserModel)

        address_type = User.__annotations__['address']
        assert isinstance(address_type, type)
        assert issubclass(address_type, modict)

        user = User(name="Alice", address={"street": "Main", "city": "Paris"})
        assert isinstance(user.address, modict)
        assert user.address.city == "Paris"
        assert user.address.street == "Main"

    def test_nested_collection_of_models_converts_annotations(self):
        """Containers of Pydantic models get converted in annotations."""
        class AddressModel(BaseModel):
            city: str

        class UserModel(BaseModel):
            name: str
            address: AddressModel

        class TeamModel(BaseModel):
            members: list[UserModel]

        Team = modict.from_model(TeamModel)
        members_type = Team.__annotations__['members']

        # list[<modict subclass>]
        assert get_origin(members_type) in (list, List)
        inner = get_args(members_type)[0]
        assert isinstance(inner, type)
        assert issubclass(inner, modict)

    def test_nested_modict_to_pydantic_model(self):
        """Nested modict classes convert to nested Pydantic models."""
        class Address(modict):
            street: str
            city: str

        class User(modict):
            name: str
            address: Address

        UserModel = User.to_model()

        user = UserModel(name="Alice", address={"street": "Main", "city": "Paris"})
        assert user.address.city == "Paris"
        assert user.address.street == "Main"
        assert hasattr(user.address, '__class__')
        assert user.address.__class__.__name__ == "Address"

    def test_collection_of_modicts_to_pydantic_model(self):
        """Containers of modict classes are converted in annotations."""
        class Address(modict):
            city: str

        class User(modict):
            name: str
            address: Address

        class Team(modict):
            members: list[User]

        TeamModel = Team.to_model()

        team = TeamModel(members=[{"name": "Bob", "address": {"city": "Lyon"}}])
        assert len(team.members) == 1
        member = team.members[0]
        assert member.name == "Bob"
        assert member.address.city == "Lyon"

    def test_dict_of_modicts_to_pydantic_model(self):
        """Dicts of modict classes are converted to dicts of Pydantic models."""
        class Product(modict):
            price: float

        class Catalog(modict):
            items: dict[str, Product]

        CatalogModel = Catalog.to_model()

        catalog = CatalogModel(items={"ref": {"price": 9.99}})
        assert isinstance(catalog.items["ref"], BaseModel)
        assert catalog.items["ref"].price == 9.99

    @pytest.mark.skipif(not PYDANTIC_V2, reason="Nested computed fields require Pydantic v2")
    def test_nested_round_trip_modict_to_pydantic_to_modict_to_pydantic_with_features(self):
        """Nested models round-trip with factory, computed fields and validators."""
        from modict._modict_meta import Factory

        class Address(modict):
            city: str
            tags: list[str] = ModictField(default=Factory(list))

            @modict.validator("city")
            def normalize_city(self, value):
                return value.strip().title()

            @modict.computed()
            def label(self) -> str:
                return f"City={self.city}"

        class User(modict):
            name: str
            address: Address

            @modict.validator("name")
            def normalize_name(self, value):
                return value.strip()

            @modict.computed()
            def greeting(self) -> str:
                return f"Hello {self.name} from {self.address.city}"

        class Team(modict):
            members: list[User] = ModictField(default=Factory(list))

        P1 = Team.to_model()
        M2 = modict.from_model(P1)
        P2 = M2.to_model()

        team = P2(
            members=[
                {"name": " Alice ", "address": {"city": " paris ", "tags": ["a"]}},
                {"name": "Bob", "address": {"city": "lyon"}},
            ]
        )

        assert team.members[0].name == "Alice"
        assert team.members[0].address.city == "Paris"
        assert team.members[0].address.label == "City=Paris"
        assert team.members[0].greeting == "Hello Alice from Paris"

        assert team.members[1].address.tags == []
        team.members[1].address.tags.append("x")

        team2 = P2(members=[{"name": "Cara", "address": {"city": "Lille"}}])
        assert team2.members[0].address.tags == []

        m = M2(
            members=[
                {"name": " Dan ", "address": {"city": " marseille "}},
            ]
        )
        assert m.members[0].name == "Dan"
        assert m.members[0].address.city == "Marseille"
        assert m.members[0].address.label == "City=Marseille"
        assert m.members[0].greeting == "Hello Dan from Marseille"

    @pytest.mark.skipif(not PYDANTIC_V2, reason="Nested computed fields require Pydantic v2")
    def test_nested_round_trip_pydantic_to_modict_to_pydantic_with_features(self):
        """Nested Pydantic models round-trip with factory, computed fields and validators."""
        from pydantic import computed_field, field_validator

        class AddressModel(BaseModel):
            city: str
            tags: list[str] = Field(default_factory=list)

            @field_validator("city")
            @classmethod
            def normalize_city(cls, value):
                return value.strip().title()

            @computed_field
            @property
            def label(self) -> str:
                return f"City={self.city}"

        class UserModel(BaseModel):
            name: str
            address: AddressModel

            @field_validator("name")
            @classmethod
            def normalize_name(cls, value):
                return value.strip()

            @computed_field
            @property
            def greeting(self) -> str:
                return f"Hello {self.name} from {self.address.city}"

        Mod = modict.from_model(UserModel)
        UserModel2 = Mod.to_model()

        u = UserModel2(name=" Alice ", address={"city": " paris "})
        assert u.name == "Alice"
        assert u.address.city == "Paris"
        assert u.address.label == "City=Paris"
        assert u.greeting == "Hello Alice from Paris"

        u2 = UserModel2(name="Bob", address={"city": "Lyon"})
        u2.address.tags.append("x")
        u3 = UserModel2(name="Cara", address={"city": "Lille"})
        assert u3.address.tags == []

    def test_nested_structure_conversion(self):
        """Test conversion with nested structures"""
        class Address(modict):
            street: str
            city: str
            country: str = "France"

        class User(modict):
            name: str
            age: int
            # Note: nested modict classes don't automatically convert to nested Pydantic
            # This is a known limitation - users should convert nested classes separately

        UserModel = User.to_model()
        user = UserModel(name="Diana", age=28)
        assert user.name == "Diana"

    def test_multiple_conversions(self):
        """Test converting multiple classes"""
        class User(modict):
            name: str

        class Product(modict):
            title: str
            price: float

        UserModel = User.to_model()
        ProductModel = Product.to_model()

        user = UserModel(name="Eve")
        product = ProductModel(title="Book", price=19.99)

        assert user.name == "Eve"
        assert product.title == "Book"
        assert product.price == 19.99

    def test_subclass_conversion(self):
        """Test converting modict subclasses"""
        class BaseUser(modict):
            name: str

        class ExtendedUser(BaseUser):
            age: int = 25

        UserModel = ExtendedUser.to_model()

        # Should include fields from both base and subclass
        user = UserModel(name="Frank")
        assert user.name == "Frank"
        assert user.age == 25


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
