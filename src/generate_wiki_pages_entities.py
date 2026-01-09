"""
Question 4: Page/Entity Distinction
Use MediaWiki API list=allpages to get ALL wiki pages.
For each page X, create:
  - page/X (the document)
  - resource/X (the real-world entity)
  Link: page/X is about resource/X
"""

import requests
import time
import os
from datetime import datetime
from rdflib import Graph, URIRef, Literal, Namespace, RDF, RDFS, XSD
# ---------------------------
# CONFIGURATION
# ---------------------------
SCHEMA = Namespace("http://schema.org/")
TOlkien = Namespace("http://example.org/tolkien/")
FOAF = Namespace("http://xmlns.com/foaf/0.1/")
DCTERMS = Namespace("http://purl.org/dc/terms/")
API_URL = "https://tolkiengateway.net/w/api.php"
FUSEKI_ENDPOINT = "http://localhost:3030/tolkienKG"

# File paths
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
OUTPUT_FILE = os.path.join(DATA_DIR, "tolkien_pages_entities.ttl")


# ---------------------------
# FUNCTION 1: Safe URI name (réutilise la tienne)
# ---------------------------
def safe_uri_name(name):
    """Convert any name to a safe URI fragment."""
    if not name:
        return "unknown"

    safe = str(name).strip()

    # Liste COMPLÈTE des caractères à remplacer
    # Ajoute '*' et autres caractères spéciaux
    special_chars = [
        ' ', ':', '(', ')', "'", '"', '&', '/',
        '*', '-', ',', ';', '!', '?', '@', '#',
        '$', '%', '^', '[', ']', '{', '}', '|',
        '\\', '=', '+', '<', '>', '~', '`'
    ]

    for char in special_chars:
        safe = safe.replace(char, '_')

    # Si après nettoyage c'est vide, retourne "unknown"
    if not safe or safe == '_':
        return "unknown"

    # Enlève les underscores multiples
    while '__' in safe:
        safe = safe.replace('__', '_')

    # Enlève les underscores au début/fin
    safe = safe.strip('_')

    return safe


# ---------------------------
# FUNCTION 2: Get ALL wiki pages
# ---------------------------
def get_all_wiki_pages(limit=None):
    """
    Get ALL pages from Tolkien Gateway using list=allpages.
    Handles pagination with 'continue' parameter.

    Args:
        limit: Max number of pages to fetch (for testing)

    Returns:
        List of page titles
    """
    print(" FETCHING ALL WIKI PAGES...")
    print("   This will take several minutes...")

    all_pages = []
    continue_params = {}
    page_count = 0

    try:
        while True:
            # Prepare API request
            params = {
                "action": "query",
                "list": "allpages",
                "aplimit": "max",  # Get maximum per request (500)
                "format": "json",
                **continue_params  # Add continue token if exists
            }

            # Make the request
            response = requests.get(API_URL, params=params, timeout=30)

            if response.status_code != 200:
                print(f"❌ API Error: {response.status_code}")
                break

            data = response.json()

            # Extract page titles
            if "query" in data and "allpages" in data["query"]:
                batch = data["query"]["allpages"]

                for page in batch:
                    title = page["title"]
                    all_pages.append(title)
                    page_count += 1

                    # Show progress every 500 pages
                    if page_count % 500 == 0:
                        print(f"   Retrieved {page_count} pages...")

            # Check if there are more pages
            if "continue" in data and "apcontinue" in data["continue"]:
                continue_params = {"apcontinue": data["continue"]["apcontinue"]}
                time.sleep(0.3)  # Be polite to the API
            else:
                break  # No more pages

            # Stop if we reached the limit (for testing)
            if limit and page_count >= limit:
                print(f"   Stopping at {limit} pages (test mode)")
                break

    except Exception as e:
        print(f"❌ Error during page fetch: {e}")

    print(f"✅ Retrieved {len(all_pages)} total pages")
    return all_pages


# ---------------------------
# FUNCTION 3: Create URIs
# ---------------------------

def create_page_uri(title):# À METTRE À LA PLACE :
    """Create URI for the wiki page (schema:WebPage)."""
    safe = safe_uri_name(title)
    return URIRef(f"http://tolkiengateway.net/page/{safe}")  #

def create_entity_uri(title):
    """Create URI for the real-world entity (schema:Thing)."""
    safe = safe_uri_name(title)
    return URIRef(f"http://tolkiengateway.net/resource/{safe}")


# ---------------------------
# FUNCTION 4: Send to Fuseki
# ---------------------------
def send_to_fuseki(graph, output_file):
    """Send RDF graph to Fuseki server."""
    print("\n SENDING TO FUSEKI...")

    try:
        # First, clear the dataset (optional but recommended)
        try:
            clear_query = "DELETE WHERE { ?s ?p ?o }"
            clear_response = requests.post(
                "http://localhost:3030/tolkienKG/update",
                data={"update": clear_query},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=10
            )
            if clear_response.status_code in [200, 201, 204]:
                print("   Dataset cleared successfully")
        except:
            print("   Could not clear dataset (maybe first run)")

        # Send the new data
        with open(output_file, "rb") as f:
            response = requests.post(
                FUSEKI_ENDPOINT,
                data=f,
                headers={"Content-Type": "text/turtle"},
                timeout=60
            )

            if response.status_code in [200, 201, 204]:
                print(f"✅ Successfully sent {len(graph)} triples to Fuseki!")
                return True
            else:
                print(f"❌ Fuseki error: {response.status_code}")
                return False

    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to Fuseki")
        print("   Make sure Fuseki is running: http://localhost:3030")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


# ---------------------------
# MAIN FUNCTION
# ---------------------------
def main():
    print("=" * 70)
    print("PAGE/ENTITY DISTINCTION GENERATOR")
    print("=" * 70)

    # Ask user for limit (for testing)
    print("\n  WARNING: Tolkien Gateway has ~15,000 pages.")
    #print("   This will take 5-10 minutes to fetch all pages.")

    test_mode = input("Run in test mode? (y/n): ").lower()

    if test_mode == 'y':
        limit = 100
        print(f"   Test mode: fetching {limit} pages only")
    else:
        limit = None
        print("   Full mode: fetching ALL pages")

    # Step 1: Create empty RDF graph
    print("\n STEP 1: Initializing RDF graph...")
    g = Graph()

    # Bind namespaces
    g.bind("schema", SCHEMA)
    g.bind("tolkien", TOlkien)
    g.bind("foaf", FOAF)
    g.bind("dcterms", DCTERMS)
    g.bind("rdfs", RDFS)

    # Step 2: Get all pages
    print("\n STEP 2: Fetching pages from wiki...")
    all_pages = get_all_wiki_pages(limit=limit)

    if not all_pages:
        print(" No pages found!")
        return

    # Step 3: Create triples for each page
    print(f"\n STEP 3: Creating page/entity triples...")
    print(f"   Processing {len(all_pages)} pages")

    start_time = time.time()
    triples_count = 0

    for i, page_title in enumerate(all_pages, 1):
        # Show progress
        if i % 100 == 0:
            elapsed = time.time() - start_time
            print(f"   Processed {i}/{len(all_pages)} pages ({elapsed:.1f}s)")

        # Create URIs
        page_uri = create_page_uri(page_title)
        entity_uri = create_entity_uri(page_title)
        wiki_url = f"https://tolkiengateway.net/wiki/{page_title.replace(' ', '_')}"

        # --- TRIPLES FOR THE PAGE (schema:WebPage) ---
        g.add((page_uri, RDF.type, SCHEMA.WebPage))  # ✅ SCHEMA.ORG
        g.add((page_uri, SCHEMA.name, Literal(f"Wiki page: {page_title}")))
        g.add((page_uri, SCHEMA.url, Literal(wiki_url, datatype=XSD.anyURI)))
        g.add((page_uri, DCTERMS.title, Literal(page_title)))
        g.add((page_uri, DCTERMS.source, Literal("Tolkien Gateway")))

        # --- TRIPLES FOR THE ENTITY (schema:Thing) ---
        g.add((entity_uri, RDF.type, SCHEMA.Thing))  # ✅ SCHEMA.ORG
        g.add((entity_uri, SCHEMA.name, Literal(page_title)))
        g.add((entity_uri, SCHEMA.url, Literal(wiki_url, datatype=XSD.anyURI)))

        # --- CRUCIAL LINK: page is about entity (schema:about) ---
        g.add((page_uri, SCHEMA.about, entity_uri))  # ✅ SCHEMA.ORG

        # Also: entity is described by the page
        g.add((entity_uri, SCHEMA.subjectOf, page_uri))
        triples_count += 9  # 9 triples per page

    elapsed_total = time.time() - start_time

    # Step 4: Save to file
    print(f"\n STEP 4: Saving to file...")

    # Create data directory if it doesn't exist
    os.makedirs(DATA_DIR, exist_ok=True)

    try:
        g.serialize(OUTPUT_FILE, format="turtle")
        file_size = os.path.getsize(OUTPUT_FILE) / 1024

        print(f"✅ File saved: {OUTPUT_FILE}")
        print(f"   Size: {file_size:.1f} KB")
        print(f"   Triples created: {triples_count}")
        print(f"   Time: {elapsed_total:.1f} seconds")

    except Exception as e:
        print(f" Error saving file: {e}")
        return

    # Step 5: Send to Fuseki
    print(f"\n STEP 5: Sending to Fuseki server...")
    send_success = send_to_fuseki(g, OUTPUT_FILE)

    # Final summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Pages processed: {len(all_pages)}")
    print(f"Triples created: {triples_count}")
    print(f"Output file: {OUTPUT_FILE}")

    if send_success:
        print("Fuseki:  Data successfully uploaded")
        print("\nYou can now query Fuseki with:")
        print("  http://localhost:3030/tolkienKG")
    else:
        print("Fuseki:   Data saved locally but not sent to Fuseki")

    print("\n" + "=" * 70)
    print("DONE!")
    print("=" * 70)


# ---------------------------
# ENTRY POINT
# ---------------------------
if __name__ == "__main__":
    # Add required imports at the top
    import requests

    main()