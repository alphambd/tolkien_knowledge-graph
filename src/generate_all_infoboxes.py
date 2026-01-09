"""
Tolkien Gateway - Infobox Extractor with schema.org integration
Extracts ALL infobox templates with proper schema.org RDF generation
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
FUSEKI_ENDPOINT = "http://localhost:3030/tolkienKG"  # Keep for optional use

# ---------------------------
# Namespaces (schema.org focused)
# ---------------------------
SCHEMA = Namespace("http://schema.org/")
TGW = Namespace("http://tolkiengateway.net/resource/")
TGWO = Namespace("http://tolkiengateway.net/ontology/")
DCTERMS = Namespace("http://purl.org/dc/terms/")
FOAF = Namespace("http://xmlns.com/foaf/0.1/")
RDF = RDF
RDFS = RDFS
XSD = XSD

# ---------------------------
# Schema.org Mappings
# ---------------------------

# Template category to schema.org class mapping
CATEGORY_TO_SCHEMA = {
    "Character": SCHEMA.Person,
    "Location": SCHEMA.Place,
    "Item": SCHEMA.Product,  # Changed from Thing to Product for collectibles
    "Book": SCHEMA.Book,
    "Film": SCHEMA.Movie,
    "Event": SCHEMA.Event,
    "Organization": SCHEMA.Organization,
    "Media": SCHEMA.MediaObject,
    "Race": SCHEMA.Person,
    "Chapter": SCHEMA.CreativeWork,  # NEW: For chapters, scenes
    "Song": SCHEMA.MusicComposition,  # NEW
    "Album": SCHEMA.MusicAlbum,  # NEW
    "Game": SCHEMA.Game,  # NEW: For video/board games
    "Website": SCHEMA.WebSite,  # NEW
    "Journal": SCHEMA.Periodical,  # NEW
    "Other": SCHEMA.Thing  # Default fallback
}

# Property mappings from infobox fields to schema.org
PROPERTY_MAPPINGS = {
    # Universal properties
    "name": SCHEMA.name,
    "title": SCHEMA.name,
    "fullname": SCHEMA.name,
    "image": SCHEMA.image,
    "caption": SCHEMA.caption,
    "description": SCHEMA.description,
    "type": SCHEMA.additionalType,
    "url": SCHEMA.url,

    # Character specific
    "othernames": SCHEMA.alternateName,
    "alias": SCHEMA.alternateName,
    "birth": SCHEMA.birthDate,
    "death": SCHEMA.deathDate,
    "birthplace": SCHEMA.birthPlace,
    "deathplace": SCHEMA.deathPlace,
    "spouse": SCHEMA.spouse,
    "children": SCHEMA.children,
    "parents": SCHEMA.parent,
    "siblings": SCHEMA.sibling,
    "height": SCHEMA.height,
    "age": SCHEMA.age,
    "gender": SCHEMA.gender,
    "race": SCHEMA.additionalType,
    "realm": SCHEMA.workLocation,
    "weapon": SCHEMA.equipment,
    "hair": TGWO.hairColor,
    "eyes": TGWO.eyeColor,

    # Location specific
    "location": SCHEMA.location,
    "region": SCHEMA.containedInPlace,
    "inhabitants": SCHEMA.person,
    "events": SCHEMA.event,
    "builder": SCHEMA.creator,
    "built": SCHEMA.foundingDate,
    "destroyed": SCHEMA.dissolutionDate,

    # Book/Film specific
    "author": SCHEMA.author,
    "artist": SCHEMA.creator,
    "director": SCHEMA.director,
    "publisher": SCHEMA.publisher,
    "released": SCHEMA.datePublished,
    "release": SCHEMA.datePublished,
    "language": SCHEMA.inLanguage,
    "pages": SCHEMA.numberOfPages,
    "isbn": SCHEMA.isbn,

    # Song/Album specific
    "composer": SCHEMA.composer,
    "lyricist": SCHEMA.lyricist,
    "performer": SCHEMA.performer,
    "duration": SCHEMA.duration,
    "genre": SCHEMA.genre,
    "tracklist": SCHEMA.track,

    # Game specific
    "designer": SCHEMA.creator,
    "players": SCHEMA.numberOfPlayers,
    "playingtime": SCHEMA.timeRequired,
    "ages": SCHEMA.suggestedMinAge,

    # Website/Journal specific
    "editor": SCHEMA.editor,
    "issn": SCHEMA.issn,
    "frequency": SCHEMA.frequency,

    # Event specific
    "date": SCHEMA.startDate,
    "enddate": SCHEMA.endDate,
    "participants": SCHEMA.participant,
    "outcome": SCHEMA.result,
}


# ---------------------------
# Utility Functions (updated for schema.org)
# ---------------------------
def safe_uri_name(name):
    """Convert any name to a safe URI fragment."""
    if not name:
        return "unknown"
    safe = str(name).strip()

    if safe.startswith("Template:"):
        safe = safe[9:].strip()

    if " (" in safe and safe.endswith(")"):
        safe = safe.split(" (")[0].strip()

    for char in ['"', "'", " ", ":", "(", ")", "[", "]", "{", "}",
                 "|", "\\", "/", "#", ",", ";", ".", "!", "?", "@"]:
        safe = safe.replace(char, "_")

    safe = re.sub(r"_+", "_", safe)
    safe = safe.strip("_")

    return safe if safe else "unknown"

def clean_wikitext_value(value):
    """Clean wikitext values for schema.org properties."""
    if not value:
        return ""

    # Remove HTML comments
    value = re.sub(r'<!--.*?-->', '', value, flags=re.DOTALL)

    # Handle internal links [[Page|Display]] -> Display
    def replace_link(match):
        page = match.group(1).strip()
        display = match.group(2).strip() if match.group(2) else page
        return display

    value = re.sub(r'\[\[([^\]|]+)(?:\|([^\]]+))?\]\]', replace_link, value)

    # Remove external links [URL text] -> text
    value = re.sub(r'\[https?://[^\s]+ ([^\]]+)\]', r'\1', value)
    value = re.sub(r'\[https?://[^\]]+\]', '', value)

    # Remove templates {{...}}
    value = re.sub(r'\{\{[^}]*\}\}', '', value)

    # Remove file links
    value = re.sub(r'\[\[(File|Image|Media):[^\]]+\]\]', '', value, flags=re.IGNORECASE)

    # Remove ref tags
    value = re.sub(r'<ref[^>]*>.*?</ref>', '', value, flags=re.DOTALL)
    value = re.sub(r'<ref[^/]*/>', '', value)

    # Remove HTML tags
    value = re.sub(r'<[^>]+>', '', value)

    # Clean whitespace and quotes
    value = value.strip('"\'{}[]()')
    value = ' '.join(value.split())

    return value.strip()

def extract_links_from_value(value):
    """Extract page links from wikitext value for schema:relatedTo."""
    links = []
    matches = re.findall(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]', value)
    for match in matches:
        link = clean_wikitext_value(match).strip()
        if link and link not in links:
            links.append(link)
    return links

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
                    if member["title"].startswith("Template:"):
                        templates.append(member["title"])

                print(f"  Found {len(templates)} templates so far...")

            # Check if there are more pages
            if "continue" in data and "cmcontinue" in data["continue"]:
                continue_param = data["continue"]["cmcontinue"]
                time.sleep(0.5)
            else:
                break

    except Exception as e:
        print(f"Error in get_all_infobox_templates: {e}")

    # Filter templates
    filtered_templates = []
    skip_keywords = ['User:', 'User talk:', 'Template talk:', 'test', 'Test']

    for template in templates:
        if not any(keyword in template for keyword in skip_keywords):
            filtered_templates.append(template)

    print(f"\nTotal infobox templates found: {len(filtered_templates)}")
    filtered_templates.sort()

    print("\nSample templates:")
    for i, template in enumerate(filtered_templates[:10]):
        print(f"  {i+1}. {template}")
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
    """Get pages using a template WITH PAGINATION."""
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

def get_page_content_simple(page_title):
    """Get page content."""
    try:
        params = {
            "action": "query",
            "prop": "revisions",
            "rvprop": "content",
            "titles": page_title,
            "format": "json",
        }

        response = requests.get(API_URL, params=params, timeout=15)
        if response.status_code != 200:
            return ""

        data = response.json()
        pages = data.get("query", {}).get("pages", {})

        if pages:
            page = next(iter(pages.values()))
            if "missing" not in page:
                revisions = page.get("revisions", [])
                if revisions:
                    return revisions[0].get("*", "")

    except Exception:
        pass

    return ""

# ---------------------------
# Template Extraction (improved for schema.org)
# ---------------------------
def extract_template_simple(wikitext, template_name):
    """Simple template extraction with better cleaning."""
    template_short = template_name.replace("Template:", "")

    # Try multiple variations
    variations = [
        template_short,
        template_short.lower(),
        template_short.replace(" ", "_"),
        template_short.replace(" infobox", ""),
        template_short.replace("Infobox ", ""),
    ]

    for variation in variations:
        # Improved regex to capture multiline templates
        pattern = rf'\{{{{\s*{re.escape(variation)}\s*\|([^{{]*(?:\{{{{[^{{]*?\}}}}\s*)*[^{{]*?)}}}}'
        matches = re.findall(pattern, wikitext, re.IGNORECASE | re.DOTALL)

        if matches:
            template_content = matches[0]

            # Parse with better line handling
            properties = {}
            lines = [line.strip() for line in template_content.split('\n') if line.strip()]

            for line in lines:
                if line.startswith('|') and '=' in line:
                    line = line[1:]  # Remove leading |
                    parts = line.split('=', 1)
                    if len(parts) == 2:
                        key = parts[0].strip()
                        value = parts[1].strip()

                        if value:
                            # Use improved cleaning
                            clean_key = clean_wikitext_value(key)
                            clean_value = clean_wikitext_value(value)

                            if clean_key and clean_value:
                                properties[clean_key] = clean_value

            return properties

    return {}

# ---------------------------
# Categorization and RDF Generation with schema.org
# ---------------------------

def categorize_template(template_name):
    """Categorize template based on its name for schema.org mapping."""
    template_lower = template_name.lower()

    # More specific categorization in order of priority
    if any(x in template_lower for x in ['character', 'person', 'elf', 'dwarf', 'hobbit',
                                         'man', 'orc', 'troll', 'valar', 'maiar', 'wizard',
                                         'actor', 'director', 'author', 'artist']):
        return "Character"  # All people-related templates

    elif any(x in template_lower for x in ['location', 'place', 'city', 'country', 'kingdom',
                                           'realm', 'region', 'forest', 'mountain', 'river']):
        return "Location"

    elif any(x in template_lower for x in ['book', 'novel', 'publication', 'audiobook']):
        return "Book"

    elif any(x in template_lower for x in ['film', 'movie', 'video']):
        return "Film"

    elif any(x in template_lower for x in ['song', 'music']):
        return "Song"

    elif any(x in template_lower for x in ['album']):
        return "Album"

    elif any(x in template_lower for x in ['chapter', 'scene', 'episode']):
        return "Chapter"

    elif any(x in template_lower for x in ['website']):
        return "Website"

    elif any(x in template_lower for x in ['journal', 'mallorn', 'mythlore', 'periodical']):
        return "Journal"

    elif any(x in template_lower for x in ['game', 'puzzle', 'board game', 'video game']):
        return "Game"

    elif any(x in template_lower for x in ['item', 'object', 'artifact', 'weapon', 'ring',
                                           'collectible', 'card']):
        return "Item"

    elif any(x in template_lower for x in ['event', 'battle', 'war', 'campaign']):
        return "Event"

    elif any(x in template_lower for x in ['organization', 'company', 'society', 'band']):
        return "Organization"

    elif any(x in template_lower for x in ['race', 'species', 'people']):
        return "Race"

    elif any(x in template_lower for x in ['media']):
        return "Media"

    else:
        return "Other"

def add_to_graph_with_schema(graph, page_title, template_name, properties):
    """Add data to RDF graph with schema.org alignment."""
    if not properties:
        return False

    try:
        # Create URIs
        page_uri = URIRef(TGW[safe_uri_name(page_title)])
        page_url = f"https://tolkiengateway.net/wiki/{page_title.replace(' ', '_')}"

        # Add basic schema.org information
        graph.add((page_uri, RDF.type, SCHEMA.Thing))
        graph.add((page_uri, SCHEMA.name, Literal(page_title)))
        graph.add((page_uri, SCHEMA.url, Literal(page_url, datatype=XSD.anyURI)))
        graph.add((page_uri, DCTERMS.source, Literal("Tolkien Gateway")))

        # Add schema.org type based on template category
        category = categorize_template(template_name)
        schema_class = CATEGORY_TO_SCHEMA.get(category, SCHEMA.Thing)
        graph.add((page_uri, RDF.type, schema_class))

        # Keep original template info for reference
        template_clean = template_name.replace("Template:", "")
        graph.add((page_uri, TGWO.usesTemplate, Literal(template_clean)))
        graph.add((page_uri, TGWO.category, Literal(category)))

        # Process properties with schema.org mapping
        for prop_name, prop_value in properties.items():
            if not prop_value or prop_value.lower() in ['unknown', 'none', '?', '']:
                continue

            prop_name_lower = prop_name.lower().strip()
            mapped_property = None

            # Try to find exact match first
            if prop_name_lower in PROPERTY_MAPPINGS:
                mapped_property = PROPERTY_MAPPINGS[prop_name_lower]
            else:
                # Try partial matches
                for key, value in PROPERTY_MAPPINGS.items():
                    if key in prop_name_lower or prop_name_lower in key:
                        mapped_property = value
                        break

            if mapped_property:
                # Add with schema.org property
                graph.add((page_uri, mapped_property, Literal(prop_value)))
            else:
                # Fallback to custom ontology
                safe_prop = safe_uri_name(prop_name)
                graph.add((page_uri, TGWO[safe_prop], Literal(prop_value)))

        # Extract and add related links (schema:relatedTo)
        for prop_value in properties.values():
            links = extract_links_from_value(prop_value)
            for link in links:
                if link and link != page_title:
                    link_uri = URIRef(TGW[safe_uri_name(link)])
                    graph.add((page_uri, SCHEMA.relatedTo, link_uri))

        return True

    except Exception as e:
        print(f"    Error adding to graph: {e}")
        return False

# ---------------------------
# Schema.org Ontology Helper
# ---------------------------
def add_schema_ontology(graph):
    """Add schema.org ontology definitions to the graph."""
    print("Adding schema.org ontology definitions...")

    # Define custom properties in our ontology
    graph.add((TGWO.hairColor, RDF.type, RDF.Property))
    graph.add((TGWO.hairColor, RDFS.label, Literal("hair color")))
    graph.add((TGWO.hairColor, RDFS.range, XSD.string))
    graph.add((TGWO.hairColor, RDFS.domain, SCHEMA.Person))

    graph.add((TGWO.eyeColor, RDF.type, RDF.Property))
    graph.add((TGWO.eyeColor, RDFS.label, Literal("eye color")))
    graph.add((TGWO.eyeColor, RDFS.range, XSD.string))
    graph.add((TGWO.eyeColor, RDFS.domain, SCHEMA.Person))

    graph.add((TGWO.race, RDF.type, RDF.Property))
    graph.add((TGWO.race, RDFS.label, Literal("race")))
    graph.add((TGWO.race, RDFS.range, XSD.string))
    graph.add((TGWO.race, RDFS.domain, SCHEMA.Person))

    graph.add((TGWO.realm, RDF.type, RDF.Property))
    graph.add((TGWO.realm, RDFS.label, Literal("realm")))
    graph.add((TGWO.realm, RDFS.range, XSD.string))
    graph.add((TGWO.realm, RDFS.domain, SCHEMA.Person))

    graph.add((TGWO.usesTemplate, RDF.type, RDF.Property))
    graph.add((TGWO.usesTemplate, RDFS.label, Literal("uses template")))

    graph.add((TGWO.category, RDF.type, RDF.Property))
    graph.add((TGWO.category, RDFS.label, Literal("category")))

    # Add schema.org class definitions
    for category, schema_class in CATEGORY_TO_SCHEMA.items():
        if schema_class != SCHEMA.Thing:  # Skip generic Thing
            graph.add((schema_class, RDFS.subClassOf, SCHEMA.Thing))
            graph.add((schema_class, RDFS.label, Literal(category)))
            graph.add((schema_class, RDFS.comment,
                      Literal(f"A {category.lower()} from Tolkien's legendarium")))

# ---------------------------
# Main Program (updated for schema.org)
# ---------------------------
def main():
    print("=" * 70)
    print("TOLKIEN GATEWAY - INFOBOX EXTRACTOR WITH SCHEMA.ORG")
    print("=" * 70)
    print("Generating RDF aligned with schema.org vocabulary")
    print("=" * 70)

    # Step 1: Get ALL infobox templates
    all_templates = get_all_infobox_templates()

    if not all_templates:
        print("ERROR: No templates found!")
        return

    print(f"\nTotal templates to process: {len(all_templates)}")

    # Step 2: Test which templates have pages
    print("\n" + "=" * 70)
    print("TESTING TEMPLATES (checking which have pages)...")
    print("=" * 70)

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

        time.sleep(0.3)

    print(f"\nTemplate summary:")
    print(f"  Working templates: {len(working_templates)}")
    print(f"  Empty templates: {len(failed_templates)}")

    if not working_templates:
        print("ERROR: No working templates found!")
        return

    # Categorize templates
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
        for template in sorted(templates):
            print(f"  • {template}")

    print("\n" + "=" * 70)
    print("STARTING EXTRACTION WITH SCHEMA.ORG")
    print("=" * 70)

    # Initialize graph with schema.org bindings
    graph = Graph()

    # Bind namespaces
    graph.bind("schema", SCHEMA)
    graph.bind("tgw", TGW)
    graph.bind("tgwo", TGWO)
    graph.bind("dcterms", DCTERMS)
    graph.bind("foaf", FOAF)
    graph.bind("rdfs", RDFS)
    graph.bind("xsd", XSD)

    # Add schema.org ontology
    add_schema_ontology(graph)

    start_time = time.time()
    total_pages = 0
    total_successful = 0
    category_results = {category: 0 for category in categorized.keys()}
    processed_pages = set()  # Avoid duplicates

    # Process each working template
    for template_idx, template_name in enumerate(working_templates, 1):
        category = categorize_template(template_name)

        print(f"\n[{template_idx}/{len(working_templates)}] {template_name}")
        print(f"  Category: {category}")
        print(f"  Schema.org class: {CATEGORY_TO_SCHEMA.get(category, 'Thing')}")

        # Get pages
        pages = get_pages_for_template(template_name, limit=50)  # Reduced for testing

        if not pages:
            print(f"    No pages found (skipping)")
            continue

        print(f"    Processing {len(pages)} pages...")

        template_success = 0

        for page_idx, page_title in enumerate(pages, 1):
            if page_title in processed_pages:
                continue

            processed_pages.add(page_title)

            if page_idx % 10 == 0 or page_idx == 1 or page_idx == len(pages):
                print(f"      Page {page_idx}/{len(pages)}: {page_title[:40]}...")

            # Get content
            wikitext = get_page_content_simple(page_title)
            if not wikitext:
                continue

            total_pages += 1

            # Extract data
            properties = extract_template_simple(wikitext, template_name)

            if properties:
                # Use schema.org version
                if add_to_graph_with_schema(graph, page_title, template_name, properties):
                    total_successful += 1
                    template_success += 1
                    category_results[category] += 1

            time.sleep(0.05)

        print(f"    {template_success}/{len(pages)} successful extractions")

    elapsed = time.time() - start_time

    # Summary
    print(f"\n" + "=" * 70)
    print("EXTRACTION SUMMARY")
    print("=" * 70)

    print(f"\nResults:")
    print(f"   Total templates found: {len(all_templates)}")
    print(f"   Working templates processed: {len(working_templates)}")
    print(f"   Empty templates skipped: {len(failed_templates)}")
    print(f"   Unique pages processed: {len(processed_pages)}")
    print(f"   Successful extractions: {total_successful}")
    print(f"   RDF triples generated: {len(graph)}")
    print(f"   Time elapsed: {elapsed:.1f}s")

    print(f"\nBy category (schema.org classes):")
    for category, count in category_results.items():
        if count > 0:
            schema_class = CATEGORY_TO_SCHEMA.get(category, "Thing")
            class_name = str(schema_class).split("/")[-1]
            print(f"   {category:15} ({class_name:20}): {count} items")

    # Save results
    if len(graph) > 0:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        # Create data directory
        data_dir = os.path.join(PROJECT_ROOT, "data")
        os.makedirs(data_dir, exist_ok=True)

        filename = f"tolkien_schema_{len(working_templates)}templates_{total_successful}items_{timestamp}.ttl"
        OUTPUT_FILE = os.path.join(data_dir, filename)

        try:
            graph.serialize(OUTPUT_FILE, format="turtle")
            file_size = os.path.getsize(OUTPUT_FILE) / 1024

            print(f"\n✅ Saved RDF with schema.org: {OUTPUT_FILE}")
            print(f"   Size: {file_size:.1f} KB")
            print(f"   Triples: {len(graph)}")

            # Save template list
            template_list_file = os.path.join(data_dir, f"templates_schema_{timestamp}.txt")
            with open(template_list_file, "w", encoding="utf-8") as f:
                f.write("SCHEMA.ORG TEMPLATE MAPPINGS\n")
                f.write("=" * 50 + "\n\n")
                for template in working_templates:
                    category = categorize_template(template)
                    schema_class = CATEGORY_TO_SCHEMA.get(category, "Thing")
                    class_name = str(schema_class).split("/")[-1]
                    f.write(f"{template}\n")
                    f.write(f"  Category: {category}\n")
                    f.write(f"  Schema.org class: {class_name}\n\n")
                f.write(f"\nTotal: {len(working_templates)} templates\n")

            print(f"✓ Template mappings saved: {template_list_file}")

            # Generate statistics
            print(f"\n📊 SCHEMA.ORG STATISTICS:")
            print(f"   schema:Person entities: {len(list(graph.subjects(RDF.type, SCHEMA.Person)))}")
            print(f"   schema:Place entities: {len(list(graph.subjects(RDF.type, SCHEMA.Place)))}")
            print(f"   schema:Book entities: {len(list(graph.subjects(RDF.type, SCHEMA.Book)))}")
            print(f"   schema:Event entities: {len(list(graph.subjects(RDF.type, SCHEMA.Event)))}")

            # Most used schema.org properties
            from collections import Counter
            props = Counter()
            for s, p, o in graph:
                if str(p).startswith("http://schema.org/"):
                    prop_name = str(p).split("/")[-1]
                    props[prop_name] += 1

            print(f"\n Top schema.org properties:")
            for prop, count in props.most_common(10):
                print(f"   {prop:20}: {count}")

            print(f"\n" + "=" * 70)
            print("OPTIONAL: SENDING TO FUSEKI")
            print("=" * 70)

            try:
                with open(OUTPUT_FILE, "rb") as f:
                    response = requests.post(
                        FUSEKI_ENDPOINT + "/data",  # Use /data endpoint
                        data=f,
                        headers={"Content-Type": "text/turtle"},
                        timeout=60
                    )

                    if response.status_code in [200, 201, 204]:
                        print("Successfully sent to Fuseki!")
                    else:
                        print(f"Fuseki error: {response.status_code}")

            except Exception as e:
                print(f"Could not send to Fuseki: {e}")
                print("You can load the .ttl file manually via Fuseki web interface")

            #print(f"\n Next steps:")
            #print(f"   1. Load {filename} into your triplestore")
            #print(f"   2. Query using SPARQL with schema.org predicates")
            #print(f"   3. Validate with SHACL shapes")
            #print(f"   4. Create Linked Data interface")

        except Exception as e:
            print(f"Error saving: {e}")

    print(f"\n" + "=" * 70)
    print(" EXTRACTION COMPLETE WITH SCHEMA.ORG!")
    print("=" * 70)

if __name__ == "__main__":
    main()