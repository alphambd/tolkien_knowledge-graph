"""
METW Cards Integration - Debug version
"""
import json
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARDS_FILE = os.path.join(PROJECT_ROOT, "data", "cards.json")

print("=" * 70)
print("DEBUG: ANALYZING CARDS.JSON STRUCTURE")
print("=" * 70)

try:
    with open(CARDS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"✅ JSON loaded successfully")
    print(f"File size: {os.path.getsize(CARDS_FILE) / 1024:.1f} KB")

    # Check type
    print(f"Data type: {type(data)}")

    if isinstance(data, dict):
        print("\n📊 DICTIONARY STRUCTURE:")
        for key, value in data.items():
            print(f"  Key: '{key}' → Type: {type(value)}")
            if isinstance(value, list):
                print(f"    List length: {len(value)}")
                if len(value) > 0:
                    print(f"    First item type: {type(value[0])}")
                    if isinstance(value[0], dict):
                        print(f"    First item keys: {list(value[0].keys())[:5]}...")

    elif isinstance(data, list):
        print(f"\n📊 LIST STRUCTURE:")
        print(f"  Length: {len(data)}")
        if len(data) > 0:
            print(f"  First item type: {type(data[0])}")
            if isinstance(data[0], dict):
                print(f"  First item keys: {list(data[0].keys())[:10]}")
                # Show first few cards
                print(f"\n📋 SAMPLE CARDS (first 3):")
                for i, card in enumerate(data[:3], 1):
                    print(f"\n  Card {i}:")
                    for key, value in list(card.items())[:5]:  # First 5 properties
                        print(f"    {key}: {str(value)[:50]}...")

    # Count cards
    cards_count = 0
    if isinstance(data, list):
        cards_count = len(data)
    elif isinstance(data, dict) and "cards" in data:
        if isinstance(data["cards"], list):
            cards_count = len(data["cards"])

    print(f"\n🎴 TOTAL CARDS FOUND: {cards_count}")

except json.JSONDecodeError as e:
    print(f"❌ JSON parsing error: {e}")
    print("   The file might be corrupted")

    # Try to read first/last few lines
    with open(CARDS_FILE, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        print(f"\n📄 First 3 lines:")
        for i, line in enumerate(lines[:3], 1):
            print(f"  {i}: {line[:100]}...")

        print(f"\n📄 Last 3 lines:")
        for i, line in enumerate(lines[-3:], 1):
            print(f"  {i}: {line[:100]}...")

except Exception as e:
    print(f"❌ Error: {e}")

print("\n" + "=" * 70)