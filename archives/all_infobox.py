"""
Tolkien Gateway - Complete Infobox Extractor
Extracts ALL infobox templates with proper RDF generation aligned with schema.org
"""
import requests
import re
import os
import time
import json
from datetime import datetime
from rdflib import Graph, URIRef, Literal, Namespace, RDF, RDFS, XSD

# ---------------------------
# Configuration
# ---------------------------
API_URL = "https://tolkiengateway.net/w/api.php"
#FUSEKI_ENDPOINT = "http://localhost:3030/tolkienKG/update"  # Changed to /update
FUSEKI_ENDPOINT = None  # Fuseki disabled

# ---------------------------
# Namespaces
# ---------------------------
SCHEMA = Namespace("http://schema.org/")
TGW = Namespace("http://tolkiengateway.net/resource/")
TGWO = Namespace("http://tolkiengateway.net/ontology/")
DCTERMS = Namespace("http://purl.org/dc/terms/")
FOAF = Namespace("http://xmlns.com/foaf/0.1/")
DBO = Namespace("http://dbpedia.org/ontology/")  # Alternative to schema.org

# Choose schema.org or DBpedia (as per project requirements)
# We'll use schema.org as requested
MAIN_ONTOLOGY = SCHEMA

# ---------------------------
# Category to Schema.org Mapping
# ---------------------------
CATEGORY_TO_SCHEMA = {
    "Character": SCHEMA.Person,
    "Location": SCHEMA.Place,
    "Item": SCHEMA.Thing,
    "Event": SCHEMA.Event,
    "Organization": SCHEMA.Organization,
    "Media": SCHEMA.MediaObject,
    "Book": SCHEMA.Book,
    "Film": SCHEMA.Movie,
    "Race": SCHEMA.Person,  # Or create custom class
    "Other": SCHEMA.Thing
}

# ---------------------------
# Property Mappings to Schema.org
# ---------------------------
PROPERTY_MAPPINGS = {
    # Common properties
    "name": SCHEMA.name,
    "title": SCHEMA.name,
    "othernames": SCHEMA.alternateName,
    "alias": SCHEMA.alternateName,
    "image": SCHEMA.image,
    "caption": SCHEMA.caption,
    "description": SCHEMA.description,
    "type": SCHEMA.additionalType,

    # Character properties
    "birth": SCHEMA.birthDate,
    "death": SCHEMA.deathDate,
    "race": TGWO.race,
    "spouse": SCHEMA.spouse,
    "children": SCHEMA.children,
    "height": SCHEMA.height,
    "hair": TGWO.hairColor,
    "eyes": TGWO.eyeColor,
    "age": TGWO.age,
    "birthplace": SCHEMA.birthPlace,
    "deathplace": SCHEMA.deathPlace,
    "realm": TGWO.realm,
    "weapon": TGWO.weapon,

    # Location properties
    "location": SCHEMA.location,
    "inhabitants": TGWO.inhabitedBy,
    "events": SCHEMA.event,
    "builder": SCHEMA.creator,
    "built": SCHEMA.foundingDate,
    "destroyed": TGWO.destroyedDate,
    "type": SCHEMA.additionalType,

    # Item/Book/Film properties
    "author": SCHEMA.author,
    "artist": SCHEMA.creator,
    "director": SCHEMA.director,
    "publisher": SCHEMA.publisher,
    "release": SCHEMA.datePublished,
    "language": SCHEMA.inLanguage,
    "pages": SCHEMA.numberOfPages,

    # Event properties
    "date": SCHEMA.startDate,
    "enddate": SCHEMA.endDate,
    "participants": SCHEMA.participant,
    "outcome": TGWO.outcome,
}


# ---------------------------
# Utility Functions
# ---------------------------
def safe_uri_name(name):
    """Convert any name to a safe URI fragment."""
    if not name:
        return "unknown"

    safe = str(name).strip()

    # Remove Template: prefix if present
    if safe.startswith("Template:"):
        safe = safe[9:].strip()

    # Remove parenthetical disambiguation
    if " (" in safe and safe.endswith(")"):
        safe = safe.split(" (")[0].strip()

    # Replace problematic characters
    for char in ['"', "'", " ", ":", "(", ")", "[", "]", "{", "}",
                 "|", "\\", "/", "#", ",", ";", ".", "!", "?", "@",
                 "&", "=", "+", "$", "%", "*", "~", "`", "^"]:
        safe = safe.replace(char, "_")

    # Collapse multiple underscores
    safe = re.sub(r"_+", "_", safe)
    safe = safe.strip("_")

    return safe if safe else "unknown"


def clean_wikitext_value(value):
    """Clean wikitext values thoroughly."""
    if not value:
        return ""

    # Remove HTML comments
    value = re.sub(r'<!--.*?-->', '', value, flags=re.DOTALL)

    # Handle internal links [[Page|Display]] -> Display or Page
    def replace_link(match):
        page = match.group(1).strip()
        display = match.group(2).strip() if match.group(2) else page
        return display

    value = re.sub(r'\[\[([^\]|]+)(?:\|([^\]]+))?\]\]', replace_link, value)

    # Remove external links [URL text] -> text
    value = re.sub(r'\[https?://[^\s]+ ([^\]]+)\]', r'\1', value)
    value = re.sub(r'\[https?://[^\]]+\]', '', value)

    # Remove templates {{...}} but keep the content
    value = re.sub(r'\{\{[^}]*\}\}', '', value)

    # Remove file links [[File:...]]
    value = re.sub(r'\[\[(File|Image|Media):[^\]]+\]\]', '', value, flags=re.IGNORECASE)

    # Remove ref tags <ref>...</ref>
    value = re.sub(r'<ref[^>]*>.*?</ref>', '', value, flags=re.DOTALL)
    value = re.sub(r'<ref[^/]*/>', '', value)

    # Remove other HTML tags but keep content
    value = re.sub(r'<[^>]+>', '', value)

    # Remove leading/trailing quotes and braces
    value = value.strip('"\'{}[]()')

    # Clean whitespace
    value = ' '.join(value.split())

    return value.strip()


def extract_links_from_value(value):
    """Extract page links from wikitext value."""
    links = []
    # Match [[Page]] or [[Page|Display]]
    matches = re.findall(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]', value)
    for match in matches:
        link = clean_wikitext_value(match).strip()
        if link and link not in links:
            links.append(link)
    return links


def get_date_from_value(value):
    """Try to extract a date from a value."""
    # Common date patterns in Tolkien Gateway
    patterns = [
        r'(\d{1,2}\s+\w+\s+\d{4})',  # 25 December 3018
        r'(\w+\s+\d{4})',  # December 3018
        r'(\d{4})',  # 3018
        r'(\d{1,2}\s+\w+)',  # 25 December
    ]

    for pattern in patterns:
        match = re.search(pattern, value)
        if match:
            return match.group(1)

    return None


# ---------------------------
# MediaWiki API Functions
# ---------------------------
def get_all_infobox_templates():
    """Get ALL templates from Category:Infobox templates."""
    print("Fetching all infobox templates from Category:Infobox templates...")

    templates = []
    continue_param = None

    try:
        while True:
            params = {
                "action": "query",
                "list": "categorymembers",
                "cmtitle": "Category:Infobox templates",
                "cmlimit": "500",
                "format": "json"
            }

            if continue_param:
                params["cmcontinue"] = continue_param

            response = requests.get(API_URL, params=params, timeout=30)

            if response.status_code != 200:
                print(f"Error fetching templates: HTTP {response.status_code}")
                break

            data = response.json()

            if "query" in data:
                members = data["query"]["categorymembers"]
                for member in members:
                    title = member["title"]
                    if title.startswith("Template:Infobox"):
                        templates.append(title)

                print(f"  Found {len(templates)} templates so far...")

            # Check if there are more pages
            if "continue" in data and "cmcontinue" in data["continue"]:
                continue_param = data["continue"]["cmcontinue"]
                time.sleep(0.5)  # Be polite to the API
            else:
                break

    except Exception as e:
        print(f"Error in get_all_infobox_templates: {e}")

    # Filter templates
    filtered_templates = []
    skip_keywords = ['User:', 'User talk:', 'Template talk:', '/test', '/Test', '/sandbox']

    for template in templates:
        # Skip user templates and test templates
        if not any(keyword in template for keyword in skip_keywords):
            filtered_templates.append(template)

    print(f"\nTotal infobox templates found: {len(filtered_templates)}")
    filtered_templates.sort()

    # Display sample
    print("\nSample templates:")
    for i, template in enumerate(filtered_templates[:10]):
        print(f"  {i + 1}. {template}")
    if len(filtered_templates) > 10:
        print(f"  ... and {len(filtered_templates) - 10} more")

    return filtered_templates


def test_template_has_pages(template_name, test_limit=3):
    """Test if a template actually has pages that use it."""
    try:
        params = {
            "action": "query",
            "generator": "embeddedin",
            "geititle": template_name,
            "geilimit": str(test_limit),
            "geinamespace": "0",
            "prop": "info",
            "format": "json",
        }

        response = requests.get(API_URL, params=params, timeout=15)
        if response.status_code != 200:
            return False

        data = response.json()
        return "query" in data and "pages" in data["query"] and len(data["query"]["pages"]) > 0

    except Exception:
        return False


def get_pages_for_template(template_name, limit=100):
    """Get pages using a template with pagination."""
    pages = []
    continue_param = None

    print(f"  Searching: {template_name}")

    try:
        while len(pages) < limit:
            params = {
                "action": "query",
                "generator": "embeddedin",
                "geititle": template_name,
                "geilimit": "max",
                "geinamespace": "0",
                "prop": "info",
                "format": "json",
            }

            if continue_param:
                params["geicontinue"] = continue_param

            response = requests.get(API_URL, params=params, timeout=30)
            if response.status_code != 200:
                break

            data = response.json()

            if "query" in data:
                batch_pages = data["query"]["pages"]
                for page_id, page_info in batch_pages.items():
                    if "missing" not in page_info:
                        pages.append(page_info["title"])

                if len(pages) % 50 == 0:
                    print(f"    Found {len(pages)} pages so far...")

            # Check for more pages
            if "continue" in data and "geicontinue" in data["continue"]:
                continue_param = data["continue"]["geicontinue"]
                time.sleep(0.3)
            else:
                break

            if len(pages) >= limit:
                break

    except Exception as e:
        print(f"    Error: {e}")

    print(f"    Total found: {len(pages)} pages")
    return pages[:limit]


def get_page_content(page_title):
    """Get page content with wikitext."""
    try:
        params = {
            "action": "parse",
            "page": page_title,
            "prop": "wikitext",
            "format": "json",
        }

        response = requests.get(API_URL, params=params, timeout=15)
        if response.status_code != 200:
            return ""

        data = response.json()
        if "parse" in data and "wikitext" in data["parse"]:
            return data["parse"]["wikitext"]["*"]

    except Exception as e:
        print(f"    Error getting content for {page_title}: {e}")

    return ""


# ---------------------------
# Template Extraction with mwparserfromhell
# ---------------------------
def extract_template_with_mwparser(wikitext, template_name):
    """Extract template using mwparserfromhell."""
    try:
        import mwparserfromhell

        wikicode = mwparserfromhell.parse(wikitext)
        template_short = template_name.replace("Template:", "")

        # Chercher toutes les occurrences du template
        for template in wikicode.filter_templates():
            current_name = str(template.name).strip()

            # Comparaison flexible des noms de template
            comparison_names = [
                current_name.lower(),
                current_name.lower().replace("infobox ", ""),
                template_short.lower(),
                template_short.lower().replace("infobox ", ""),
            ]

            # Vérifier si c'est le bon template
            is_target = any(
                name in comparison_names for name in [
                    template_short.lower(),
                    template_short.lower().replace("infobox ", "")
                ]
            ) or any(
                template_short.lower() in name for name in comparison_names
            )

            if is_target:
                properties = {}

                # Extraire tous les paramètres
                for param in template.params:
                    param_name = str(param.name).strip()
                    param_value = str(param.value).strip()

                    if param_name and param_value:
                        # Ignorer les paramètres numérotés (ex: |1=, |2=)
                        if not param_name.isdigit():
                            clean_name = clean_wikitext_value(param_name)
                            clean_value = clean_wikitext_value(param_value)

                            if clean_name and clean_value:
                                properties[clean_name] = clean_value

                return properties

    except ImportError:
        print("    WARNING: mwparserfromhell not installed, using regex fallback")
        return extract_template_simple_fallback(wikitext, template_name)
    except Exception as e:
        print(f"    Parser error: {e}")

    return {}


def extract_template_simple_fallback(wikitext, template_name):
    """Fallback extraction if mwparserfromhell is not available."""
    template_short = template_name.replace("Template:", "")

    # Try to find the template
    patterns = [
        rf'\{{{{\s*{re.escape(template_short)}\s*\|([^{{}}]+(?:\{{{{[^{{}}]*?\}}}}\s*)*[^{{}}]*?)}}}}',
        rf'\{{{{\s*{re.escape(template_short.lower())}\s*\|([^{{}}]+(?:\{{{{[^{{}}]*?\}}}}\s*)*[^{{}}]*?)}}}}',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, wikitext, re.IGNORECASE | re.DOTALL)
        if matches:
            template_content = matches[0]

            # Parse parameters
            properties = {}
            lines = template_content.split('\n')

            for line in lines:
                line = line.strip()
                if line.startswith('|') and '=' in line:
                    line = line[1:]  # Remove leading |
                    parts = line.split('=', 1)
                    if len(parts) == 2:
                        key = parts[0].strip()
                        value = parts[1].strip()

                        if key and value:
                            clean_key = clean_wikitext_value(key)
                            clean_value = clean_wikitext_value(value)
                            if clean_key and clean_value:
                                properties[clean_key] = clean_value

            return properties

    return {}


# ---------------------------
# Categorization and RDF Generation
# ---------------------------
def categorize_template(template_name):
    """Categorize template based on its name."""
    template_lower = template_name.lower()

    # Check in order of specificity
    if any(x in template_lower for x in ['character', 'person', 'elf', 'dwarf', 'hobbit',
                                         'orc', 'troll', 'valar', 'maiar', 'wizard', 'king']):
        return "Character"
    elif any(x in template_lower for x in ['location', 'place', 'city', 'country', 'kingdom',
                                           'realm', 'region', 'forest', 'mountain', 'river']):
        return "Location"
    elif any(x in template_lower for x in ['book', 'novel', 'publication']):
        return "Book"
    elif any(x in template_lower for x in ['film', 'movie', 'video']):
        return "Film"
    elif any(x in template_lower for x in ['event', 'battle', 'war', 'campaign', 'feast']):
        return "Event"
    elif any(x in template_lower for x in ['organization', 'company', 'society', 'guild']):
        return "Organization"
    elif any(x in template_lower for x in ['race', 'species', 'people', 'culture']):
        return "Race"
    elif any(x in template_lower for x in ['item', 'object', 'artifact', 'weapon', 'ring']):
        return "Item"
    elif any(x in template_lower for x in ['media', 'audio', 'song', 'music', 'album']):
        return "Media"
    else:
        return "Other"


def add_to_graph(graph, page_title, template_name, properties):
    """Add data to RDF graph with schema.org alignment."""
    if not properties:
        return False

    try:
        # Create URIs
        page_uri = URIRef(TGW[safe_uri_name(page_title)])
        page_url = f"https://tolkiengateway.net/wiki/{page_title.replace(' ', '_')}"

        # Add basic info
        graph.add((page_uri, RDF.type, SCHEMA.Thing))
        graph.add((page_uri, SCHEMA.name, Literal(page_title)))
        graph.add((page_uri, SCHEMA.url, Literal(page_url, datatype=XSD.anyURI)))
        graph.add((page_uri, DCTERMS.source, Literal("Tolkien Gateway")))

        # Add template info
        template_clean = template_name.replace("Template:", "")
        graph.add((page_uri, TGWO.usesTemplate, Literal(template_clean)))

        # Add type based on template category
        category = categorize_template(template_name)
        schema_class = CATEGORY_TO_SCHEMA.get(category, SCHEMA.Thing)
        graph.add((page_uri, RDF.type, schema_class))

        # Also add custom category property
        graph.add((page_uri, TGWO.category, Literal(category)))

        # Process properties
        for prop_name, prop_value in properties.items():
            if not prop_value or prop_value.lower() in ['unknown', 'none', '?', '']:
                continue

            # Clean the property name
            prop_name_lower = prop_name.lower().strip()

            # Try to map to schema.org
            mapped_prop = None
            for key, value in PROPERTY_MAPPINGS.items():
                if key in prop_name_lower or prop_name_lower in key:
                    mapped_prop = value
                    break

            if mapped_prop:
                # Special handling for dates
                if mapped_prop in [SCHEMA.birthDate, SCHEMA.deathDate, SCHEMA.startDate,
                                   SCHEMA.endDate, SCHEMA.datePublished]:
                    date_value = get_date_from_value(prop_value)
                    if date_value:
                        graph.add((page_uri, mapped_prop, Literal(date_value)))
                    else:
                        graph.add((page_uri, mapped_prop, Literal(prop_value)))
                else:
                    graph.add((page_uri, mapped_prop, Literal(prop_value)))
            else:
                # Fallback: use custom ontology
                safe_prop = safe_uri_name(prop_name)
                graph.add((page_uri, TGWO[safe_prop], Literal(prop_value)))

        # Extract and add links to other pages
        all_values = list(properties.values())
        for prop_value in all_values:
            links = extract_links_from_value(prop_value)
            for link in links:
                if link and link != page_title:
                    link_uri = URIRef(TGW[safe_uri_name(link)])
                    # Add bidirectional relationship
                    graph.add((page_uri, SCHEMA.relatedTo, link_uri))
                    graph.add((link_uri, SCHEMA.relatedTo, page_uri))

        return True

    except Exception as e:
        print(f"    Error adding to graph: {e}")
        return False


# ---------------------------
# Save and Export Functions
# ---------------------------
def save_graph(graph, filename):
    """Save graph to Turtle file."""
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(filename), exist_ok=True)

        # Serialize to Turtle
        graph.serialize(filename, format="turtle")
        file_size = os.path.getsize(filename) / 1024

        print(f"\n✓ Saved: {filename}")
        print(f"  Size: {file_size:.1f} KB")
        print(f"  Triples: {len(graph)}")

        return True
    except Exception as e:
        print(f"✗ Error saving graph: {e}")
        return False


def send_to_fuseki(graph, endpoint):
    """Send graph to Fuseki triplestore."""

    if endpoint is None:
        print("⚠️  Fuseki upload disabled (endpoint is None)")
        return False
    try:
        # Convert graph to Turtle
        ttl_data = graph.serialize(format="turtle")

        # Send to Fuseki
        headers = {
            "Content-Type": "application/x-turtle"
        }

        response = requests.post(
            endpoint,
            data=ttl_data,
            headers=headers,
            timeout=60
        )

        if response.status_code in [200, 201, 204]:
            print(f"✓ Successfully sent to Fuseki!")
            return True
        else:
            print(f"✗ Fuseki error: {response.status_code}")
            print(f"  Response: {response.text[:200]}")
            return False

    except Exception as e:
        print(f"✗ Could not send to Fuseki: {e}")
        return False


def save_by_category(graph, base_dir="data/categories"):
    """Save graph by category for better organization."""
    os.makedirs(base_dir, exist_ok=True)

    print("\nSaving data by category...")

    for category, schema_class in CATEGORY_TO_SCHEMA.items():
        category_graph = Graph()

        # Bind namespaces
        category_graph.bind("schema", SCHEMA)
        category_graph.bind("tgw", TGW)
        category_graph.bind("tgwo", TGWO)

        # Find all entities of this category
        entities = set()
        for s, p, o in graph.triples((None, RDF.type, schema_class)):
            entities.add(s)

        # Add all triples for these entities
        for entity in entities:
            for s, p, o in graph.triples((entity, None, None)):
                category_graph.add((s, p, o))

        if len(category_graph) > 0:
            filename = os.path.join(base_dir, f"{category.lower()}.ttl")
            category_graph.serialize(filename, format="turtle")
            print(f"  ✓ {category}: {len(category_graph)} triples")


# ---------------------------
# Main Program
# ---------------------------
def main():
    print("=" * 70)
    print("TOLKIEN GATEWAY - COMPLETE INFOBOX EXTRACTOR")
    print("=" * 70)
    print("Using schema.org ontology for RDF generation")
    print("=" * 70)

    # Check for mwparserfromhell
    try:
        import mwparserfromhell
        print("✓ mwparserfromhell is available")
    except ImportError:
        print("⚠️  WARNING: mwparserfromhell not installed")
        print("   Install with: pip install mwparserfromhell")
        print("   Using regex fallback (less accurate)")

    # Step 1: Get ALL infobox templates
    print("\n[1/4] Fetching infobox templates...")
    all_templates = get_all_infobox_templates()

    if not all_templates:
        print("ERROR: No templates found!")
        return

    # Step 2: Test which templates have pages
    print("\n[2/4] Testing templates...")
    working_templates = []
    failed_templates = []

    for i, template in enumerate(all_templates, 1):
        print(f"[{i}/{len(all_templates)}] Testing: {template}")

        if test_template_has_pages(template):
            working_templates.append(template)
            print(f"  ✓ Has pages")
        else:
            failed_templates.append(template)
            print(f"  ✗ No pages found")

        time.sleep(0.2)

    print(f"\nTemplate summary:")
    print(f"  Working templates: {len(working_templates)}")
    print(f"  Empty templates: {len(failed_templates)}")

    if not working_templates:
        print("ERROR: No working templates found!")
        return

    # Categorize working templates
    categorized = {}
    for template in working_templates:
        category = categorize_template(template)
        if category not in categorized:
            categorized[category] = []
        categorized[category].append(template)

    # Display categorized templates
    print("\n" + "=" * 70)
    print("WORKING TEMPLATES BY CATEGORY:")
    print("=" * 70)

    for category in sorted(categorized.keys()):
        templates = categorized[category]
        print(f"\n{category} ({len(templates)}):")
        for template in sorted(templates)[:5]:  # Show first 5
            print(f"  • {template}")
        if len(templates) > 5:
            print(f"  ... and {len(templates) - 5} more")

    # Step 3: Initialize RDF graph
    print("\n[3/4] Initializing RDF graph...")
    graph = Graph()

    # Bind namespaces
    graph.bind("schema", SCHEMA)
    graph.bind("tgw", TGW)
    graph.bind("tgwo", TGWO)
    graph.bind("dcterms", DCTERMS)
    graph.bind("foaf", FOAF)
    graph.bind("rdfs", RDFS)
    graph.bind("xsd", XSD)

    # Add ontology declarations
    for category, schema_class in CATEGORY_TO_SCHEMA.items():
        graph.add((schema_class, RDFS.subClassOf, SCHEMA.Thing))
        graph.add((schema_class, RDFS.label, Literal(f"{category}")))
        graph.add((schema_class, RDFS.comment,
                   Literal(f"A {category.lower()} from Tolkien's legendarium")))

    # Step 4: Process templates and extract data
    print("\n[4/4] Extracting data from pages...")
    print("=" * 70)

    start_time = time.time()
    total_pages = 0
    total_successful = 0
    processed_pages = set()  # To avoid duplicates

    # Process each working template
    for template_idx, template_name in enumerate(working_templates, 1):
        category = categorize_template(template_name)

        print(f"\n[{template_idx}/{len(working_templates)}] {template_name}")
        print(f"  Category: {category}")

        # Get pages for this template
        pages = get_pages_for_template(template_name, limit=50)  # Limit for testing

        if not pages:
            print(f"    No pages found (skipping)")
            continue

        print(f"    Processing {len(pages)} pages...")

        template_success = 0

        for page_idx, page_title in enumerate(pages, 1):
            # Skip if already processed
            if page_title in processed_pages:
                continue

            processed_pages.add(page_title)

            if page_idx % 10 == 0 or page_idx == 1 or page_idx == len(pages):
                print(f"      Page {page_idx}/{len(pages)}: {page_title[:40]}...")

            # Get page content
            wikitext = get_page_content(page_title)
            if not wikitext:
                continue

            total_pages += 1

            # Extract template data
            properties = extract_template_with_mwparser(wikitext, template_name)

            if properties:
                if add_to_graph(graph, page_title, template_name, properties):
                    total_successful += 1
                    template_success += 1

            # Be polite to the API
            time.sleep(0.1)

        print(f"    {template_success}/{len(pages)} successful extractions")

    elapsed = time.time() - start_time

    # Summary
    print(f"\n" + "=" * 70)
    print("EXTRACTION SUMMARY")
    print("=" * 70)

    print(f"\nResults:")
    print(f"  Total templates found: {len(all_templates)}")
    print(f"  Working templates processed: {len(working_templates)}")
    print(f"  Empty templates skipped: {len(failed_templates)}")
    print(f"  Unique pages processed: {len(processed_pages)}")
    print(f"  Successful extractions: {total_successful}")
    print(f"  RDF triples generated: {len(graph)}")
    print(f"  Time elapsed: {elapsed:.1f}s ({elapsed / 60:.1f}min)")

    # Save results
    if len(graph) > 0:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = "data"

        # Main graph
        main_filename = f"{output_dir}/tolkien_graph_{timestamp}.ttl"
        save_graph(graph, main_filename)

        # By category
        save_by_category(graph, f"{output_dir}/categories")

        # Template list
        template_list_file = f"{output_dir}/templates_used_{timestamp}.txt"
        with open(template_list_file, "w", encoding="utf-8") as f:
            f.write("WORKING TEMPLATES:\n")
            for template in working_templates:
                category = categorize_template(template)
                f.write(f"{template} [{category}]\n")
            f.write(f"\nTotal: {len(working_templates)} templates\n")

        print(f"\n✓ Template list saved: {template_list_file}")

        # COMMENTÉ: Send to Fuseki
        # print("\n" + "=" * 70)
        # print("SENDING TO FUSEKI")
        # print("=" * 70)
        #
        # if send_to_fuseki(graph, FUSEKI_ENDPOINT):
        #     print("\n✅ EXTRACTION COMPLETE!")
        #     print(f"   Graph saved to: {main_filename}")
        #     print(f"   Total triples: {len(graph)}")
        #     print(f"   Fuseki endpoint: {FUSEKI_ENDPOINT.replace('/update', '')}")
        # else:
        #     print("\n⚠️  Extraction complete but Fuseki upload failed")
        #     print(f"   Graph saved to: {main_filename}")

    else:
        print("\n❌ NO DATA EXTRACTED!")
        print("   Check your internet connection and API access.")

    print("\n" + "=" * 70)
    print("DONE!")
    print("=" * 70)


# ---------------------------
# Run the program
# ---------------------------
if __name__ == "__main__":
    # Create data directory
    os.makedirs("data", exist_ok=True)
    os.makedirs("data/categories", exist_ok=True)

    # Run main program
    main()