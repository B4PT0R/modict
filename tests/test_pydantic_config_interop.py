"""Tests for Pydantic configuration interoperability."""

import pytest

try:
    from pydantic import BaseModel, ConfigDict
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False

from modict import modict

pytestmark = pytest.mark.skipif(not PYDANTIC_AVAILABLE, reason="Pydantic not installed")


class TestPydanticToModictConfig:
    """Test configuration mapping from Pydantic to modict."""

    def test_extra_config_mapping(self):
        """Test that Pydantic 'extra' config maps to modict."""

        # Test extra='forbid'
        class PydanticForbid(BaseModel):
            model_config = ConfigDict(extra='forbid')
            name: str

        ModictForbid = modict.from_model(PydanticForbid)

        # Should have extra='forbid' config
        assert hasattr(ModictForbid, '_config')
        assert ModictForbid._config.extra == 'forbid'

        # Should enforce at runtime
        m = ModictForbid(name="test")
        with pytest.raises(KeyError):
            m.extra_field = "not allowed"

    def test_extra_allow_mapping(self):
        """Test that Pydantic extra='allow' maps to modict."""

        class PydanticAllow(BaseModel):
            model_config = ConfigDict(extra='allow')
            name: str

        ModictAllow = modict.from_model(PydanticAllow)

        assert ModictAllow._config.extra == 'allow'

        # Should allow extra fields
        m = ModictAllow(name="test")
        m.extra_field = "allowed"
        assert m.extra_field == "allowed"

    def test_extra_ignore_mapping(self):
        """Test that Pydantic extra='ignore' maps to modict."""

        class PydanticIgnore(BaseModel):
            model_config = ConfigDict(extra='ignore')
            name: str

        ModictIgnore = modict.from_model(PydanticIgnore)

        assert ModictIgnore._config.extra == 'ignore'

        # Should ignore extra fields
        m = ModictIgnore(name="test", extra_field="ignored")
        assert "extra_field" not in m

    def test_frozen_config_mapping(self):
        """Test that Pydantic frozen config maps to modict."""

        class PydanticFrozen(BaseModel):
            model_config = ConfigDict(frozen=True)
            name: str

        ModictFrozen = modict.from_model(PydanticFrozen)

        assert ModictFrozen._config.frozen is True

        # Should be immutable
        m = ModictFrozen(name="test")
        with pytest.raises(TypeError, match="frozen"):
            m.name = "new"

    def test_strict_config_mapping(self):
        """Test that Pydantic strict config maps to modict."""

        class PydanticStrict(BaseModel):
            model_config = ConfigDict(strict=True)
            age: int

        ModictStrict = modict.from_model(PydanticStrict)

        assert ModictStrict._config.strict is True

    def test_str_transformations_mapping(self):
        """Test that Pydantic string transformations map to modict."""

        class PydanticStrings(BaseModel):
            model_config = ConfigDict(
                str_strip_whitespace=True,
                str_to_lower=True
            )
            email: str

        ModictStrings = modict.from_model(PydanticStrings)

        assert ModictStrings._config.str_strip_whitespace is True
        assert ModictStrings._config.str_to_lower is True

        # Should apply transformations
        m = ModictStrings(email="  ALICE@EXAMPLE.COM  ")
        assert m.email == "alice@example.com"

    def test_combined_config_mapping(self):
        """Test multiple config options mapping together."""

        class PydanticCombined(BaseModel):
            model_config = ConfigDict(
                extra='forbid',
                frozen=True,
                strict=True,
                str_strip_whitespace=True
            )
            name: str

        ModictCombined = modict.from_model(PydanticCombined)

        assert ModictCombined._config.extra == 'forbid'
        assert ModictCombined._config.frozen is True
        assert ModictCombined._config.strict is True
        assert ModictCombined._config.str_strip_whitespace is True

    def test_use_enum_values_config_mapping(self):
        """Test that Pydantic use_enum_values maps to modict and keeps behavior."""
        from enum import Enum

        class Color(str, Enum):
            RED = "red"

        class PydanticEnum(BaseModel):
            model_config = ConfigDict(use_enum_values=True)
            color: Color

        ModictEnum = modict.from_model(PydanticEnum)
        assert ModictEnum._config.use_enum_values is True

        m = ModictEnum(color=Color.RED)
        assert m.color == "red"

    def test_validate_default_config_mapping(self):
        """Test that Pydantic validate_default maps to modict."""
        class PydanticValidateDefault(BaseModel):
            model_config = ConfigDict(validate_default=True)
            age: int = 0

        ModictValidateDefault = modict.from_model(PydanticValidateDefault)
        assert ModictValidateDefault._config.validate_default is True

    def test_populate_by_name_config_mapping(self):
        """Test that Pydantic populate_by_name maps to modict."""
        class PydanticPopulateByName(BaseModel):
            model_config = ConfigDict(populate_by_name=True)
            name: str

        Mod = modict.from_model(PydanticPopulateByName)
        assert Mod._config.populate_by_name is True

    def test_alias_generator_config_mapping(self):
        """Test that Pydantic alias_generator maps to modict and generates aliases."""
        def gen(name: str) -> str:
            return name.upper()

        class PydanticAliasGen(BaseModel):
            model_config = ConfigDict(alias_generator=gen)
            name: str

        Mod = modict.from_model(PydanticAliasGen)
        assert callable(Mod._config.alias_generator)
        assert Mod.__fields__["name"].aliases["alias"] == "NAME"


class TestModictToPydanticConfig:
    """Test configuration mapping from modict to Pydantic."""

    def test_extra_config_reverse_mapping(self):
        """Test that modict 'extra' config maps to Pydantic."""

        class ModictForbid(modict):
            _config = modict.config(extra='forbid')
            name: str

        PydanticForbid = ModictForbid.to_model()

        # Check Pydantic config
        assert hasattr(PydanticForbid, 'model_config')
        assert PydanticForbid.model_config['extra'] == 'forbid'

        # Should enforce at runtime
        with pytest.raises(Exception):  # Pydantic ValidationError
            PydanticForbid(name="test", extra_field="not allowed")

    def test_frozen_reverse_mapping(self):
        """Test that modict frozen config maps to Pydantic."""

        class ModictFrozen(modict):
            _config = modict.config(frozen=True)
            name: str

        PydanticFrozen = ModictFrozen.to_model()

        assert PydanticFrozen.model_config['frozen'] is True

        # Should be immutable
        p = PydanticFrozen(name="test")
        with pytest.raises(Exception):  # Pydantic ValidationError
            p.name = "new"

    def test_strict_reverse_mapping(self):
        """Test that modict strict config maps to Pydantic."""

        class ModictStrict(modict):
            _config = modict.config(strict=True)
            age: int

        PydanticStrict = ModictStrict.to_model()

        assert PydanticStrict.model_config.get('strict') is True

    def test_str_transformations_reverse_mapping(self):
        """Test that modict string transformations map to Pydantic."""

        class ModictStrings(modict):
            _config = modict.config(
                str_strip_whitespace=True,
                str_to_lower=True
            )
            email: str

        PydanticStrings = ModictStrings.to_model()

        assert PydanticStrings.model_config.get('str_strip_whitespace') is True
        assert PydanticStrings.model_config.get('str_to_lower') is True

        # Should apply transformations in Pydantic too
        p = PydanticStrings(email="  ALICE@EXAMPLE.COM  ")
        assert p.email == "alice@example.com"

    def test_combined_config_reverse_mapping(self):
        """Test multiple config options mapping to Pydantic."""

        class ModictCombined(modict):
            _config = modict.config(
                extra='forbid',
                frozen=True,
                strict=True,
                str_strip_whitespace=True
            )
            name: str

        PydanticCombined = ModictCombined.to_model()

        config = PydanticCombined.model_config
        assert config['extra'] == 'forbid'
        assert config['frozen'] is True
        assert config.get('strict') is True
        assert config.get('str_strip_whitespace') is True

    def test_use_enum_values_reverse_mapping(self):
        """Test that modict use_enum_values maps to Pydantic and keeps behavior."""
        from enum import Enum

        class Color(str, Enum):
            RED = "red"

        class M(modict):
            _config = modict.config(use_enum_values=True)
            color: Color

        P = M.to_model()
        assert P.model_config.get("use_enum_values") is True

        p = P(color=Color.RED)
        assert p.color == "red"

    def test_validate_default_reverse_mapping(self):
        """Test that modict validate_default maps to Pydantic."""
        class M(modict):
            _config = modict.config(validate_default=True)
            age: int = 0

        P = M.to_model()
        assert P.model_config.get("validate_default") is True

    def test_populate_by_name_reverse_mapping(self):
        """Test that modict populate_by_name maps to Pydantic."""
        class M(modict):
            _config = modict.config(populate_by_name=True)
            name: str

        P = M.to_model()
        assert P.model_config.get("populate_by_name") is True

    def test_alias_generator_reverse_mapping(self):
        """Test that modict alias_generator maps to Pydantic and affects field aliases."""
        def gen(name: str) -> str:
            return name.upper()

        class M(modict):
            _config = modict.config(alias_generator=gen, populate_by_name=False)
            name: str

        P = M.to_model()
        assert callable(P.model_config.get("alias_generator"))
        assert P.model_fields["name"].alias == "NAME"


class TestConfigRoundTrip:
    """Test bidirectional config mapping preserves settings."""

    def test_pydantic_to_modict_to_pydantic_config(self):
        """Test config survives Pydantic → modict → Pydantic."""

        class OriginalPydantic(BaseModel):
            model_config = ConfigDict(
                extra='forbid',
                frozen=True,
                str_strip_whitespace=True
            )
            name: str

        # Convert to modict
        AsModict = modict.from_model(OriginalPydantic)

        # Convert back to Pydantic
        BackToPydantic = AsModict.to_model()

        # Config should be preserved
        config = BackToPydantic.model_config
        assert config['extra'] == 'forbid'
        assert config['frozen'] is True
        assert config.get('str_strip_whitespace') is True

    def test_modict_to_pydantic_to_modict_config(self):
        """Test config survives modict → Pydantic → modict."""

        class OriginalModict(modict):
            _config = modict.config(
                extra='forbid',
                frozen=True,
                str_to_lower=True
            )
            email: str

        # Convert to Pydantic
        AsPydantic = OriginalModict.to_model()

        # Convert back to modict
        BackToModict = modict.from_model(AsPydantic)

        # Config should be preserved
        assert BackToModict._config.extra == 'forbid'
        assert BackToModict._config.frozen is True
        assert BackToModict._config.str_to_lower is True

    def test_config_with_override(self):
        """Test that explicit parameters override extracted config."""

        class PydanticSource(BaseModel):
            model_config = ConfigDict(extra='allow', strict=False)
            name: str

        # Override with strict=True
        ModictOverride = modict.from_model(PydanticSource, strict=True)

        # Should have strict from override, extra from source
        assert ModictOverride._config.strict is True
        assert ModictOverride._config.extra == 'allow'

    def test_modict_specific_config_not_mapped(self):
        """Test that modict-specific config doesn't map to Pydantic."""

        class ModictSpecific(modict):
            _config = modict.config(
                check_values=True,
                enforce_json=True,
                auto_convert=True
            )
            name: str

        PydanticModel = ModictSpecific.to_model()

        # These are modict-specific and shouldn't appear in Pydantic config
        config = PydanticModel.model_config
        assert 'check_values' not in config
        assert 'enforce_json' not in config
        assert 'auto_convert' not in config
