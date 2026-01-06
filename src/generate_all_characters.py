import requests
import re
import os
import time
from urllib.parse import quote
from rdflib import Graph, URIRef, Literal, Namespace, RDF, RDFS

# ---------------------------
# Configuration
# ---------------------------
TOlkien = Namespace("http://example.org/tolkien/")
FUSEKI_ENDPOINT = "http://localhost:3030/tolkienKG"
API_URL = "https://tolkiengateway.net/w/api.php"


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
    # Example: "Adrahil (Captain of the Left Wing)" -> "Adrahil"
    if " (" in safe and safe.endswith(")"):
        # Extract the main name without the description in parentheses
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


def parse_wiki_value(value, namespace):
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
            uris.append(URIRef(namespace[safe_name]))
        return uris
    # If no link, return raw value as Literal
    return [Literal(value.strip())]


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
            # Small pause to avoid overloading the API
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
        # Make request with timeout
        response = requests.get(API_URL, params=params, timeout=15)

        # Check if response is valid
        if response.status_code != 200:
            # Don't display error for normal pages that don't exist
            return ""

        # Try to parse JSON
        try:
            data = response.json()
        except ValueError:  # Invalid JSON
            # Silent to avoid cluttering output
            return ""

        # Check expected structure
        if "query" not in data:
            return ""

        pages = data.get("query", {}).get("pages", {})
        if not pages:
            return ""

        # Take the first page
        page = next(iter(pages.values()))

        # Check if page exists (negative pageid or 'missing' present)
        if page.get("missing") is not None or page.get("pageid", 0) <= 0:
            # Page doesn't exist - this is normal for some names
            return ""

        # Retrieve content
        revisions = page.get("revisions", [])
        if revisions:
            return revisions[0].get("*", "")

        return ""

    except requests.exceptions.Timeout:
        # Silent timeout
        return ""
    except requests.exceptions.ConnectionError:
        # Silent connection error
        return ""
    except Exception:
        # Any other exception - return empty silently
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


# ---------------------------
# RDF graph creation
# ---------------------------
g = Graph()

# Add namespace declaration
g.bind("tolkien", TOlkien)

print("=" * 50)
print("Starting RDF graph generation - ALL CHARACTERS")
print("=" * 50)

# Retrieve ALL characters (no limit)
characters = get_characters_from_category("Third_Age_characters")

# Counters for tracking
total_characters = len(characters)
characters_with_infobox = 0
characters_without_infobox = 0
characters_with_errors = 0

print(f"\nProcessing {total_characters} characters...")
print("(Characters without infobox will be silently ignored)")
print("")

start_time = time.time()

for index, name in enumerate(characters, 1):
    # Display progress every 20 characters
    if index % 20 == 0:
        elapsed = time.time() - start_time
        print(
            f"[Progress: {index}/{total_characters}] - {characters_with_infobox} infoboxes parsed - Time: {elapsed:.1f}s")

    # Extract description if present
    description = extract_description_from_name(name)

    # Create a safe name for the URI
    safe_name = safe_uri_name(name)
    character_uri = URIRef(TOlkien[safe_name])

    # Add basic metadata
    g.add((character_uri, RDF.type, TOlkien.Character))
    g.add((character_uri, RDF.type, RDFS.Resource))
    g.add((character_uri, TOlkien.originalName, Literal(name)))

    # Add description if it exists
    if description:
        g.add((character_uri, TOlkien.descriptionNote, Literal(description)))

    # Retrieve and parse infobox
    try:
        infobox_text = get_infobox(name)
        if not infobox_text:
            characters_without_infobox += 1
            continue  # Move to next one silently

        characters_with_infobox += 1
        fields_parsed = 0

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

                    # Clean field name
                    safe_field = safe_uri_name(field)

                    try:
                        objects = parse_wiki_value(value, TOlkien)
                        for obj in objects:
                            g.add((character_uri, TOlkien[safe_field], obj))
                        fields_parsed += 1
                    except Exception:
                        # Minor error on a field, continue
                        pass

        # Display success for this character
        print(f"  [{index}] {name}: {fields_parsed} fields parsed")

    except Exception as e:
        characters_with_errors += 1
        # Major error on this character, continue with others
        print(f"  [{index}] Error on {name}: {str(e)[:50]}...")

    # Small pause to avoid overloading the API
    time.sleep(0.1)

# ---------------------------
# Serialization and sending
# ---------------------------
elapsed_total = time.time() - start_time

print("\n" + "=" * 50)
print("RDF GRAPH SERIALIZATION")
print("=" * 50)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_FILE = os.path.join(PROJECT_ROOT, "data", "all_characters.ttl")

# Create data folder if it doesn't exist
os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

# Serialize RDF graph
try:
    g.serialize(OUTPUT_FILE, format="turtle")
    print(f"RDF generated: {OUTPUT_FILE}")
    print(f"File size: {os.path.getsize(OUTPUT_FILE) / 1024:.1f} KB")
    print(f"Total triples: {len(g)}")

    # Count unique characters in the graph
    characters_in_graph = len(set(s for s, p, o in g if (s, RDF.type, TOlkien.Character) in g))
    print(f"Characters in graph: {characters_in_graph}")

except Exception as e:
    print(f"Error during serialization: {e}")
    # Backup save
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
print("SENDING TO FUSEKI")
print("=" * 50)

# Check and send to Fuseki
if os.path.exists(OUTPUT_FILE):
    if wait_for_fuseki():
        try:
            with open(OUTPUT_FILE, "rb") as f:
                r = requests.post(
                    FUSEKI_ENDPOINT,
                    data=f,
                    headers={"Content-Type": "text/turtle"},
                    timeout=60
                )
                if r.status_code in [200, 201, 204]:
                    print("RDF successfully added to Fuseki!")
                    print(f"   {len(g)} triples - {characters_with_infobox} characters")
                else:
                    print(f"Fuseki error: {r.status_code}")
                    if r.text:
                        print(f"  Message: {r.text[:200]}...")
        except requests.exceptions.ConnectionError:
            print("Fuseki is no longer accessible")
        except Exception as e:
            print(f"Error during sending: {e}")
    else:
        print("Fuseki is not accessible")
        print("   To start Fuseki:")
        print("   cd ~/Downloads/Semantic_WEB/Fusiki/apache-jena-fuseki-4.9.0")
        print("   ./fuseki-server --update --mem /tolkienKG")
else:
    print("RDF file not found")

print("\n" + "=" * 50)
print("COMPLETED!")
print("=" * 50)