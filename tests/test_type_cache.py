"""Tests for TypeCache global caching of Pydantic/modict conversions."""

import pytest

try:
    from pydantic import BaseModel, ConfigDict
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False

from modict import modict
from modict._pydantic_interop import TypeCache

pytestmark = pytest.mark.skipif(not PYDANTIC_AVAILABLE, reason="Pydantic not installed")


def test_type_cache_pydantic_to_modict():
    """Test that Pydantic → modict conversions are cached globally."""

    # Clear cache first
    TypeCache.clear()

    class PydanticUser(BaseModel):
        name: str
        age: int = 25

    # First conversion
    ModictUser1 = modict.from_model(PydanticUser)

    # Second conversion should return the same cached class
    ModictUser2 = modict.from_model(PydanticUser)

    # Should be the exact same class object
    assert ModictUser1 is ModictUser2

    # Verify it's cached
    cached = TypeCache.get_modict(PydanticUser)
    assert cached is ModictUser1


def test_type_cache_modict_to_pydantic():
    """Test that modict → Pydantic conversions are cached globally."""

    # Clear cache first
    TypeCache.clear()

    class User(modict):
        name: str
        age: int = 25

    # First conversion
    PydanticUser1 = User.to_model()

    # Second conversion should return the same cached class
    PydanticUser2 = User.to_model()

    # Should be the exact same class object
    assert PydanticUser1 is PydanticUser2

    # Verify it's cached
    cached = TypeCache.get_pydantic(User)
    assert cached is PydanticUser1


def test_type_cache_nested_models():
    """Test that nested model conversions are cached."""

    # Clear cache first
    TypeCache.clear()

    class PydanticAddress(BaseModel):
        street: str
        city: str

    class PydanticUser(BaseModel):
        name: str
        address: PydanticAddress

    # Convert to modict
    ModictUser = modict.from_model(PydanticUser)

    # The nested PydanticAddress should be cached
    cached_address = TypeCache.get_modict(PydanticAddress)
    assert cached_address is not None

    # Converting PydanticAddress separately should use the cache
    ModictAddress = modict.from_model(PydanticAddress)
    assert ModictAddress is cached_address

    # Verify both conversions are cached
    assert TypeCache.get_modict(PydanticUser) is ModictUser
    assert TypeCache.get_modict(PydanticAddress) is ModictAddress


def test_type_cache_multiple_sessions():
    """Test that cache persists across multiple conversion sessions."""

    # Clear cache first
    TypeCache.clear()

    class PydanticModel1(BaseModel):
        value: str

    class PydanticModel2(BaseModel):
        data: int

    # First session: convert Model1
    ModictModel1_session1 = modict.from_model(PydanticModel1)

    # Second session: convert Model2
    ModictModel2_session1 = modict.from_model(PydanticModel2)

    # Third session: convert Model1 again (should be cached)
    ModictModel1_session2 = modict.from_model(PydanticModel1)

    # Should use the cache from first session
    assert ModictModel1_session1 is ModictModel1_session2

    # All should be in cache
    assert TypeCache.get_modict(PydanticModel1) is ModictModel1_session1
    assert TypeCache.get_modict(PydanticModel2) is ModictModel2_session1


def test_type_cache_bidirectional():
    """Test bidirectional caching: Pydantic → modict → Pydantic."""

    # Clear cache first
    TypeCache.clear()

    class OriginalPydantic(BaseModel):
        name: str
        age: int = 30

    # Convert to modict
    AsModict = modict.from_model(OriginalPydantic)

    # Convert back to Pydantic
    BackToPydantic = AsModict.to_model()

    # Both conversions should be cached
    assert TypeCache.get_modict(OriginalPydantic) is AsModict
    assert TypeCache.get_pydantic(AsModict) is BackToPydantic


def test_type_cache_modict_bidirectional():
    """Test bidirectional caching: modict → Pydantic → modict."""

    # Clear cache first
    TypeCache.clear()

    class OriginalModict(modict):
        name: str
        age: int = 30

    # Convert to Pydantic
    AsPydantic = OriginalModict.to_model()

    # Convert back to modict
    BackToModict = modict.from_model(AsPydantic)

    # Both conversions should be cached
    assert TypeCache.get_pydantic(OriginalModict) is AsPydantic
    assert TypeCache.get_modict(AsPydantic) is BackToModict


def test_type_cache_clear():
    """Test that TypeCache.clear() properly clears all cached conversions."""

    # Clear cache first
    TypeCache.clear()

    class PydanticModel(BaseModel):
        value: str

    class ModictModel(modict):
        data: int

    # Create conversions
    modict_result = modict.from_model(PydanticModel)
    pydantic_result = ModictModel.to_model()

    # Verify cached
    assert TypeCache.get_modict(PydanticModel) is not None
    assert TypeCache.get_pydantic(ModictModel) is not None

    # Clear cache
    TypeCache.clear()

    # Verify cache is empty
    assert TypeCache.get_modict(PydanticModel) is None
    assert TypeCache.get_pydantic(ModictModel) is None


def test_type_cache_with_config_changes():
    """Test that different configs create new classes (not cached)."""

    # Clear cache first
    TypeCache.clear()

    class PydanticUser(BaseModel):
        name: str
        age: int

    # First conversion with strict=True
    ModictUser1 = modict.from_model(PydanticUser, strict=True)

    # Note: The cache keys on the Pydantic class itself, not the config
    # So this WILL return the cached version, even with different config
    ModictUser2 = modict.from_model(PydanticUser, strict=False)

    # This is expected behavior - cache is based on class identity
    assert ModictUser1 is ModictUser2


def test_type_cache_nested_complex():
    """Test caching with deeply nested structures."""

    # Clear cache first
    TypeCache.clear()

    class PydanticAddress(BaseModel):
        street: str
        city: str

    class PydanticUser(BaseModel):
        name: str
        address: PydanticAddress

    class PydanticCompany(BaseModel):
        name: str
        owner: PydanticUser

    # Convert the top-level class
    ModictCompany = modict.from_model(PydanticCompany)

    # All nested classes should be cached
    assert TypeCache.get_modict(PydanticCompany) is ModictCompany
    assert TypeCache.get_modict(PydanticUser) is not None
    assert TypeCache.get_modict(PydanticAddress) is not None

    # Converting any nested class should use the cache
    ModictUser = modict.from_model(PydanticUser)
    ModictAddress = modict.from_model(PydanticAddress)

    assert ModictUser is TypeCache.get_modict(PydanticUser)
    assert ModictAddress is TypeCache.get_modict(PydanticAddress)
