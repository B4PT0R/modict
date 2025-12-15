"""
Example demonstrating the TypeCache for global caching of type conversions.

The TypeCache provides a global, session-wide cache for Pydantic ↔ modict
conversions. This ensures that:
1. Repeated conversions of the same type return the exact same class
2. Nested model conversions are properly cached
3. Memory is efficiently managed via weak references
"""

from modict import modict, TypeCache

try:
    from pydantic import BaseModel, ConfigDict
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False
    print("⚠️  Pydantic not installed - this example requires Pydantic")
    exit(0)


# ============================================================================
# Example 1: Basic Caching
# ============================================================================

print("=" * 70)
print("Example 1: Basic Caching")
print("=" * 70)

# Define a Pydantic model
class PydanticUser(BaseModel):
    name: str
    age: int = 25

# First conversion
print("First conversion...")
ModictUser1 = modict.from_model(PydanticUser)
print(f"Created modict class: {ModictUser1.__name__}")

# Second conversion - should return the cached class
print("\nSecond conversion (should use cache)...")
ModictUser2 = modict.from_model(PydanticUser)

# Verify they're the same object
print(f"Same class object? {ModictUser1 is ModictUser2}")  # True
print(f"ID of first:  {id(ModictUser1)}")
print(f"ID of second: {id(ModictUser2)}")

# Check the cache directly
cached = TypeCache.get_modict(PydanticUser)
print(f"\nCache lookup successful? {cached is ModictUser1}")

print()


# ============================================================================
# Example 2: Nested Model Caching
# ============================================================================

print("=" * 70)
print("Example 2: Nested Model Caching")
print("=" * 70)

class PydanticAddress(BaseModel):
    street: str
    city: str

class PydanticCompany(BaseModel):
    name: str
    address: PydanticAddress

# Convert the parent model (which includes the nested Address)
print("Converting parent model with nested child...")
ModictCompany = modict.from_model(PydanticCompany)
print(f"Created: {ModictCompany.__name__}")

# The nested PydanticAddress should automatically be cached
cached_address = TypeCache.get_modict(PydanticAddress)
print(f"\nNested PydanticAddress was automatically cached? {cached_address is not None}")

# Converting the nested model separately should use the cache
print("\nConverting nested model separately (should use cache)...")
ModictAddress = modict.from_model(PydanticAddress)
print(f"Uses cached version? {ModictAddress is cached_address}")

print()


# ============================================================================
# Example 3: Bidirectional Caching
# ============================================================================

print("=" * 70)
print("Example 3: Bidirectional Caching")
print("=" * 70)

class Person(modict):
    name: str
    email: str

print("Converting modict → Pydantic...")
PydanticPerson = Person.to_model()
print(f"Created Pydantic model: {PydanticPerson.__name__}")

# Check it's cached
print(f"Cached in Pydantic direction? {TypeCache.get_pydantic(Person) is not None}")

# Converting back should create a new modict class and cache it
print("\nConverting Pydantic → modict...")
BackToModict = modict.from_model(PydanticPerson)
print(f"Created modict class: {BackToModict.__name__}")

# Both directions should be cached
print(f"\nmodict → Pydantic cached? {TypeCache.get_pydantic(Person) is PydanticPerson}")
print(f"Pydantic → modict cached? {TypeCache.get_modict(PydanticPerson) is BackToModict}")

print()


# ============================================================================
# Example 4: Cache Management
# ============================================================================

print("=" * 70)
print("Example 4: Cache Management")
print("=" * 70)

class TempModel(BaseModel):
    value: str

# Create conversion
print("Creating conversion...")
TempModict = modict.from_model(TempModel)
print(f"Cache contains TempModel? {TypeCache.get_modict(TempModel) is not None}")

# Clear the entire cache
print("\nClearing cache...")
TypeCache.clear()

# Verify cache is empty
print(f"Cache contains TempModel after clear? {TypeCache.get_modict(TempModel) is not None}")

# Converting again creates a new class
print("\nConverting after clear (creates new class)...")
TempModict2 = modict.from_model(TempModel)
print(f"Same class as before clear? {TempModict2 is TempModict}")  # False
print(f"New class cached? {TypeCache.get_modict(TempModel) is TempModict2}")  # True

print()


# ============================================================================
# Example 5: Performance Benefits
# ============================================================================

print("=" * 70)
print("Example 5: Performance Benefits")
print("=" * 70)

import time

class Product(BaseModel):
    name: str
    price: float
    description: str

# Clear cache first
TypeCache.clear()

# Time first conversion (no cache)
start = time.perf_counter()
for _ in range(100):
    TypeCache.clear()  # Clear each time to measure without cache
    modict.from_model(Product)
elapsed_no_cache = time.perf_counter() - start

# Time with cache
TypeCache.clear()
modict.from_model(Product)  # Prime the cache
start = time.perf_counter()
for _ in range(100):
    modict.from_model(Product)  # Should use cache every time
elapsed_with_cache = time.perf_counter() - start

print(f"100 conversions without cache: {elapsed_no_cache*1000:.2f}ms")
print(f"100 conversions with cache:    {elapsed_with_cache*1000:.2f}ms")
print(f"Speedup: {elapsed_no_cache/elapsed_with_cache:.1f}x faster")

print()


# ============================================================================
# Example 6: Weak References (Memory Management)
# ============================================================================

print("=" * 70)
print("Example 6: Weak References (Memory Management)")
print("=" * 70)

class TemporaryModel(BaseModel):
    data: str

print("Creating conversion...")
TempClass = modict.from_model(TemporaryModel)
print(f"Class cached? {TypeCache.get_modict(TemporaryModel) is not None}")

print("\nDeleting reference to converted class...")
del TempClass

# The cache uses weak references, so the class may be garbage collected
# (In practice, Python may keep it alive longer, but the cache won't prevent GC)
import gc
gc.collect()

print("After garbage collection, cache may have cleaned up the weak reference")
print("(Actual behavior depends on Python's GC timing)")

print()


# ============================================================================
# Summary
# ============================================================================

print("=" * 70)
print("Summary")
print("=" * 70)
print("""
TypeCache provides:

1. ✅ Global caching - conversions persist across your entire Python session
2. ✅ Automatic nested caching - child models are cached when parent is converted
3. ✅ Bidirectional caching - both modict→Pydantic and Pydantic→modict
4. ✅ Memory efficient - uses weak references to allow garbage collection
5. ✅ Performance - repeated conversions are instant (cache lookup)

API:
- TypeCache.get_modict(PydanticClass) - Get cached modict class
- TypeCache.get_pydantic(ModictClass) - Get cached Pydantic class
- TypeCache.set_modict(PydanticClass, ModictClass) - Manually cache (rarely needed)
- TypeCache.set_pydantic(ModictClass, PydanticClass) - Manually cache (rarely needed)
- TypeCache.clear() - Clear all cached conversions

Note: In most cases, you don't need to interact with TypeCache directly.
It works automatically in the background when you use modict.from_model()
and YourModict.to_model().
""")
