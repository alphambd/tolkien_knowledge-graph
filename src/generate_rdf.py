# generate_rdf_enhanced.py - Enhanced RDF Generator with WikiText cleaning
from rdflib import Graph, URIRef, Literal, Namespace, RDF, RDFS, XSD
import requests
import re
import os

# ---------------------------
# Enhanced Helper functions
# ---------------------------

def clean_wiki_text(text):
    """
    Clean WikiText markup from the input text.
    """
    if not text:
        return text

    # Remove HTML comments
    text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)

    # Remove <ref> tags and their content
    text = re.sub(r'<ref[^>]*>.*?</ref>', '', text, flags=re.DOTALL)

    # Remove remaining HTML tags but keep <br/> as separator
    text = re.sub(r'<[^>]+>', ' ', text)

    # Convert wiki links [[Link]] or [[Link|Display]] to just Display or Link
    def replace_wiki_link(match):
        link = match.group(1)
        display = match.group(2) if match.group(2) else link
        return display

    text = re.sub(r'\[\[([^\]|]+)(?:\|([^\]]+))?\]\]', replace_wiki_link, text)

    # Handle templates {{FA|532}} -> FA 532
    text = re.sub(r'\{\{([^}|]+)\|([^}]+)\}\}', r'\1 \2', text)

    # Handle simple templates {{Template}}
    text = re.sub(r'\{\{[^}]+\}\}', '', text)

    # Clean extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()

    text = re.split(r'<ref', text)[0]  # Keep only content before <ref

    return text


def parse_wiki_value_enhanced(value, namespace):
    """
    Enhanced parser that properly handles WikiText values.
    Returns either a URI for entities or a cleaned Literal.
    """
    value = value.strip()

    # Handle empty values
    if not value or value == '""':
        return None

    # Clean the value first
    cleaned_value = clean_wiki_text(value)

    # Check if this should be a URI (entity names)
    # For entity references in the text (like "[[Celebrían]]")
    # Extract potential entity names from the original value before cleaning
    entity_matches = re.findall(r'\[\[([^\]|]+)', value)

    if entity_matches:
        # If it's a simple entity reference like "[[Celebrían]]"
        if len(entity_matches) == 1 and re.fullmatch(r'\[\[[^\]]+\]\]', value.strip()):
            entity_name = entity_matches[0].strip()
            uri_name = entity_name.replace(" ", "_").replace("'", "").replace("&", "and")
            return URIRef(namespace[uri_name])

    # Check for numeric values
    if cleaned_value.isdigit():
        return Literal(cleaned_value, datatype=XSD.integer)

    # Check for boolean-like values
    if cleaned_value.lower() in ['true', 'false']:
        return Literal(cleaned_value.lower() == 'true', datatype=XSD.boolean)

    # Check for date patterns (like "29 September, TA 3021")
    date_pattern = r'(\d{1,2}\s+[A-Za-z]+,\s+[A-Za-z]+\s+\d{4})'
    if re.match(date_pattern, cleaned_value):
        return Literal(cleaned_value, datatype=XSD.string)

    # Default: string literal
    return Literal(cleaned_value)


def split_multiple_values(value):
    """
    Split values that contain multiple items separated by <br/> or commas.
    """
    if not value:
        return []

    # Split by <br/> or commas (but not within numbers like "1,234")
    splits = re.split(r'<br\s*/?>|,\s*(?![^<]*>)', value)

    # Clean each split
    result = []
    for item in splits:
        item = item.strip()
        if item and item != '""':
            # Remove trailing commas or dots
            item = re.sub(r'[.,;]$', '', item)
            result.append(item)

    return result

# ---------------------------
# Configuration
# ---------------------------
TOlkien = Namespace("http://example.org/tolkien/")
ELROND_URI = URIRef(TOlkien.Elrond)

# Use correct relative paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_FILE = os.path.join(BASE_DIR, "data", "elrond_infobox.txt")
OUTPUT_FILE = os.path.join(BASE_DIR, "data", "elrond_cleaned.ttl")
FUSEKI_ENDPOINT = "http://localhost:3030/tolkienKG"

# ---------------------------
# Create RDF graph
# ---------------------------
g = Graph()

# Bind namespaces
g.bind("tolkien", TOlkien)
g.bind("xsd", XSD)
g.bind("rdfs", RDFS)

# Check if input file exists
if not os.path.exists(INPUT_FILE):
    print("================================================================")
    print("ERROR: FILE NOT FOUND")
    print("================================================================")
    print(f"File: {INPUT_FILE}")
    print()
    print("Solution: Create the file data/elrond_infobox.txt")
    print("================================================================")
    exit(1)

print("================================================================")
print("WIKITEXT CLEANING & RDF GENERATION")
print("================================================================")
print(f"Reading file: {os.path.basename(INPUT_FILE)}")
print("Processing with advanced WikiText cleaning...")
print("================================================================")

try:
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        content = f.read()
except UnicodeDecodeError:
    with open(INPUT_FILE, "r", encoding="latin-1") as f:
        content = f.read()

# Split into lines and process
lines = content.split('\n')
triple_count = 0
skipped_count = 0

print("\nPROCESSING PROPERTIES:")
print("-" * 60)

for line in lines:
    line = line.strip()

    # Skip non-property lines
    if not line.startswith("|"):
        continue

    # Remove the leading | and split on first =
    line_content = line[1:].strip()
    if '=' not in line_content:
        continue

    parts = line_content.split('=', 1)
    if len(parts) != 2:
        continue

    field, raw_value = parts
    field = field.strip()
    raw_value = raw_value.strip()

    # Skip empty values
    if not raw_value or raw_value == '""':
        skipped_count += 1
        continue

    # Check for multiple values
    values_to_process = []
    if '<br/>' in raw_value or (',' in raw_value and len(raw_value) > 30):
        split_values = split_multiple_values(raw_value)
        values_to_process = split_values
    else:
        values_to_process = [raw_value]

    # Process each value
    for value in values_to_process:
        obj = parse_wiki_value_enhanced(value, TOlkien)

        if obj is not None:
            # Add type information for certain fields
            if field == 'age' and isinstance(obj, Literal):
                obj = Literal(str(obj), datatype=XSD.integer)
            elif field in ['gender', 'race', 'name']:
                pass

            g.add((ELROND_URI, TOlkien[field], obj))
            triple_count += 1
        else:
            skipped_count += 1

print("\nPROCESSING RESULTS:")
print("-" * 60)
print(f"RDF triples created     : {triple_count}")
print(f"Values skipped          : {skipped_count}")

# ---------------------------
# Add inferred triples
# ---------------------------
g.add((ELROND_URI, RDF.type, TOlkien.Character))
g.add((ELROND_URI, RDF.type, TOlkien.HalfElven))
g.add((ELROND_URI, RDFS.label, Literal("Elrond Half-elven")))

# ---------------------------
# Save Turtle file
# ---------------------------
output_dir = os.path.dirname(OUTPUT_FILE)
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

g.serialize(OUTPUT_FILE, format="turtle")

print("\nSAVING FILE:")
print("-" * 60)
print(f"Directory : {output_dir}")
print(f"File      : {os.path.basename(OUTPUT_FILE)}")
print(f"Size      : {os.path.getsize(OUTPUT_FILE)/1024:.1f} KB")

# ---------------------------
# Result preview
# ---------------------------
print("\nTRIPLES PREVIEW (first 10):")
print("-" * 60)

triples = list(g.triples((ELROND_URI, None, None)))
for i, (s, p, o) in enumerate(triples[:10]):
    prop_name = str(p).split('/')[-1]
    obj_str = str(o)

    # Truncate long values
    if len(obj_str) > 40:
        obj_str = obj_str[:37] + "..."

    # Format based on type
    if isinstance(o, URIRef):
        type_marker = "[URI]"
    elif isinstance(o, Literal) and o.datatype == XSD.integer:
        type_marker = "[INT]"
    else:
        type_marker = "[STR]"

    print(f"{i + 1:2}. {prop_name:20} {type_marker} {obj_str}")

if len(triples) > 10:
    print(f"... and {len(triples) - 10} more triples")

# ---------------------------
# Show cleaning examples
# ---------------------------
print("\nWIKITEXT CLEANING EXAMPLES:")
print("-" * 60)

examples = [
    ('"[[Elladan]] & [[Elrohir]] ([[twins]])<br/>[[Arwen]]"', '"Elladan & Elrohir (twins) Arwen"'),
    ('"{{FA|532}}<ref>...</ref>"', '"FA 532"'),
    ('"Grey<ref name=\"meetings\"/>"', '"Grey"'),
    ('"[[Sindarin|S]], {{IPA|[\'ɛlʲrond]}}"', '"S, IPA [\'ɛlʲrond]"'),
]

for original, cleaned in examples:
    print(f"BEFORE : {original}")
    print(f"AFTER  : {cleaned}")
    print("-" * 40)

# ---------------------------
# Optional: send to Fuseki
# ---------------------------
print("\nSENDING TO FUSEKI:")
print("-" * 60)
send_to_fuseki = input("Send cleaned RDF to Fuseki? (y/n): ").lower()

if send_to_fuseki == 'y' or send_to_fuseki == 'o':
    print("Connecting to Fuseki...")
    try:
        with open(OUTPUT_FILE, "rb") as f:
            r = requests.post(
                FUSEKI_ENDPOINT,
                data=f,
                headers={"Content-Type": "text/turtle"},
                timeout=10
            )
            if r.status_code in [200, 201, 204]:
                print("SUCCESS: RDF data added to Fuseki!")
            else:
                print(f"ERROR Fuseki: {r.status_code}")
                if len(r.text) > 0:
                    print(f"Message: {r.text[:100]}...")
    except requests.exceptions.ConnectionError:
        print("ERROR: Cannot connect to Fuseki")
        print("Make sure Fuseki is running on http://localhost:3030")
    except Exception as e:
        print(f"ERROR: {e}")
else:
    print("Transfer cancelled")

print("\n" + "=" * 60)
print("ENHANCED RDF GENERATION COMPLETED!")
print("=" * 60)