"""
Extract ALL infobox templates from Tolkien Gateway
Automatically fetches templates from Category:Infobox templates
"""
import requests
import re
import os
import time
import json
from datetime import datetime
from rdflib import Graph, URIRef, Literal, Namespace, RDF, RDFS

# ---------------------------
# Configuration
# ---------------------------
TOlkien = Namespace("http://example.org/tolkien/")
FUSEKI_ENDPOINT = "http://localhost:3030/tolkienKG"
API_URL = "https://tolkiengateway.net/w/api.php"

# ---------------------------
# Utility Functions
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
                time.sleep(0.5)  # Be polite to the API
            else:
                break

    except Exception as e:
        print(f"Error in get_all_infobox_templates: {e}")

    # Filter and clean templates
    filtered_templates = []
    skip_keywords = ['User:', 'User talk:', 'Template talk:', 'test', 'Test']

    for template in templates:
        # Skip user templates and test templates
        if not any(keyword in template for keyword in skip_keywords):
            filtered_templates.append(template)

    print(f"\nTotal infobox templates found: {len(filtered_templates)}")

    # Sort templates for better organization
    filtered_templates.sort()

    # Display first few templates as sample
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

def get_pages_for_template(template_name, limit=10):
    """Get pages using a template."""
    pages = []

    print(f"  Searching: {template_name}")

    try:
        params = {
            "action": "query",
            "generator": "embeddedin",
            "geititle": template_name,
            "geilimit": "20",
            "geinamespace": "0",
            "prop": "info",
            "format": "json",
        }

        response = requests.get(API_URL, params=params, timeout=30)
        if response.status_code != 200:
            return pages

        data = response.json()

        if "query" in data:
            batch_pages = data["query"]["pages"]
            for page_id, page_info in batch_pages.items():
                if "missing" not in page_info:
                    pages.append(page_info["title"])

            print(f"    Found {len(pages)} pages")

    except Exception as e:
        print(f"    Error: {e}")

    return pages[:limit]

def extract_template_simple(wikitext, template_name):
    """Simple template extraction."""
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
        pattern = rf'\{{{{\s*{re.escape(variation)}\s*\|([^}}]+)}}}}'
        matches = re.findall(pattern, wikitext, re.IGNORECASE | re.DOTALL)

        if matches:
            # Take first match
            template_content = matches[0]

            # Simple parsing
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
                            # Basic cleaning
                            value = re.sub(r'\[\[([^\]|]+)(?:\|([^\]]+))?\]\]',
                                         lambda m: m.group(2) if m.group(2) else m.group(1),
                                         value)
                            value = re.sub(r'\{\{[^}]*\}\}', '', value)
                            value = ' '.join(value.split())

                            if value:
                                properties[key] = value

            return properties

    return {}

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

def categorize_template(template_name):
    """Categorize template based on its name."""
    template_lower = template_name.lower()

    if any(x in template_lower for x in ['location', 'kingdom', 'mountain', 'city', 'country', 'place']):
        return "Location"
    elif any(x in template_lower for x in ['character', 'person', 'actor', 'artist', 'author', 'director',
                                          'elf', 'dwarf', 'man', 'hobbit', 'orc', 'troll', 'valar', 'maiar']):
        return "Character"
    elif any(x in template_lower for x in ['object', 'item', 'book', 'film', 'album', 'game', 'song', 'poem']):
        return "Item"
    elif any(x in template_lower for x in ['event', 'battle', 'war', 'campaign']):
        return "Event"
    elif any(x in template_lower for x in ['organization', 'company', 'race', 'house']):
        return "Organization"
    elif any(x in template_lower for x in ['media', 'video', 'audio', 'journal', 'website']):
        return "Media"
    else:
        return "Other"

def add_to_graph_simple(graph, page_title, template_name, properties):
    """Add data to RDF graph."""
    if not properties:
        return False

    # Create URI
    page_uri = URIRef(TOlkien[safe_uri_name(page_title)])

    # Add basic info
    graph.add((page_uri, RDF.type, RDFS.Resource))
    graph.add((page_uri, TOlkien["pageTitle"], Literal(page_title)))

    # Add template info
    template_clean = template_name.replace("Template:", "")
    graph.add((page_uri, TOlkien["templateType"], Literal(template_clean)))

    # Add type based on template category
    category = categorize_template(template_name)
    graph.add((page_uri, RDF.type, TOlkien[category]))

    # Add properties
    for prop_name, prop_value in properties.items():
        if prop_value:
            safe_prop = safe_uri_name(prop_name)
            graph.add((page_uri, TOlkien[safe_prop], Literal(prop_value)))

    return True

# ---------------------------
# Main Program
# ---------------------------
def main():
    print("=" * 70)
    print("TOLKIEN GATEWAY - ALL INFOBOX TEMPLATES EXTRACTOR")
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

        time.sleep(0.3)  # Be polite to the API

    print(f"\nTemplate summary:")
    print(f"  Working templates: {len(working_templates)}")
    print(f"  Empty templates: {len(failed_templates)}")

    if len(failed_templates) > 0:
        print(f"\nEmpty templates (skipped):")
        for template in failed_templates[:10]:
            print(f"  • {template}")
        if len(failed_templates) > 10:
            print(f"  ... and {len(failed_templates) - 10} more")

    if not working_templates:
        print("ERROR: No working templates found!")
        return

    # Sort working templates by category for better organization
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
    print("STARTING EXTRACTION")
    print("=" * 70)

    # Initialize graph
    graph = Graph()
    graph.bind("tolkien", TOlkien)

    # Define RDF types for all categories
    for category in categorized.keys():
        graph.add((TOlkien[category], RDF.type, RDFS.Class))
        graph.add((TOlkien[category], RDFS.label, Literal(category)))

    start_time = time.time()

    total_pages = 0
    total_successful = 0
    category_results = {category: 0 for category in categorized.keys()}

    # Process each working template
    for template_idx, template_name in enumerate(working_templates, 1):
        category = categorize_template(template_name)

        print(f"\n[{template_idx}/{len(working_templates)}] {template_name}")
        print(f"  Category: {category}")

        # Get pages
        pages = get_pages_for_template(template_name, limit=5)  # Limit to 5 pages per template initially

        if not pages:
            print(f"    No pages found (skipping)")
            continue

        print(f"    Processing {len(pages)} pages...")

        template_success = 0

        for page_idx, page_title in enumerate(pages, 1):
            if page_idx % 5 == 0 or page_idx == 1 or page_idx == len(pages):
                print(f"      Page {page_idx}/{len(pages)}...")

            # Get content
            wikitext = get_page_content_simple(page_title)
            if not wikitext:
                continue

            total_pages += 1

            # Extract data
            properties = extract_template_simple(wikitext, template_name)

            if properties:
                if add_to_graph_simple(graph, page_title, template_name, properties):
                    total_successful += 1
                    template_success += 1
                    category_results[category] += 1

            time.sleep(0.2)  # Be polite

        print(f"    {template_success}/{len(pages)} successful")

    elapsed = time.time() - start_time

    # Summary
    print(f"\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    print(f"\nResults:")
    print(f"   Total templates found: {len(all_templates)}")
    print(f"   Working templates processed: {len(working_templates)}")
    print(f"   Empty templates skipped: {len(failed_templates)}")
    print(f"   Total pages processed: {total_pages}")
    print(f"   Successful extractions: {total_successful}")
    print(f"   RDF triples generated: {len(graph)}")
    print(f"   Time elapsed: {elapsed:.1f}s")

    print(f"\nBy category:")
    for category, count in category_results.items():
        if count > 0:
            print(f"   {category:15}: {count} items")

    # Save results
    if len(graph) > 0:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        filename = f"tolkien_{len(working_templates)}templates_{total_successful}items_{timestamp}.ttl"
        OUTPUT_FILE = os.path.join(PROJECT_ROOT, "data", filename)

        os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

        try:
            graph.serialize(OUTPUT_FILE, format="turtle")
            file_size = os.path.getsize(OUTPUT_FILE) / 1024

            print(f"\nSaved: {OUTPUT_FILE}")
            print(f"   Size: {file_size:.1f} KB")

            # Save template list for reference
            template_list_file = os.path.join(PROJECT_ROOT, "data", f"templates_list_{timestamp}.txt")
            with open(template_list_file, "w", encoding="utf-8") as f:
                f.write("WORKING TEMPLATES:\n")
                for template in working_templates:
                    f.write(f"{template}\n")
                f.write(f"\nTotal: {len(working_templates)} templates\n")

            # Send to Fuseki
            print(f"\n" + "=" * 70)
            print("SENDING TO FUSEKI")
            print("=" * 70)

            try:
                with open(OUTPUT_FILE, "rb") as f:
                    response = requests.post(
                        FUSEKI_ENDPOINT,
                        data=f,
                        headers={"Content-Type": "text/turtle"},
                        timeout=60
                    )

                    if response.status_code in [200, 201, 204]:
                        print("Successfully sent to Fuseki!")
                        print(f"   Total triples in dataset: ~{630 + len(graph)}")
                        print(f"   (630 characters + {len(graph)} new items)")
                    else:
                        print(f"Fuseki error: {response.status_code}")
                        print(f"Response: {response.text[:200]}")

            except Exception as e:
                print(f"Could not send to Fuseki: {e}")

        except Exception as e:
            print(f"Error saving: {e}")

    print(f"\n" + "=" * 70)
    print("DONE!")
    print("=" * 70)

if __name__ == "__main__":
    main()