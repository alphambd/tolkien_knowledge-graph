"""
METW Cards Integration - BEAUTIFUL OUTPUT VERSION
"""
import json
import os
import re
from rdflib import Graph, URIRef, Literal, Namespace, RDF, XSD

# ---------------------------
# ANSI Colors for beautiful output
# ---------------------------
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'

def print_header(text):
    """Print a formatted header."""
    print(f"\n{Colors.BOLD}{Colors.HEADER}{'='*80}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.HEADER}{text.center(80)}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.HEADER}{'='*80}{Colors.END}")

def print_section(text):
    """Print a section title."""
    print(f"\n{Colors.BOLD}{Colors.CYAN} {text}{Colors.END}")
    print(f"{Colors.CYAN}{'─'*80}{Colors.END}")

def print_step(step_num, text):
    """Print a step with number."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}[STEP {step_num}] {text}{Colors.END}")

def print_success(text):
    """Print success message."""
    print(f"{Colors.GREEN} {text}{Colors.END}")

def print_info(text):
    """Print info message."""
    print(f"{Colors.CYAN} {text}{Colors.END}")

def print_warning(text):
    """Print warning message."""
    print(f"{Colors.YELLOW} {text}{Colors.END}")

def print_error(text):
    """Print error message."""
    print(f"{Colors.RED} {text}{Colors.END}")

def print_progress(current, total, message=""):
    """Print progress bar."""
    percent = (current / total) * 100
    bar_length = 40
    filled_length = int(bar_length * current // total)
    bar = '█' * filled_length + '░' * (bar_length - filled_length)

    if message:
        print(f"\r{Colors.CYAN}[{bar}] {percent:.1f}% - {message}{Colors.END}", end="", flush=True)
    else:
        print(f"\r{Colors.CYAN}[{bar}] {percent:.1f}%{Colors.END}", end="", flush=True)

    if current == total:
        print()

# ---------------------------
# Configuration
# ---------------------------
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARDS_FILE = os.path.join(PROJECT_ROOT, "data", "cards.json")
OUTPUT_FILE = os.path.join(PROJECT_ROOT, "data", "metw_integration_cards.ttl")

# Namespaces
SCHEMA = Namespace("http://schema.org/")
TGW = Namespace("http://tolkiengateway.net/resource/")
TGWO = Namespace("http://tolkiengateway.net/ontology/")
METW = Namespace("http://example.org/metw/")

# Expansion codes mapping
EXPANSION_NAMES = {
    "AS": "Against the Shadow",
    "BA": "The Balrog",
    "DM": "Dark Minions",
    "LE": "Legends",
    "TD": "The Dragons",
    "TW": "The Wizards",
    "WH": "White Hand"
}

# ---------------------------
# Helper Functions
# ---------------------------
def safe_uri_name(name):
    """Convert name to a URI-safe version."""
    if not name:
        return "unknown"

    safe = str(name).strip()
    special_chars = [' ', ':', '(', ')', "'", '"', '&', '/', '*', '-', ',', ';', '!', '?', '@']
    for char in special_chars:
        safe = safe.replace(char, '_')

    safe = re.sub(r'_+', '_', safe)
    safe = safe.strip('_')

    return safe if safe else "unknown"

def extract_all_cards(data):
    """Extract all cards from the correct data structure."""
    all_cards = []

    for expansion_code, expansion_data in data.items():
        if not isinstance(expansion_data, dict):
            continue

        expansion_name = EXPANSION_NAMES.get(expansion_code, expansion_code)

        # Cards are in the 'cards' dictionary
        if 'cards' in expansion_data and isinstance(expansion_data['cards'], dict):
            cards_dict = expansion_data['cards']

            for card_id, card_data in cards_dict.items():
                if isinstance(card_data, dict):
                    # Add metadata
                    card_copy = card_data.copy()
                    card_copy['_id'] = card_id
                    card_copy['_expansion'] = expansion_code
                    card_copy['_expansion_name'] = expansion_name
                    all_cards.append(card_copy)

    return all_cards

def get_card_name(card):
    """Extract card name from multilingual structure."""
    name_obj = card.get('name')

    if isinstance(name_obj, dict):
        # Try different languages in order
        for lang in ['en', 'es', 'de', 'fr', 'it']:
            if lang in name_obj:
                name = name_obj[lang]
                if name and name.strip():
                    return name.strip()

    # Fallback to any string field
    for field in ['name', 'Name', 'title', 'Title', 'cardname']:
        if field in card and isinstance(card[field], str):
            return card[field].strip()

    # Last resort: use ID
    return card.get('_id', 'Unknown Card')

# ---------------------------
# Main Integration
# ---------------------------
def integrate_metw_cards():
    print_header("INTEGRATION OF METW CARDS INTO THE KNOWLEDGE GRAPH")

    print_section(" Objective of this integration")
    print("This step links Tolkien Gateway entities with Middle Earth: The Wizards (METW) cards.")
    print("Each link created means:")
    print("  • A Tolkien entity (e.g., 'Gandalf') has a card representation")
    print("  • A card (e.g., 'Gandalf') represents a real entity")

    # Step 1: Load data
    print_step(1, "Loading METW cards data")

    try:
        with open(CARDS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)

        print_success("JSON file loaded successfully")
        print_info(f"Number of expansions found: {len(data)}")

        # Extract all cards
        all_cards = extract_all_cards(data)

        if len(all_cards) == 0:
            print_error("No cards found in the file")
            return

        print_success(f"Total number of cards extracted: {len(all_cards)}")

        # Show expansion breakdown
        print("\n Expansion breakdown:")
        expansion_counts = {}
        for card in all_cards:
            exp = card.get('_expansion', 'Unknown')
            if exp not in expansion_counts:
                expansion_counts[exp] = 0
            expansion_counts[exp] += 1

        for exp_code, count in sorted(expansion_counts.items()):
            exp_name = EXPANSION_NAMES.get(exp_code, exp_code)
            print(f"  {Colors.YELLOW}{exp_code}:{Colors.END} {exp_name:30} → {count:4} cards")

        # Show sample card
        print("\n Example card (first one):")
        sample = all_cards[0]
        card_name = get_card_name(sample)
        print(f"  {Colors.BOLD}Name:{Colors.END} {card_name}")
        print(f"  {Colors.BOLD}ID:{Colors.END} {sample.get('_id')}")
        print(
            f"  {Colors.BOLD}Expansion:{Colors.END} {sample.get('_expansion')} ({EXPANSION_NAMES.get(sample.get('_expansion', ''), '')})")
        print(f"  {Colors.BOLD}Type:{Colors.END} {sample.get('type', 'Unknown')}")

    except Exception as e:
        print_error(f"Error while loading: {e}")
        return

    # Step 2: Entity matching
    print_step(2, "Preparing matching with Tolkien entities")

    # Common Tolkien characters (expandable)
    common_entities = [
        "Elrond", "Gandalf", "Aragorn", "Frodo Baggins", "Samwise Gamgee",
        "Legolas", "Gimli", "Boromir", "Gollum", "Saruman", "Galadriel",
        "Bilbo Baggins", "Théoden", "Éowyn", "Éomer", "Faramir", "Denethor",
        "Treebeard", "Tom Bombadil", "Sauron", "Witch-king", "Balrog",
        "Celeborn", "Arwen", "Elendil", "Isildur", "Glorfindel", "Haldir",
        "Radagast", "Shelob", "Thorin Oakenshield", "Bard", "Beorn",
        "Elfhelm", "Erkenbrand", "Gamling", "Háma", "Gríma", "Wormtongue"
    ]

    print_info(f"List of {len(common_entities)} Tolkien entities for matching")
    print("The system will look for these names in the card names")

    # Step 3: Create RDF graph
    print_step(3, "Creating RDF graph using schema.org")

    g = Graph()
    g.bind("schema", SCHEMA)
    g.bind("tgw", TGW)
    g.bind("tgwo", TGWO)
    g.bind("metw", METW)

    print_success("RDF graph initialized with namespaces:")
    print(f"  • {Colors.CYAN}schema:{Colors.END} http://schema.org/ (standard vocabulary)")
    print(f"  • {Colors.CYAN}tgw:{Colors.END} http://tolkiengateway.net/resource/ (your entities)")
    print(f"  • {Colors.CYAN}tgwo:{Colors.END} http://tolkiengateway.net/ontology/ (custom vocabulary)")
    print(f"  • {Colors.CYAN}metw:{Colors.END} http://example.org/metw/ (METW cards)")

    # Step 4: Process cards
    print_step(4, f"Processing {len(all_cards)} cards")
    print("This step may take a few seconds...")

    matches_found = 0
    cards_processed = 0
    interesting_matches = []  # Store interesting matches for display

    for i, card in enumerate(all_cards):
        cards_processed += 1

        # Get card name
        card_name = get_card_name(card)

        # Create card URI
        card_uri_name = safe_uri_name(f"{card.get('_id', '')}_{card_name}")
        card_uri = URIRef(METW[card_uri_name])

        # Add card to graph
        g.add((card_uri, RDF.type, TGWO.Card))
        g.add((card_uri, RDF.type, SCHEMA.CreativeWork))
        g.add((card_uri, SCHEMA.name, Literal(card_name, lang="en")))

        # Add metadata
        if '_id' in card:
            g.add((card_uri, TGWO.cardId, Literal(card['_id'], lang="en")))
        if '_expansion' in card:
            g.add((card_uri, TGWO.expansion, Literal(card['_expansion'], lang="en")))

        # Add card type if available
        card_type = card.get('type')
        if card_type:
            g.add((card_uri, TGWO.cardType, Literal(card_type, lang="en")))

        # Try to match with Tolkien entities
        card_lower = card_name.lower()
        matched_entity = None

        for entity in common_entities:
            entity_lower = entity.lower()

            # Simple matching
            if entity_lower in card_lower or entity_lower.replace(' ', '') in card_lower.replace(' ', ''):
                matched_entity = entity
                break

        if matched_entity:
            matches_found += 1

            # Store interesting matches for display
            if matches_found <= 15:  # Keep first 15 for display
                interesting_matches.append((card_name, matched_entity))

            # Create entity URI
            entity_uri_name = safe_uri_name(matched_entity)
            entity_uri = URIRef(TGW[entity_uri_name])

            # Create links
            g.add((entity_uri, TGWO.hasCardRepresentation, card_uri))
            g.add((card_uri, TGWO.representsEntity, entity_uri))
            g.add((entity_uri, SCHEMA.relatedTo, card_uri))
            g.add((card_uri, SCHEMA.relatedTo, entity_uri))

        # Show progress every 100 cards
        if (i + 1) % 100 == 0:
            print_progress(i + 1, len(all_cards), f"{i + 1}/{len(all_cards)} cards processed")

    print_progress(len(all_cards), len(all_cards), "Processing completed!")

    # Step 5: Save results
    print_step(5, "Save results in Turtle format")

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    try:
        g.serialize(OUTPUT_FILE, format="turtle")
        file_size = os.path.getsize(OUTPUT_FILE) / 1024

        print_success(f"File saved: {OUTPUT_FILE}")
        print_info(f"File size: {file_size:.1f} KB")
        print_info(f"Number of RDF triples generated: {len(g)}")

    except Exception as e:
        print_error(f"Error while saving: {e}")
        return

    # Step 6: Beautiful statistics
    print_header(" INTEGRATION RESULTS")

    print_section("General statistics")

    # Create a nice table
    stats = [
        ("Cards processed", f"{cards_processed:,}", Colors.CYAN),
        ("Matches found", f"{matches_found:,}", Colors.GREEN),
        ("Matching rate", f"{(matches_found / cards_processed) * 100:.1f}%", Colors.YELLOW),
        ("RDF triples generated", f"{len(g):,}", Colors.BLUE),
        ("File size", f"{file_size:.1f} KB", Colors.CYAN),
    ]

    for label, value, color in stats:
        print(f"  {color}{label:25}{Colors.END}: {Colors.BOLD}{value}{Colors.END}")

    # Show interesting matches
    print_section(" Example matches found")

    if interesting_matches:
        for i, (card_name, entity) in enumerate(interesting_matches, 1):
            arrow = f"{Colors.YELLOW}→{Colors.END}"
            print(f"  {i:2}. {Colors.CYAN}{card_name:35}{Colors.END} {arrow} {Colors.GREEN}{entity}{Colors.END}")
    else:
        print("  No matches found")

    # Card type distribution
    print_section(" Card type distribution")

    type_counts = {}
    for card in all_cards:
        card_type = card.get('type')
        if card_type:
            if isinstance(card_type, str):
                if card_type not in type_counts:
                    type_counts[card_type] = 0
                type_counts[card_type] += 1

    if type_counts:
        total_cards_with_type = sum(type_counts.values())
        max_count = max(type_counts.values()) if type_counts else 1

        print(f"{Colors.CYAN}Total cards with type: {total_cards_with_type}/{len(all_cards)}{Colors.END}")

        for card_type, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / total_cards_with_type) * 100 if total_cards_with_type > 0 else 0
            bar_length = 30
            filled = int(bar_length * count / max_count) if max_count > 0 else 0
            bar = '█' * filled + '░' * (bar_length - filled)

            print(f"  {Colors.BOLD}{card_type:20}{Colors.END}: {count:4} cards {bar} {percentage:.1f}%")
    else:
        print(f"{Colors.YELLOW}No card types found in the data{Colors.END}")

    # What was created
    print_section(" What was created in the graph")

    print("For each match, 4 RDF triples were created:")
    print(f"  1. {Colors.CYAN}Entity → tgwo:hasCardRepresentation → Card{Colors.END}")
    print(f"  2. {Colors.CYAN}Card → tgwo:representsEntity → Entity{Colors.END}")
    print(f"  3. {Colors.CYAN}Entity → schema:relatedTo → Card{Colors.END}")
    print(f"  4. {Colors.CYAN}Card → schema:relatedTo → Entity{Colors.END}")

    print(f"\n{Colors.BOLD}Full example for 'Gandalf':{Colors.END}")
    print(f"  tgw:Gandalf tgwo:hasCardRepresentation metw:Gandalf_Card")
    print(f"  metw:Gandalf_Card tgwo:representsEntity tgw:Gandalf")
    print(f"  tgw:Gandalf schema:relatedTo metw:Gandalf_Card")
    print(f"  metw:Gandalf_Card schema:relatedTo tgw:Gandalf")

    # Next steps
    print_section(" Next steps")

    print("1. Load the file into Fuseki:")
    print(f"   {Colors.CYAN}curl -X POST -H \"Content-Type: text/turtle\" \\{Colors.END}")
    print(f"   {Colors.CYAN}  --data-binary @{OUTPUT_FILE} \\{Colors.END}")
    print(f"   {Colors.CYAN}  http://localhost:3030/tolkienKG/data{Colors.END}")

    print("\n2. Test with a SPARQL query:")
    print(
        f"   {Colors.YELLOW}SELECT ?entity ?card WHERE {{?entity tgwo:hasCardRepresentation ?card}} LIMIT 10{Colors.END}")

    print("\n3. Merge with your existing graph")

    print_header(" INTEGRATION SUCCESSFUL!")

    print(f"\n{Colors.GREEN} Congratulations! You successfully integrated{Colors.END}")
    print(f"{Colors.GREEN}   {matches_found} METW cards with your Tolkien entities.{Colors.END}")
    print(f"\n{Colors.BOLD}The graph is now enriched with links to the card game!{Colors.END}")


# ---------------------------
# Run
# ---------------------------
if __name__ == "__main__":
    integrate_metw_cards()
