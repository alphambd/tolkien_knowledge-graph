import requests
import re
import os
import time
from urllib.parse import quote
from rdflib import Graph, URIRef, Literal, Namespace, RDF, RDFS, XSD

# ---------------------------
# Configuration
# ---------------------------
SCHEMA = Namespace("http://schema.org/")
TGW = Namespace("http://tolkiengateway.net/resource/")
TGWO = Namespace("http://tolkiengateway.net/ontology/")
DCTERMS = Namespace("http://purl.org/dc/terms/")
FOAF = Namespace("http://xmlns.com/foaf/0.1/")

FUSEKI_ENDPOINT = "http://localhost:3030/tolkienKG"
API_URL = "https://tolkiengateway.net/w/api.php"

# Schema.org property mappings for character infoboxes
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
# Enhanced helper functions
# ---------------------------
def safe_uri_name(name):
    """
    Convert a name to a URI-safe version.
    Handles parentheses, quotes, and special characters.
    """
    safe = name.strip()

    # Special handling for parentheses containing descriptions
    if " (" in safe and safe.endswith(")"):
        safe = safe.split(" (")[0].strip()

    # Remove quotes
    safe = safe.replace('"', '').replace("'", "")

    # List of characters to replace with underscores
    chars_to_replace = [" ", ":", "(", ")", "[", "]", "{", "}",
                        "|", "\\", "/", "#", ",", ";", ".", "!"]

    for char in chars_to_replace:
        safe = safe.replace(char, "_")

    # Replace multiple underscore sequences with a single one
    safe = re.sub(r"_+", "_", safe)

    # Remove underscores from beginning and end
    safe = safe.strip("_")

    return safe


def extract_description_from_name(name):
    """
    Extract the description from parentheses in a name.
    Example: "Adrahil (Captain of the Left Wing)" -> "Captain of the Left Wing"
    """
    name = name.strip()
    if " (" in name and name.endswith(")"):
        description = name.split(" (")[1].rstrip(")").strip()
        return description
    return None


def parse_wiki_value(value):
    """
    Parse a wiki value.
    - If it contains one or more links [[X]] or [[X|Y]], return a list of URIRefs.
    - Otherwise, return a single Literal.
    """
    # Find all links [[X]] or [[X|Y]]
    links = re.findall(r"\[\[([^\|\]]+)(?:\|([^\]]+))?\]\]", value)
    if links:
        uris = []
        for link in links:
            entity_name = link[0].strip()  # link target
            safe_name = safe_uri_name(entity_name)
            uris.append(URIRef(TGW[safe_name]))
        return uris
    # If no link, return raw value as Literal
    return [Literal(value.strip())]


def clean_wikitext_value(value):
    """Clean wikitext values."""
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


def get_characters_from_category(category, limit=None):
    """
    Retrieve characters from a Wikipedia category.
    """
    members = []
    cmcontinue = ""
    count = 0

    print(f"Retrieving characters from category: {category}")

    while True:
        params = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": f"Category:{category}",
            "cmlimit": "max",  # Use max (500) instead of 50
            "format": "json",
        }
        if cmcontinue:
            params["cmcontinue"] = cmcontinue

        try:
            r = requests.get(API_URL, params=params, timeout=15).json()
        except Exception as e:
            print(f"Error during retrieval: {e}")
            break

        if "query" in r:
            batch = r["query"]["categorymembers"]
            for m in batch:
                members.append(m["title"])
                count += 1
                if limit and count >= limit:
                    break

        if limit and count >= limit:
            break

        if "continue" in r:
            cmcontinue = r["continue"]["cmcontinue"]
            time.sleep(0.5)
        else:
            break

    print(f"  {len(members)} characters found")
    return members


def get_infobox(title):
    """
    Retrieve infobox content from a Wikipedia page.
    Robust version with better error handling.
    """
    params = {
        "action": "query",
        "prop": "revisions",
        "rvprop": "content",
        "titles": title,
        "format": "json"
    }

    try:
        response = requests.get(API_URL, params=params, timeout=15)

        if response.status_code != 200:
            return ""

        try:
            data = response.json()
        except ValueError:
            return ""

        if "query" not in data:
            return ""

        pages = data.get("query", {}).get("pages", {})
        if not pages:
            return ""

        page = next(iter(pages.values()))

        if page.get("missing") is not None or page.get("pageid", 0) <= 0:
            return ""

        revisions = page.get("revisions", [])
        if revisions:
            return revisions[0].get("*", "")

        return ""

    except requests.exceptions.Timeout:
        return ""
    except requests.exceptions.ConnectionError:
        return ""
    except Exception:
        return ""


def wait_for_fuseki(max_retries=10):
    """
    Wait for Fuseki to be available.
    """
    for i in range(max_retries):
        try:
            response = requests.get("http://localhost:3030/", timeout=2)
            if response.status_code == 200:
                print("Fuseki is accessible")
                return True
        except:
            if i < max_retries - 1:
                print(f"  Attempt {i + 1}/{max_retries} - Waiting for Fuseki...")
                time.sleep(2)
    return False


def add_to_graph_with_schema(graph, name, properties):
    """
    Add character data to RDF graph with schema.org alignment.
    """
    if not properties:
        return False

    try:
        # Create URIs
        safe_name = safe_uri_name(name)
        character_uri = URIRef(TGW[safe_name])
        page_url = f"https://tolkiengateway.net/wiki/{name.replace(' ', '_')}"

        # Add basic schema.org information
        graph.add((character_uri, RDF.type, SCHEMA.Person))
        graph.add((character_uri, SCHEMA.name, Literal(name)))
        graph.add((character_uri, SCHEMA.url, Literal(page_url, datatype=XSD.anyURI)))
        graph.add((character_uri, DCTERMS.source, Literal("Tolkien Gateway")))
        graph.add((character_uri, TGWO.category, Literal("Character")))

        # Add description if present in name
        description = extract_description_from_name(name)
        if description:
            graph.add((character_uri, SCHEMA.description, Literal(description)))

        # Process properties with schema.org mapping
        for prop_name, prop_value in properties.items():
            if not prop_value or prop_value.lower() in ['unknown', 'none', '?', '']:
                continue

            # Clean the value
            clean_value = clean_wikitext_value(prop_value)
            if not clean_value:
                continue

            prop_name_lower = prop_name.lower().strip()
            mapped_property = None

            # Try to find in property mappings
            if prop_name_lower in PROPERTY_MAPPINGS:
                mapped_property = PROPERTY_MAPPINGS[prop_name_lower]
            else:
                # Try partial matches
                for key, value in PROPERTY_MAPPINGS.items():
                    if key in prop_name_lower or prop_name_lower in key:
                        mapped_property = value
                        break

            if mapped_property:
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
                        match = re.search(pattern, clean_value)
                        if match:
                            date_value = match.group(1)
                            break

                    if date_value:
                        graph.add((character_uri, mapped_property, Literal(date_value)))
                    else:
                        graph.add((character_uri, mapped_property, Literal(clean_value)))
                else:
                    graph.add((character_uri, mapped_property, Literal(clean_value)))
            else:
                # Fallback to custom ontology
                safe_prop = safe_uri_name(prop_name)
                graph.add((character_uri, TGWO[safe_prop], Literal(clean_value)))

        # Extract and add related links
        for prop_value in properties.values():
            links = re.findall(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]', prop_value)
            for link in links:
                if link and link != name:
                    link_safe = safe_uri_name(link)
                    link_uri = URIRef(TGW[link_safe])
                    graph.add((character_uri, SCHEMA.relatedTo, link_uri))

        return True

    except Exception as e:
        print(f"    Error adding to graph: {e}")
        return False


# ---------------------------
# Main Program
# ---------------------------
def main():
    # Initialize RDF graph with bindings
    g = Graph()
    g.bind("schema", SCHEMA)
    g.bind("tgw", TGW)
    g.bind("tgwo", TGWO)
    g.bind("dcterms", DCTERMS)
    g.bind("foaf", FOAF)
    g.bind("rdfs", RDFS)
    g.bind("xsd", XSD)

    print("=" * 50)
    print("Starting RDF graph generation - ALL CHARACTERS WITH SCHEMA.ORG")
    print("=" * 50)

    # Retrieve ALL characters (no limit)
    characters = get_characters_from_category("Third_Age_characters")

    # Counters for tracking
    total_characters = len(characters)
    characters_with_infobox = 0
    characters_without_infobox = 0
    characters_with_errors = 0

    print(f"\nProcessing {total_characters} characters with schema.org...")
    print("")

    start_time = time.time()

    for index, name in enumerate(characters, 1):
        # Display progress every 20 characters
        if index % 20 == 0:
            elapsed = time.time() - start_time
            print(
                f"[Progress: {index}/{total_characters}] - {characters_with_infobox} infoboxes parsed - Time: {elapsed:.1f}s")

        # Retrieve and parse infobox
        try:
            infobox_text = get_infobox(name)
            if not infobox_text:
                characters_without_infobox += 1
                continue

            # Parse infobox properties
            properties = {}
            for line in infobox_text.split("\n"):
                line = line.strip()
                if line.startswith("|"):
                    parts = line[1:].split("=", 1)
                    if len(parts) == 2:
                        field, value = parts
                        field = field.strip()
                        value = value.strip()

                        if not field or not value:
                            continue

                        properties[field] = value

            if properties:
                if add_to_graph_with_schema(g, name, properties):
                    characters_with_infobox += 1
                    print(f"  [{index}] {name}: {len(properties)} fields parsed (schema.org)")
                else:
                    characters_with_errors += 1
            else:
                characters_without_infobox += 1

        except Exception as e:
            characters_with_errors += 1
            print(f"  [{index}] Error on {name}: {str(e)[:50]}...")

        # Small pause to avoid overloading the API
        time.sleep(0.1)

    # ---------------------------
    # Serialization
    # ---------------------------
    elapsed_total = time.time() - start_time

    print("\n" + "=" * 50)
    print("RDF GRAPH SERIALIZATION")
    print("=" * 50)

    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    OUTPUT_FILE = os.path.join(PROJECT_ROOT, "data", "all_characters_schema.ttl")

    # Create data folder if it doesn't exist
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    # Serialize RDF graph
    try:
        g.serialize(OUTPUT_FILE, format="turtle")
        print(f"✅ RDF generated with schema.org: {OUTPUT_FILE}")
        print(f"   File size: {os.path.getsize(OUTPUT_FILE) / 1024:.1f} KB")
        print(f"   Total triples: {len(g)}")

        # Count schema:Person entities
        person_count = len(list(g.subjects(RDF.type, SCHEMA.Person)))
        print(f"   schema:Person entities: {person_count}")

    except Exception as e:
        print(f"Error during serialization: {e}")
        backup_file = OUTPUT_FILE.replace(".ttl", ".nt")
        g.serialize(backup_file, format="nt")
        print(f"NTriples backup: {backup_file}")

    print("\n" + "=" * 50)
    print("FINAL SUMMARY")
    print("=" * 50)
    print(f"Total characters in category: {total_characters}")
    print(f"Characters with infobox processed: {characters_with_infobox}")
    print(f"Characters without infobox: {characters_without_infobox}")
    print(f"Characters with errors: {characters_with_errors}")
    print(f"Total execution time: {elapsed_total:.1f} seconds")
    print(f"RDF triples generated: {len(g)}")

    print("\n" + "=" * 50)
    print("SCHEMA.ORG STATISTICS")
    print("=" * 50)

    # Count most used schema.org properties
    from collections import Counter
    props = Counter()
    for s, p, o in g:
        if str(p).startswith("http://schema.org/"):
            prop_name = str(p).split("/")[-1]
            props[prop_name] += 1

    print("Top schema.org properties:")
    for prop, count in props.most_common(10):
        print(f"  {prop:20}: {count}")

    # COMMENTÉ: Sending to Fuseki
    # print("\n" + "=" * 50)
    # print("OPTIONAL: SENDING TO FUSEKI")
    # print("=" * 50)
    #
    # if os.path.exists(OUTPUT_FILE):
    #     if wait_for_fuseki():
    #         try:
    #             with open(OUTPUT_FILE, "rb") as f:
    #                 r = requests.post(
    #                     FUSEKI_ENDPOINT + "/data",
    #                     data=f,
    #                     headers={"Content-Type": "text/turtle"},
    #                     timeout=60
    #                 )
    #                 if r.status_code in [200, 201, 204]:
    #                     print("RDF successfully added to Fuseki!")
    #                 else:
    #                     print(f"Fuseki error: {r.status_code}")
    #         except Exception as e:
    #             print(f"Error during sending: {e}")
    #     else:
    #         print("Fuseki is not accessible")
    # else:
    #     print("RDF file not found")

    print("\n" + "=" * 50)
    print("✅ COMPLETED WITH SCHEMA.ORG!")
    print("=" * 50)


if __name__ == "__main__":
    main()