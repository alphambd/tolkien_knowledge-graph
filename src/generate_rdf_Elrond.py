# generate_rdf_enhanced.py - Enhanced RDF Generator with WikiText cleaning and schema.org
from rdflib import Graph, URIRef, Literal, Namespace, RDF, RDFS, XSD
import requests
import re
import os

# ---------------------------
# Namespaces
# ---------------------------
SCHEMA = Namespace("http://schema.org/")
TGW = Namespace("http://tolkiengateway.net/resource/")
TGWO = Namespace("http://tolkiengateway.net/ontology/")
DCTERMS = Namespace("http://purl.org/dc/terms/")
FOAF = Namespace("http://xmlns.com/foaf/0.1/")

# Schema.org property mappings
PROPERTY_MAPPINGS = {
    "name": SCHEMA.name,
    "othernames": SCHEMA.alternateName,
    "alias": SCHEMA.alternateName,
    "title": SCHEMA.description,
    "race": SCHEMA.additionalType,
    "birth": SCHEMA.birthDate,
    "death": SCHEMA.deathDate,
    "birthplace": SCHEMA.birthPlace,
    "deathplace": SCHEMA.deathPlace,
    "realm": TGWO.realm,
    "spouse": SCHEMA.spouse,
    "children": SCHEMA.children,
    "parents": SCHEMA.parent,
    "siblings": SCHEMA.sibling,
    "height": SCHEMA.height,
    "hair": TGWO.hairColor,
    "eyes": TGWO.eyeColor,
    "gender": SCHEMA.gender,
    "weapon": TGWO.weapon,
    "age": TGWO.age,
    "image": SCHEMA.image,
    "caption": SCHEMA.caption,
}


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

    text = re.split(r'<ref', text)[0]

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


def map_field_to_schema(field_name):
    """
    Map infobox field name to schema.org property.
    """
    field_lower = field_name.lower().strip()

    # Try exact match first
    if field_lower in PROPERTY_MAPPINGS:
        return PROPERTY_MAPPINGS[field_lower]

    # Try partial matches
    for key, value in PROPERTY_MAPPINGS.items():
        if key in field_lower or field_lower in key:
            return value

    # Fallback to custom ontology
    return TGWO[field_name.replace(" ", "_")]


# ---------------------------
# Configuration
# ---------------------------
ELROND_URI = URIRef(TGW.Elrond)

# Use correct relative paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_FILE = os.path.join(BASE_DIR, "data", "elrond_infobox.txt")
OUTPUT_FILE = os.path.join(BASE_DIR, "data", "elrond_schema.ttl")
FUSEKI_ENDPOINT = "http://localhost:3030/tolkienKG"

# ---------------------------
# Create RDF graph
# ---------------------------
g = Graph()

# Bind namespaces
g.bind("schema", SCHEMA)
g.bind("tgw", TGW)
g.bind("tgwo", TGWO)
g.bind("dcterms", DCTERMS)
g.bind("foaf", FOAF)
g.bind("rdfs", RDFS)
g.bind("xsd", XSD)

# Check if input file exists
if not os.path.exists(INPUT_FILE):
    print("=" * 70)
    print("ERROR: FILE NOT FOUND")
    print("=" * 70)
    print(f"File: {INPUT_FILE}")
    print()
    print("Solution: Create the file data/elrond_infobox.txt")
    print("=" * 70)
    exit(1)

print("=" * 70)
print("WIKITEXT CLEANING & RDF GENERATION WITH SCHEMA.ORG")
print("=" * 70)
print(f"Reading file: {os.path.basename(INPUT_FILE)}")
print("Processing with advanced WikiText cleaning and schema.org alignment...")
print("=" * 70)

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
schema_properties_used = set()
custom_properties_used = set()

print("\nPROCESSING PROPERTIES WITH SCHEMA.ORG MAPPING:")
print("-" * 70)

# First add basic schema.org information
g.add((ELROND_URI, RDF.type, SCHEMA.Person))
g.add((ELROND_URI, SCHEMA.name, Literal("Elrond")))
g.add((ELROND_URI, SCHEMA.url, Literal("https://tolkiengateway.net/wiki/Elrond", datatype=XSD.anyURI)))
g.add((ELROND_URI, DCTERMS.source, Literal("Tolkien Gateway")))
g.add((ELROND_URI, TGWO.category, Literal("Character")))
g.add((ELROND_URI, RDFS.label, Literal("Elrond Half-elven")))

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

    # Map field to schema.org property
    mapped_property = map_field_to_schema(field)
    property_name = str(mapped_property).split("/")[-1]

    # Track which properties are used
    if str(mapped_property).startswith("http://schema.org/"):
        schema_properties_used.add(property_name)
    else:
        custom_properties_used.add(field)

    # Process each value
    for value in values_to_process:
        obj = parse_wiki_value_enhanced(value, TGW)

        if obj is not None:
            # Special handling for dates
            if mapped_property in [SCHEMA.birthDate, SCHEMA.deathDate]:
                # Try to extract date from value
                date_patterns = [
                    r'(\d{1,2}\s+\w+\s+\d{4})',  # 25 December 3018
                    r'(\w+\s+\d{4})',  # December 3018
                    r'(\d{4})',  # 3018
                ]

                date_value = None
                for pattern in date_patterns:
                    match = re.search(pattern, str(obj))
                    if match:
                        date_value = match.group(1)
                        break

                if date_value:
                    g.add((ELROND_URI, mapped_property, Literal(date_value)))
                else:
                    g.add((ELROND_URI, mapped_property, obj))
            else:
                g.add((ELROND_URI, mapped_property, obj))

            triple_count += 1
        else:
            skipped_count += 1

print("\nPROCESSING RESULTS:")
print("-" * 70)
print(f"RDF triples created     : {triple_count}")
print(f"Values skipped          : {skipped_count}")
print(f"Schema.org properties   : {len(schema_properties_used)}")
print(f"Custom properties       : {len(custom_properties_used)}")

# ---------------------------
# Save Turtle file
# ---------------------------
output_dir = os.path.dirname(OUTPUT_FILE)
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

g.serialize(OUTPUT_FILE, format="turtle")

print("\nSAVING FILE:")
print("-" * 70)
print(f"Directory : {output_dir}")
print(f"File      : {os.path.basename(OUTPUT_FILE)}")
print(f"Size      : {os.path.getsize(OUTPUT_FILE) / 1024:.1f} KB")

# ---------------------------
# Schema.org Statistics
# ---------------------------
print("\nSCHEMA.ORG STATISTICS:")
print("-" * 70)

if schema_properties_used:
    print("Schema.org properties used:")
    for prop in sorted(schema_properties_used):
        print(f"  • schema:{prop}")
else:
    print("No schema.org properties mapped")

if custom_properties_used:
    print("\nCustom properties used (tgwo:):")
    for prop in sorted(custom_properties_used):
        print(f"  • {prop}")

# ---------------------------
# Result preview
# ---------------------------
print("\nTRIPLES PREVIEW (first 15):")
print("-" * 70)

triples = list(g.triples((ELROND_URI, None, None)))
for i, (s, p, o) in enumerate(triples[:15]):
    # Get property namespace and name
    prop_str = str(p)
    if "schema.org" in prop_str:
        prop_display = f"schema:{prop_str.split('/')[-1]}"
        type_marker = "[SCHEMA]"
    elif "tolkiengateway.net/ontology" in prop_str:
        prop_display = f"tgwo:{prop_str.split('/')[-1]}"
        type_marker = "[CUSTOM]"
    elif "tolkiengateway.net/resource" in prop_str:
        prop_display = f"tgw:{prop_str.split('/')[-1]}"
        type_marker = "[RESOURCE]"
    else:
        prop_display = prop_str
        type_marker = "[OTHER]"

    obj_str = str(o)

    # Truncate long values
    if len(obj_str) > 40:
        obj_str = obj_str[:37] + "..."

    print(f"{i + 1:2}. {prop_display:30} {type_marker} {obj_str}")

if len(triples) > 15:
    print(f"... and {len(triples) - 15} more triples")

# ---------------------------
# Show cleaning examples
# ---------------------------
print("\nWIKITEXT CLEANING EXAMPLES:")
print("-" * 70)

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
print("-" * 70)
send_to_fuseki = input("Send cleaned RDF with schema.org to Fuseki? (y/n): ").lower()

if send_to_fuseki == 'y' or send_to_fuseki == 'o':
    print("Connecting to Fuseki...")
    try:
        with open(OUTPUT_FILE, "rb") as f:
            r = requests.post(
                FUSEKI_ENDPOINT + "/data",
                data=f,
                headers={"Content-Type": "text/turtle"},
                timeout=10
            )
            if r.status_code in [200, 201, 204]:
                print("SUCCESS: RDF data with schema.org added to Fuseki!")
                print(f"Total triples: {len(g)}")
                print(f"Schema.org triples: {len(schema_properties_used)}")
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

print("\n" + "=" * 70)
print("ENHANCED RDF GENERATION WITH SCHEMA.ORG COMPLETED!")
print("=" * 70)