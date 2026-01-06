"""
Extract ALL infobox templates from Tolkien Gateway Category:Infobox_templates
and convert them to RDF.
Improved version with:
1. Better file naming to identify content
2. Better handling of templates with no pages
3. Improved template categorization
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

# Cache to avoid repeated API calls
TEMPLATE_PAGE_CACHE = {}

# ---------------------------
# Utility Functions - IMPROVED
# ---------------------------
def safe_uri_name(name):
    """Convert any name to a safe URI fragment."""
    if not name:
        return "unknown"

    safe = str(name).strip()

    # Remove "Template:" prefix if present
    if safe.startswith("Template:"):
        safe = safe[9:].strip()

    # Remove parentheses with descriptions
    if " (" in safe and safe.endswith(")"):
        safe = safe.split(" (")[0].strip()

    # Replace problematic characters
    for char in ['"', "'", " ", ":", "(", ")", "[", "]", "{", "}",
                 "|", "\\", "/", "#", ",", ";", ".", "!", "?", "@",
                 "$", "%", "^", "&", "*", "+", "=", "~", "`"]:
        safe = safe.replace(char, "_")

    # Collapse multiple underscores
    safe = re.sub(r"_+", "_", safe)

    # Remove leading/trailing underscores
    safe = safe.strip("_")

    return safe if safe else "unknown"

def get_all_infobox_templates():
    """Get ALL templates from Category:Infobox_templates with better filtering."""
    templates = []
    cmcontinue = ""

    print("Fetching all infobox templates from Category:Infobox_templates...")

    while True:
        params = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": "Category:Infobox_templates",
            "cmlimit": "max",
            "format": "json",
        }

        if cmcontinue:
            params["cmcontinue"] = cmcontinue

        try:
            response = requests.get(API_URL, params=params, timeout=30)
            if response.status_code != 200:
                print(f"  API Error: {response.status_code}")
                break

            data = response.json()

            if "query" in data:
                batch = data["query"]["categorymembers"]
                for item in batch:
                    title = item["title"]
                    # Filter out user pages and non-template pages
                    if (title.startswith("Template:") and
                        not title.startswith("Template:User/") and
                        not title.startswith("User:")):
                        templates.append(title)

                print(f"  Batch: {len(batch)} items (Templates: {len(templates)})")

            if "continue" in data:
                cmcontinue = data["continue"]["cmcontinue"]
                time.sleep(0.5)  # Be nice to the API
            else:
                break

        except Exception as e:
            print(f"  Error fetching templates: {e}")
            break

    print(f"\n✅ Found {len(templates)} infobox templates")
    return sorted(templates)

def get_pages_using_template_improved(template_name, limit=20):
    """Get pages that use a specific template with better error handling."""
    if template_name in TEMPLATE_PAGE_CACHE:
        print(f"  Using cached result for {template_name}")
        return TEMPLATE_PAGE_CACHE[template_name][:limit]

    pages = []
    geicontinue = None
    attempts = 0
    max_attempts = 3

    print(f"  Searching for pages using: {template_name}")

    while attempts < max_attempts:
        try:
            params = {
                "action": "query",
                "generator": "embeddedin",
                "geititle": template_name,
                "geilimit": "50",  # Use 'min' for fewer results per request
                "geinamespace": "0",  # Main namespace only
                "prop": "info",
                "format": "json",
            }

            if geicontinue:
                params["geicontinue"] = geicontinue

            response = requests.get(API_URL, params=params, timeout=45)

            if response.status_code == 403:
                print(f"    Access forbidden for {template_name}. Skipping.")
                TEMPLATE_PAGE_CACHE[template_name] = []
                return []

            if response.status_code != 200:
                print(f"    HTTP Error {response.status_code}")
                attempts += 1
                time.sleep(2)
                continue

            data = response.json()

            # Check for API errors
            if "error" in data:
                error_code = data["error"].get("code", "unknown")
                error_info = data["error"].get("info", "")
                print(f"    API Error {error_code}: {error_info[:100]}")

                # Handle specific error cases
                if error_code == "badtitle":
                    print(f"    Template '{template_name}' may not exist or have invalid title")
                    TEMPLATE_PAGE_CACHE[template_name] = []
                    return []

                attempts += 1
                time.sleep(2)
                continue

            if "query" in data:
                batch_pages = data["query"]["pages"]
                new_pages = 0
                for page_id, page_info in batch_pages.items():
                    if "missing" not in page_info and page_info.get("ns", 0) == 0:
                        pages.append(page_info["title"])
                        new_pages += 1

                if new_pages > 0:
                    print(f"    Found {new_pages} pages (total: {len(pages)})")
                else:
                    print(f"    No new pages in this batch")

            # Check if we should continue
            if "continue" in data and len(pages) < limit:
                geicontinue = data["continue"]["geicontinue"]
                time.sleep(0.5)  # Be nice to the API
            else:
                break

            # Stop if we have enough
            if len(pages) >= limit:
                break

            attempts = 0  # Reset attempts on successful request

        except requests.exceptions.Timeout:
            print(f"    Timeout on attempt {attempts + 1}/{max_attempts}")
            attempts += 1
            time.sleep(3)
        except Exception as e:
            print(f"    Error: {e}")
            attempts += 1
            time.sleep(2)

    # Cache the result
    TEMPLATE_PAGE_CACHE[template_name] = pages.copy()

    if attempts >= max_attempts:
        print(f"    Max attempts reached for {template_name}")

    return pages[:limit]


def extract_template_data_improved(wikitext, template_name):
    """Extract data from ANY template invocation with better parsing."""
    template_short = template_name.replace("Template:", "")

    # Try multiple patterns to catch different template formats
    patterns = [
        # Standard pattern with exact name
        rf'\{{{{\s*{re.escape(template_short)}\s*\|([^}}]+)}}}}',
        # Lowercase version (for cases like "dwarves infobox" vs "Dwarves infobox")
        rf'\{{{{\s*{re.escape(template_short.lower())}\s*\|([^}}]+)}}}}',
        # Without "infobox" suffix
        rf'\{{{{\s*{re.escape(template_short.replace(" infobox", "").replace(" Infobox", ""))}\s*\|([^}}]+)}}}}',
        # Without "infobox" suffix, lowercase
        rf'\{{{{\s*{re.escape(template_short.replace(" infobox", "").replace(" Infobox", "").lower())}\s*\|([^}}]+)}}}}',
        # Infobox X pattern (for "Infobox character" style)
        rf'\{{{{\s*[Ii]nfobox\s+{re.escape(template_short.replace("Infobox ", "").replace("infobox ", ""))}\s*\|([^}}]+)}}}}',
        # Generic pattern with template name variations
        rf'\{{{{\s*[^{{|}}]*(?:{re.escape(template_short.split()[0]) if " " in template_short else re.escape(template_short)})[^{{|}}]*\|([^}}]+)}}}}',
    ]

    all_matches = []
    used_pattern = ""

    for i, pattern in enumerate(patterns):
        matches = re.findall(pattern, wikitext, re.IGNORECASE | re.DOTALL)
        if matches:
            all_matches.extend(matches)
            used_pattern = f"pattern {i + 1}"
            # Don't break, collect ALL matches from this pattern
            # But we can continue to try other patterns for different formats

    if not all_matches:
        # Try generic infobox pattern as fallback
        generic_pattern = r'\{\{\s*[Ii]nfobox[^}]*\|([^}]+)\}\}'
        generic_matches = re.findall(generic_pattern, wikitext, re.DOTALL)
        if generic_matches:
            print(f"    Using generic infobox pattern for {template_name}")
            all_matches = generic_matches
            used_pattern = "generic infobox"

    if not all_matches:
        # One more attempt: look for ANY template with similar name
        simple_name = template_short.replace(" infobox", "").replace(" Infobox", "").replace("Infobox ", "").replace(
            "infobox ", "")
        simple_pattern = rf'\{{{{\s*{re.escape(simple_name)}[^{{|}}]*\|([^}}]+)}}}}'
        simple_matches = re.findall(simple_pattern, wikitext, re.IGNORECASE | re.DOTALL)
        if simple_matches:
            print(f"    Using simplified pattern for {template_name}")
            all_matches = simple_matches
            used_pattern = "simplified"

    if not all_matches:
        # Debug: show a snippet of the wikitext to see what's there
        if "dwarf" in template_name.lower() or "dwarves" in template_name.lower():
            # Look for any mention of dwarf-related templates
            dwarf_pattern = r'\{\{.*[Dd]warf.*\|'
            dwarf_matches = re.findall(dwarf_pattern, wikitext)
            if dwarf_matches:
                print(f"    Found potential dwarf template: {dwarf_matches[0][:50]}...")
        return []

    # Debug output
    if used_pattern:
        print(f"    Found {len(all_matches)} matches using {used_pattern}")

    results = []

    for match in all_matches:
        template_content = match

        # Parse parameters with better handling of nested templates
        properties = {}

        # Improved parsing that handles nested templates better
        lines = []
        depth = 0
        current_line = ""

        # First, normalize the content
        template_content = template_content.replace('\n\n', '\n')

        # Parse character by character to handle nested templates
        for char in template_content:
            if char == '{':
                depth += 1
            elif char == '}':
                depth -= 1

            if char == '|' and depth == 0:
                if current_line:
                    lines.append(current_line)
                    current_line = ""
            else:
                current_line += char

        # Don't forget the last line
        if current_line:
            lines.append(current_line)

        # Alternative simpler parsing for complex cases
        if not lines or len(lines) < 2:
            # Fall back to simple split if complex parsing failed
            lines = [line.strip() for line in template_content.split('|') if line.strip()]

        # Parse each line
        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Skip template name line (usually first line without =)
            if '=' not in line and not properties:
                continue

            if '=' in line:
                # Find the first = that's not inside nested templates
                equals_pos = -1
                nested_depth = 0
                for i, char in enumerate(line):
                    if char == '{':
                        nested_depth += 1
                    elif char == '}':
                        nested_depth -= 1
                    elif char == '=' and nested_depth == 0:
                        equals_pos = i
                        break

                if equals_pos > 0:
                    param_name = line[:equals_pos].strip()
                    param_value = line[equals_pos + 1:].strip()

                    # Clean up the parameter name
                    if param_name.startswith('|'):
                        param_name = param_name[1:].strip()

                    if param_name and param_value:
                        # Basic cleaning of the value
                        param_value = re.sub(r'\s+', ' ', param_value)  # Normalize whitespace

                        # Remove leading/trailing quotes
                        param_value = param_value.strip('"\'').strip()

                        properties[param_name] = param_value
                else:
                    # No = found, might be a continuation line
                    if properties and list(properties.keys()):
                        # Append to last parameter
                        last_param = list(properties.keys())[-1]
                        properties[last_param] += " " + line
            elif properties:
                # Continuation line - append to last parameter
                last_param = list(properties.keys())[-1]
                properties[last_param] += " " + line

        if properties:
            # Clean up properties
            cleaned_properties = {}
            for key, value in properties.items():
                if value and str(value).strip():
                    # Remove common wikitext artifacts
                    clean_value = str(value)
                    # Remove HTML comments
                    clean_value = re.sub(r'<!--.*?-->', '', clean_value, flags=re.DOTALL)
                    # Remove ref tags
                    clean_value = re.sub(r'<ref[^>]*>.*?</ref>', '', clean_value, flags=re.DOTALL)
                    # Remove span tags
                    clean_value = re.sub(r'<span[^>]*>.*?</span>', '', clean_value, flags=re.DOTALL)
                    # Clean whitespace again
                    clean_value = re.sub(r'\s+', ' ', clean_value).strip()

                    if clean_value:
                        cleaned_properties[key] = clean_value

            if cleaned_properties:
                results.append(cleaned_properties)

    return results

def get_page_content_improved(page_title):
    """Get wikitext content of a page with retry logic."""
    params = {
        "action": "query",
        "prop": "revisions",
        "rvprop": "content",
        "titles": page_title,
        "format": "json",
    }

    for attempt in range(3):
        try:
            response = requests.get(API_URL, params=params, timeout=20)
            if response.status_code != 200:
                if attempt < 2:
                    time.sleep(1)
                    continue
                return ""

            data = response.json()

            # Check for API errors
            if "error" in data:
                return ""

            pages = data.get("query", {}).get("pages", {})
            if not pages:
                return ""

            page = next(iter(pages.values()))
            if "missing" in page:
                return ""

            revisions = page.get("revisions", [])
            if revisions:
                return revisions[0].get("*", "")

            return ""

        except requests.exceptions.Timeout:
            if attempt < 2:
                print(f"    Timeout fetching {page_title}, retrying...")
                time.sleep(2)
                continue
        except Exception:
            if attempt < 2:
                time.sleep(1)
                continue

    return ""

def add_template_data_to_graph_improved(graph, page_title, template_name, properties):
    """Add template data to RDF graph with better type assignment."""
    if not properties:
        return False

    # Create URI for the page
    page_uri = URIRef(TOlkien[safe_uri_name(page_title)])

    # Add basic info
    graph.add((page_uri, RDF.type, RDFS.Resource))
    graph.add((page_uri, TOlkien["pageTitle"], Literal(page_title)))
    graph.add((page_uri, TOlkien["extractionDate"], Literal(datetime.now().isoformat())))

    # Add template type with better classification
    template_clean = template_name.replace("Template:", "")
    graph.add((page_uri, TOlkien["templateType"], Literal(template_clean)))

    # Determine RDF type based on template name
    template_lower = template_clean.lower()
    if any(x in template_lower for x in ['character', 'person', 'actor', 'author', 'artist']):
        graph.add((page_uri, RDF.type, TOlkien["Character"]))
    elif any(x in template_lower for x in ['location', 'kingdom', 'mountain', 'settlement']):
        graph.add((page_uri, RDF.type, TOlkien["Location"]))
    elif any(x in template_lower for x in ['dwarf', 'elf', 'men', 'hobbit', 'race', 'valar', 'maiar', 'dragon']):
        graph.add((page_uri, RDF.type, TOlkien["RaceOrCreature"]))
    elif any(x in template_lower for x in ['object', 'item', 'artifact']):
        graph.add((page_uri, RDF.type, TOlkien["Item"]))
    elif any(x in template_lower for x in ['event', 'battle', 'war', 'campaign']):
        graph.add((page_uri, RDF.type, TOlkien["Event"]))
    elif any(x in template_lower for x in ['film', 'book', 'album', 'game', 'video', 'song', 'poem']):
        graph.add((page_uri, RDF.type, TOlkien["Media"]))
    else:
        graph.add((page_uri, RDF.type, TOlkien["Other"]))

    # Add all properties with improved cleaning
    for prop_name, prop_value in properties.items():
        if prop_value and str(prop_value).strip():
            safe_prop = safe_uri_name(prop_name)

            # Clean value: remove wiki markup but preserve essential info
            clean_value = str(prop_value)

            # Handle links: extract the display text if available
            def replace_link(match):
                target = match.group(1)
                display = match.group(2) if match.group(2) else target
                return display

            clean_value = re.sub(r'\[\[([^\]|]+)(?:\|([^\]]+))?\]\]', replace_link, clean_value)

            # Remove simple templates but keep their content
            clean_value = re.sub(r'\{\{([^}|]+)(?:\|([^}]+))?\}\}', r'\1', clean_value)

            # Remove HTML tags
            clean_value = re.sub(r'<[^>]+>', '', clean_value)

            # Clean whitespace
            clean_value = ' '.join(clean_value.split())

            if clean_value:
                # Check if value looks like it could be a reference to another entity
                if (len(clean_value) < 100 and
                    re.match(r'^[A-Z][a-zA-Z\s\-]+$', clean_value) and
                    ' ' in clean_value):  # Looks like a proper name with spaces
                    # Try to create a connection
                    try:
                        target_uri = URIRef(TOlkien[safe_uri_name(clean_value)])
                        graph.add((page_uri, TOlkien[safe_prop], target_uri))
                    except:
                        graph.add((page_uri, TOlkien[safe_prop], Literal(clean_value)))
                else:
                    graph.add((page_uri, TOlkien[safe_prop], Literal(clean_value)))

    return True

def categorize_templates_improved(templates):
    """Categorize templates more accurately."""
    categories = {
        'character': [],
        'location': [],
        'race_creature': [],
        'item': [],
        'event': [],
        'media': [],
        'other': []
    }

    character_keywords = ['character', 'person', 'people', 'actor', 'author', 'artist', 'director', 'user']
    location_keywords = ['location', 'kingdom', 'mountain', 'settlement', 'amonhen', 'arnorian', 'gondorian']
    race_keywords = ['dwarf', 'elf', 'men', 'hobbit', 'race', 'valar', 'maiar', 'dragon', 'druadan',
                     'easterling', 'edain', 'ent', 'nandor', 'noldor', 'northmen', 'numenorean',
                     'rohirrim', 'sindar', 'vanyar', 'avar', 'half-elf']
    item_keywords = ['object', 'item', 'artifact', 'collectible']
    event_keywords = ['event', 'battle', 'war', 'campaign', 'scene']
    media_keywords = ['film', 'book', 'album', 'game', 'video', 'song', 'poem', 'audiobook',
                      'board game', 'video game', 'chapter', 'letter', 'journal', 'mythlore']

    for template in templates:
        template_name = template.replace("Template:", "").lower()
        categorized = False

        # Check each category
        if any(keyword in template_name for keyword in character_keywords):
            categories['character'].append(template)
            categorized = True
        elif any(keyword in template_name for keyword in location_keywords):
            categories['location'].append(template)
            categorized = True
        elif any(keyword in template_name for keyword in race_keywords):
            categories['race_creature'].append(template)
            categorized = True
        elif any(keyword in template_name for keyword in item_keywords):
            categories['item'].append(template)
            categorized = True
        elif any(keyword in template_name for keyword in event_keywords):
            categories['event'].append(template)
            categorized = True
        elif any(keyword in template_name for keyword in media_keywords):
            categories['media'].append(template)
            categorized = True

        if not categorized:
            categories['other'].append(template)

    return categories

def generate_descriptive_filename(category_choice, templates_count, timestamp):
    """Generate descriptive filenames based on content."""
    category_names = {
        '1': 'characters',
        '2': 'locations',
        '3': 'races_creatures',
        '4': 'items',
        '5': 'events',
        '6': 'media',
        '7': 'all_infoboxes'
    }

    base_name = category_names.get(category_choice, 'unknown')
    return f"tolkien_{base_name}_{templates_count}templates_{timestamp}.ttl"

# ---------------------------
# Main Processing - IMPROVED
# ---------------------------
def main():
    print("=" * 80)
    print("TOLKIEN GATEWAY - IMPROVED INFOBOX TEMPLATES EXTRACTOR")
    print("=" * 80)

    # Step 1: Get ALL infobox templates
    all_templates = get_all_infobox_templates()

    if not all_templates:
        print("❌ No templates found!")
        return

    # Step 2: Categorize templates more accurately
    categories = categorize_templates_improved(all_templates)

    print("\n" + "=" * 80)
    print("TEMPLATE CATEGORIES FOUND")
    print("=" * 80)

    print(f"\n📊 Category Breakdown:")
    print(f"   🧑  Character templates: {len(categories['character'])}")
    print(f"   🗺️   Location templates: {len(categories['location'])}")
    print(f"   👥  Race/Creature templates: {len(categories['race_creature'])}")
    print(f"   🗡️   Item/Object templates: {len(categories['item'])}")
    print(f"   ⚔️   Event templates: {len(categories['event'])}")
    print(f"   📚  Media templates: {len(categories['media'])}")
    print(f"   📋  Other templates: {len(categories['other'])}")

    # Step 3: Let user select which templates to process
    print("\n" + "=" * 80)
    print("SELECT TEMPLATES TO PROCESS")
    print("=" * 80)

    print("\nSelect templates to process:")
    print("1. Character templates")
    print("2. Location templates")
    print("3. Race/Creature templates")
    print("4. Item/Object templates")
    print("5. Event templates")
    print("6. Media templates")
    print("7. All templates (will take a LONG time)")

    try:
        choice = input("\nEnter your choice (1-7, default=2): ").strip()
        if not choice:
            choice = "2"

        category_map = {
            '1': categories['character'],
            '2': categories['location'],
            '3': categories['race_creature'],
            '4': categories['item'],
            '5': categories['event'],
            '6': categories['media'],
            '7': all_templates
        }

        selected_templates = category_map.get(choice, categories['location'])

        # Remove known problematic templates
        problematic_templates = ['Template:Infoboxes', 'Template:VTbox', 'Template:SEVEN']
        selected_templates = [t for t in selected_templates if t not in problematic_templates]

        print(f"\nSelected {len(selected_templates)} templates to process")

        # Show which templates we're processing
        if len(selected_templates) <= 15:
            print("\nTemplates to process:")
            for i, template in enumerate(selected_templates, 1):
                print(f"  {i:2d}. {template}")

        # Limit for testing if too many
        if len(selected_templates) > 15:
            print(f"\nLimiting to first 15 templates for reasonable testing...")
            selected_templates = selected_templates[:15]

    except Exception as e:
        print(f"\nError in selection: {e}")
        print("Using default: Location templates (first 5)")
        selected_templates = categories['location'][:5]

    # Step 4: Process selected templates
    graph = Graph()
    graph.bind("tolkien", TOlkien)

    # Define common RDF types
    for rdf_type in ["Character", "Location", "RaceOrCreature", "Item", "Event", "Media", "Other"]:
        graph.add((TOlkien[rdf_type], RDF.type, RDFS.Class))
        graph.add((TOlkien[rdf_type], RDFS.label, Literal(rdf_type)))

    total_templates_attempted = 0
    total_templates_with_pages = 0
    total_pages = 0
    total_successful = 0

    print("\n" + "=" * 80)
    print("PROCESSING TEMPLATES")
    print("=" * 80)

    start_time = time.time()

    for template_idx, template_name in enumerate(selected_templates, 1):
        print(f"\n[{template_idx}/{len(selected_templates)}] Processing: {template_name}")

        total_templates_attempted += 1

        # Get pages using this template (with improved function)
        pages = get_pages_using_template_improved(template_name, limit=15)

        if not pages:
            print(f"  ⚠️  No pages found using this template")
            # Try alternative name (without "infobox" suffix)
            if " infobox" in template_name.lower():
                alt_name = template_name.replace(" infobox", "").replace(" Infobox", "")
                print(f"  🔄 Trying alternative name: {alt_name}")
                pages = get_pages_using_template_improved(alt_name, limit=10)

            if not pages:
                continue

        total_templates_with_pages += 1
        print(f"  📄 Found {len(pages)} pages to process")

        template_pages_processed = 0
        template_pages_successful = 0

        for page_idx, page_title in enumerate(pages, 1):
            if page_idx % 5 == 0:
                print(f"    Processing page {page_idx}/{len(pages)}...")

            # Get page content with improved function
            wikitext = get_page_content_improved(page_title)
            if not wikitext:
                continue

            total_pages += 1
            template_pages_processed += 1

            # Extract template data with improved function
            template_data_list = extract_template_data_improved(wikitext, template_name)

            # If no data found with specific template, try generic infobox
            if not template_data_list and "infobox" in template_name.lower():
                template_data_list = extract_template_data_improved(wikitext, "infobox")

            if template_data_list:
                for template_data in template_data_list:
                    if add_template_data_to_graph_improved(graph, page_title, template_name, template_data):
                        total_successful += 1
                        template_pages_successful += 1

            # Be nice to the API
            time.sleep(0.2)

        success_rate = (template_pages_successful / template_pages_processed * 100) if template_pages_processed > 0 else 0
        print(f"  ✅ Results: {template_pages_successful}/{template_pages_processed} pages successful ({success_rate:.1f}%)")

    elapsed = time.time() - start_time

    # Step 5: Summary and save results
    print(f"\n" + "=" * 80)
    print("PROCESSING SUMMARY")
    print("=" * 80)

    print(f"\n📊 Extraction Statistics:")
    print(f"   Templates attempted: {total_templates_attempted}")
    print(f"   Templates with pages: {total_templates_with_pages}")
    print(f"   Total pages processed: {total_pages}")
    print(f"   Successful extractions: {total_successful}")
    print(f"   RDF triples generated: {len(graph)}")
    print(f"   Time elapsed: {elapsed:.1f} seconds")

    if total_templates_with_pages > 0:
        templates_success_rate = (total_templates_with_pages / total_templates_attempted * 100)
        print(f"   Templates with data: {templates_success_rate:.1f}%")

    # Save results with descriptive filename
    if len(graph) > 0:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        # Generate descriptive filename
        filename = generate_descriptive_filename(choice, total_templates_with_pages, timestamp)
        OUTPUT_FILE = os.path.join(PROJECT_ROOT, "data", filename)

        os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

        try:
            # Save in multiple formats for flexibility
            graph.serialize(OUTPUT_FILE, format="turtle")

            # Also save as JSON-LD for easier inspection
            jsonld_file = OUTPUT_FILE.replace(".ttl", ".jsonld")
            graph.serialize(jsonld_file, format="json-ld")

            file_size_kb = os.path.getsize(OUTPUT_FILE) / 1024
            print(f"\n💾 Saved files:")
            print(f"   Turtle: {OUTPUT_FILE}")
            print(f"   JSON-LD: {jsonld_file}")
            print(f"   File size: {file_size_kb:.1f} KB")

            # Generate a manifest file describing the contents
            manifest = {
                "extraction_date": datetime.now().isoformat(),
                "category_choice": choice,
                "templates_processed": total_templates_with_pages,
                "total_pages": total_pages,
                "successful_extractions": total_successful,
                "rdf_triples": len(graph),
                "processing_time_seconds": elapsed,
                "templates_list": selected_templates[:20],  # First 20 only
                "output_files": [OUTPUT_FILE, jsonld_file]
            }

            manifest_file = OUTPUT_FILE.replace(".ttl", "_manifest.json")
            with open(manifest_file, 'w', encoding='utf-8') as f:
                json.dump(manifest, f, indent=2, ensure_ascii=False)

            print(f"   Manifest: {manifest_file}")

            # Send to Fuseki
            print(f"\n" + "=" * 80)
            print("SENDING TO FUSEKI")
            print("=" * 80)

            try:
                with open(OUTPUT_FILE, "rb") as f:
                    response = requests.post(
                        FUSEKI_ENDPOINT,
                        data=f,
                        headers={"Content-Type": "text/turtle"},
                        timeout=120
                    )

                    if response.status_code in [200, 201, 204]:
                        print("✅ Successfully sent to Fuseki!")
                        print(f"   Dataset now contains ~{len(graph)} triples")
                    else:
                        print(f"⚠️  Fuseki returned status {response.status_code}")
                        if response.text:
                            print(f"   Message: {response.text[:200]}...")
            except requests.exceptions.ConnectionError:
                print("⚠️  Could not connect to Fuseki. Is it running?")
                print("   Start with: ./fuseki-server --update --mem /tolkienKG")
            except Exception as e:
                print(f"⚠️  Error sending to Fuseki: {e}")

        except Exception as e:
            print(f"❌ Error saving files: {e}")
            # Try to save at least in NT format
            try:
                backup_file = os.path.join(PROJECT_ROOT, "data", f"backup_{timestamp}.nt")
                graph.serialize(backup_file, format="nt")
                print(f"💾 Backup saved as NTriples: {backup_file}")
            except:
                print("❌ Could not save backup file either")
    else:
        print("\n⚠️  No data extracted. Check your template selection and API connection.")

    print(f"\n" + "=" * 80)
    print("DONE!")
    print("=" * 80)

    # Final recommendations
    if total_templates_with_pages < total_templates_attempted:
        print(f"\n💡 Recommendations:")
        print(f"   • {total_templates_attempted - total_templates_with_pages} templates had no pages")
        print(f"   • Try checking template names manually on Tolkien Gateway")
        print(f"   • Some templates might be obsolete or rarely used")

if __name__ == "__main__":
    main()