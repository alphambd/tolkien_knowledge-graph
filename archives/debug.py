"""
Debug the exact structure of cards.json
"""
import json
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARDS_FILE = os.path.join(PROJECT_ROOT, "data", "cards.json")


def debug_structure(data, indent=0, max_depth=3, current_depth=0):
    """Recursively debug JSON structure."""
    if current_depth >= max_depth:
        return

    prefix = "  " * indent

    if isinstance(data, dict):
        for key, value in data.items():
            print(f"{prefix}{key}: {type(value)}", end="")

            if isinstance(value, dict):
                print(f" (dict with {len(value)} keys)")
                if len(value) > 0 and current_depth < max_depth - 1:
                    # Show first few sub-keys
                    sub_keys = list(value.keys())[:3]
                    print(f"{prefix}  sample keys: {sub_keys}")
                    if len(sub_keys) > 0:
                        debug_structure(value[sub_keys[0]], indent + 2, max_depth, current_depth + 1)
            elif isinstance(value, list):
                print(f" (list with {len(value)} items)")
                if len(value) > 0 and current_depth < max_depth - 1:
                    # Show type of first item
                    print(f"{prefix}  first item type: {type(value[0])}")
                    if isinstance(value[0], dict) and len(value[0]) > 0:
                        sample_keys = list(value[0].keys())[:3]
                        print(f"{prefix}  first item keys: {sample_keys}")
            elif isinstance(value, str):
                if len(value) > 50:
                    print(f": {value[:50]}...")
                else:
                    print(f": {value}")
            else:
                print(f": {value}")
    elif isinstance(data, list):
        print(f"{prefix}List of {len(data)} items")
        if len(data) > 0:
            print(f"{prefix}First item type: {type(data[0])}")
            if isinstance(data[0], dict):
                debug_structure(data[0], indent + 1, max_depth, current_depth + 1)


print("=" * 70)
print("DEEP STRUCTURE ANALYSIS OF CARDS.JSON")
print("=" * 70)

try:
    with open(CARDS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"\n📊 TOP LEVEL (type: {type(data)}, keys: {len(data)})")
    debug_structure(data, indent=1, max_depth=4)
    # Après la ligne "debug_structure(data, indent=1, max_depth=4)", ajoutez :
    print(f"\n🔍 EXAMINING 'context' IN EACH EXPANSION...")

    for expansion_code, expansion_data in data.items():
        if isinstance(expansion_data, dict) and 'context' in expansion_data:
            context = expansion_data['context']
            print(f"\nExpansion {expansion_code} - context type: {type(context)}")

            if isinstance(context, dict):
                print(f"  Context has {len(context)} keys")
                print(f"  Context keys: {list(context.keys())[:10]}")

                # Look for cards in context
                for key, value in context.items():
                    if isinstance(value, list):
                        print(f"    Key '{key}': list with {len(value)} items")
                        if len(value) > 0:
                            print(f"      First item type: {type(value[0])}")
                            if isinstance(value[0], dict):
                                print(f"      First item keys: {list(value[0].keys())[:5]}")
    # Let's try to find cards more aggressively
    print(f"\n🔍 SEARCHING FOR CARDS IN EXPANSIONS...")

    total_cards_found = 0
    for expansion_code, expansion_data in data.items():
        if isinstance(expansion_data, dict):
            print(f"\nExpansion: {expansion_code}")

            # Try different approaches to find cards
            card_lists = []

            # Method 1: Direct lists in expansion
            for key, value in expansion_data.items():
                if isinstance(value, list):
                    print(f"  Found list at key '{key}': {len(value)} items")
                    if len(value) > 0 and isinstance(value[0], dict):
                        print(f"    First item keys: {list(value[0].keys())[:5]}")
                        card_lists.append((key, value))

            # Count total cards
            for list_name, card_list in card_lists:
                total_cards_found += len(card_list)
                print(f"  List '{list_name}': {len(card_list)} cards")

                # Show a sample card
                if len(card_list) > 0:
                    sample = card_list[0]
                    print(f"  Sample card keys: {list(sample.keys())[:8]}")
                    for k, v in list(sample.items())[:3]:
                        print(f"    {k}: {str(v)[:50]}...")

    print(f"\n🎴 TOTAL CARDS FOUND (all methods): {total_cards_found}")

    # Alternative: try to find any list with more than 100 items
    print(f"\n🔎 LOOKING FOR LARGE LISTS (>100 items)...")


    def find_large_lists(obj, path="", results=None):
        if results is None:
            results = []

        if isinstance(obj, dict):
            for key, value in obj.items():
                new_path = f"{path}.{key}" if path else key
                find_large_lists(value, new_path, results)
        elif isinstance(obj, list):
            if len(obj) > 100:
                results.append((path, len(obj)))
                if len(obj) > 0 and isinstance(obj[0], dict):
                    print(f"  {path}: {len(obj)} items")
                    print(f"    First item keys: {list(obj[0].keys())[:6]}")
        return results


    large_lists = find_large_lists(data)
    print(f"Found {len(large_lists)} large lists")

except Exception as e:
    print(f" Error: {e}")

print("\n" + "=" * 70)