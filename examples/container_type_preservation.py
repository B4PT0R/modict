"""
Example: Container Type Preservation in Walk/Unwalk

This example demonstrates how modict preserves exact container types
when walking and unwalking nested structures.
"""

from collections import OrderedDict, UserDict, UserList
from modict._collections_utils._advanced import walk, walked, unwalk


class MyCustomDict(dict):
    """Custom dictionary with additional behavior."""
    
    def __repr__(self):
        return f"MyCustomDict({dict.__repr__(self)})"


class MyCustomList(list):
    """Custom list with additional behavior."""
    
    def __repr__(self):
        return f"MyCustomList({list.__repr__(self)})"


def main():
    print("=" * 70)
    print("Container Type Preservation Example")
    print("=" * 70)
    
    # Create a complex structure with various container types
    original = MyCustomDict({
        'users': MyCustomList([
            OrderedDict([('name', 'Alice'), ('age', 30)]),
            OrderedDict([('name', 'Bob'), ('age', 25)])
        ]),
        'config': OrderedDict([
            ('theme', 'dark'),
            ('language', 'en')
        ]),
        'data': UserDict({
            'items': UserList([1, 2, 3, 4, 5])
        })
    })
    
    print("\n1. Original structure:")
    print(f"   Root type: {type(original).__name__}")
    print(f"   users type: {type(original['users']).__name__}")
    print(f"   users[0] type: {type(original['users'][0]).__name__}")
    print(f"   config type: {type(original['config']).__name__}")
    print(f"   data type: {type(original['data']).__name__}")
    print(f"   data.items type: {type(original['data']['items']).__name__}")
    
    # Walk the structure
    print("\n2. Walking the structure:")
    walked_data = walked(original)
    
    # Show a few paths with their container classes
    print("   Sample paths with container classes:")
    for i, (path, value) in enumerate(list(walked_data.items())[:3]):
        classes = [c.container_class.__name__ for c in path.components]
        print(f"   {path}: {value}")
        print(f"      Container chain: {' → '.join(classes)}")
    
    # Unwalk to reconstruct
    print("\n3. Reconstructing from walked data:")
    reconstructed = unwalk(walked_data)
    
    print(f"   Root type: {type(reconstructed).__name__}")
    print(f"   users type: {type(reconstructed['users']).__name__}")
    print(f"   users[0] type: {type(reconstructed['users'][0]).__name__}")
    print(f"   config type: {type(reconstructed['config']).__name__}")
    print(f"   data type: {type(reconstructed['data']).__name__}")
    print(f"   data.items type: {type(reconstructed['data']['items']).__name__}")
    
    # Verify exact type preservation
    print("\n4. Verification:")
    print(f"   Root type preserved: {type(original) == type(reconstructed)}")
    print(f"   users type preserved: {type(original['users']) == type(reconstructed['users'])}")
    print(f"   users[0] type preserved: {type(original['users'][0]) == type(reconstructed['users'][0])}")
    print(f"   config type preserved: {type(original['config']) == type(reconstructed['config'])}")
    print(f"   data type preserved: {type(original['data']) == type(reconstructed['data'])}")
    print(f"   data.items type preserved: {type(original['data']['items']) == type(reconstructed['data']['items'])}")
    
    # Show that data is identical
    print("\n5. Data integrity:")
    print(f"   All values preserved: {walked(original) == walked(reconstructed)}")
    
    print("\n" + "=" * 70)
    print("✅ All container types preserved through walk/unwalk cycle!")
    print("=" * 70)


if __name__ == "__main__":
    main()
