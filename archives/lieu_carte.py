"""
Debug: Find the actual cards in cards.json
"""
import json
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARDS_FILE = os.path.join(PROJECT_ROOT, "data", "cards.json")

print("=" * 70)
print("FINDING CARDS IN THE ACTUAL STRUCTURE")
print("=" * 70)

try:
    with open(CARDS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f" JSON loaded. Top-level keys: {list(data.keys())}")

    # Let's examine one expansion in detail
    first_expansion = list(data.keys())[0]
    print(f"\n🔍 EXAMINING EXPANSION '{first_expansion}':")

    expansion_data = data[first_expansion]
    print(f"Type: {type(expansion_data)}")

    if isinstance(expansion_data, dict):
        print(f"Keys in expansion: {list(expansion_data.keys())}")

        for key, value in expansion_data.items():
            print(f"\n  Key: '{key}'")
            print(f"    Type: {type(value)}")

            if isinstance(value, str):
                if len(value) > 100:
                    print(f"    Value (first 100 chars): {value[:100]}...")
                else:
                    print(f"    Value: {value}")

            elif isinstance(value, list):
                print(f"    List length: {len(value)}")
                if len(value) > 0:
                    print(f"    First item type: {type(value[0])}")
                    if isinstance(value[0], dict):
                        print(f"    First item keys: {list(value[0].keys())[:8]}")
                        # Show a sample if it looks like a card
                        if 'name' in value[0] or 'Name' in value[0] or 'title' in value[0]:
                            print(f"    SAMPLE CARD:")
                            for k, v in list(value[0].items())[:5]:
                                print(f"      {k}: {str(v)[:50]}...")

            elif isinstance(value, dict):
                print(f"    Dict with {len(value)} keys")
                # Show first few keys
                first_keys = list(value.keys())[:5]
                print(f"    Sample keys: {first_keys}")

    # Alternative: Search recursively for cards
    print(f"\n🔎 RECURSIVE SEARCH FOR CARDS...")


    def find_cards(obj, path="", depth=0, max_depth=5):
        if depth >= max_depth:
            return []

        cards = []

        if isinstance(obj, dict):
            # Check if this looks like a card
            if ('name' in obj or 'Name' in obj or 'title' in obj) and len(obj) > 2:
                cards.append((path, obj))

            # Recursively search
            for key, value in obj.items():
                new_path = f"{path}.{key}" if path else key
                cards.extend(find_cards(value, new_path, depth + 1, max_depth))

        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                new_path = f"{path}[{i}]"
                cards.extend(find_cards(item, new_path, depth + 1, max_depth))

        return cards


    cards_found = find_cards(data)
    print(f"Found {len(cards_found)} potential cards")

    if cards_found:
        print(f"\n📋 SAMPLE CARDS (first 3):")
        for i, (path, card) in enumerate(cards_found[:3], 1):
            print(f"\n  Card {i} at path: {path}")
            for key, value in list(card.items())[:6]:
                print(f"    {key}: {str(value)[:50]}...")

    # Let's also count all lists that might contain cards
    print(f"\n📊 COUNTING ALL LISTS IN THE STRUCTURE...")


    def count_lists(obj, depth=0, max_depth=4):
        counts = {}

        if depth >= max_depth:
            return counts

        if isinstance(obj, dict):
            for key, value in obj.items():
                if isinstance(value, list):
                    if key not in counts:
                        counts[key] = 0
                    counts[key] += len(value)

                    # Recursively count in list items
                    if len(value) > 0 and depth < max_depth - 1:
                        for item in value[:2]:  # Just first 2 items
                            sub_counts = count_lists(item, depth + 1, max_depth)
                            for sub_key, sub_count in sub_counts.items():
                                if sub_key not in counts:
                                    counts[sub_key] = 0
                                counts[sub_key] += sub_count

        elif isinstance(obj, list):
            for item in obj:
                sub_counts = count_lists(item, depth + 1, max_depth)
                for sub_key, sub_count in sub_counts.items():
                    if sub_key not in counts:
                        counts[sub_key] = 0
                    counts[sub_key] += sub_count

        return counts


    list_counts = count_lists(data)
    print(f"List counts by key:")
    for key, count in sorted(list_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"  {key}: {count} items")

except Exception as e:
    print(f" Error: {e}")
    import traceback

    traceback.print_exc()

print("\n" + "=" * 70)