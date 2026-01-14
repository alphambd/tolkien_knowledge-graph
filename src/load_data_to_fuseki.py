"""
load_data_to_fuseki.py - Load all data into Fuseki automatically
"""
import requests
import os
import time
import glob

FUSEKI_ENDPOINT = "http://localhost:3030/tolkienKG"
OUTPUT_DIR = "data/output"
FINAL_KG_FILE = os.path.join(OUTPUT_DIR, "final_knowledge_graph.ttl")

def wait_for_fuseki():
    """Wait for Fuseki to be ready"""
    print("Waiting for Fuseki to start...")
    for i in range(30):
        try:
            response = requests.get("http://localhost:3030/", timeout=2)
            if response.status_code == 200:
                print("Success : Fuseki is ready")
                return True
        except:
            pass
        time.sleep(1)
    print("Err : Fuseki not responding")
    return False

def clear_dataset():
    """Clear the dataset before loading"""
    print("\nClearing existing data...")

    clear_query = "DELETE WHERE { ?s ?p ?o }"

    try:
        response = requests.post(
            f"{FUSEKI_ENDPOINT}/update",
            data={"update": clear_query},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30
        )

        if response.status_code in [200, 201, 204]:
            print("Success : Dataset cleared")
            return True
        else:
            print(f" Clear failed: {response.status_code}")
            return False

    except Exception as e:
        print(f" Clear error: {e}")
        return False

def load_turtle_file(filepath):
    """Load a Turtle file into Fuseki"""
    filename = os.path.basename(filepath)

    try:
        with open(filepath, "rb") as f:
            response = requests.post(
                f"{FUSEKI_ENDPOINT}/data",
                data=f.read(),
                headers={"Content-Type": "text/turtle"},
                timeout=60
            )

            if response.status_code in [200, 201, 204]:
                print(f"Success : Loaded: {filename}")
                return True
            else:
                print(f" Failed to load {filename}: {response.status_code}")
                if response.text:
                    print(f"  Error: {response.text[:200]}")
                return False

    except Exception as e:
        print(f" Error loading {filename}: {e}")
        return False

def export_final_kg():
    """Export the complete KG from Fuseki to a file"""
    print("\nExporting final knowledge graph...")

    # Create output directory if it doesn't exist
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # SPARQL query to get all triples
    query = "CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o }"

    try:
        response = requests.get(
            f"{FUSEKI_ENDPOINT}/sparql",
            params={"query": query},
            headers={"Accept": "text/turtle"},
            timeout=120  # Longer timeout for large exports
        )

        if response.status_code == 200:
            with open(FINAL_KG_FILE, "w", encoding="utf-8") as f:
                f.write(response.text)

            # Count triples
            triples_count = response.text.count('\n')
            print(f"Success : Final KG exported to {FINAL_KG_FILE}")
            print(f"         Estimated triples: {triples_count:,}")
            return True
        else:
            print(f" Export failed: {response.status_code}")
            print(f"  Error: {response.text[:500]}")
            return False

    except Exception as e:
        print(f" Export error: {e}")
        return False

def load_all_data():
    """Load all Turtle files in order"""
    print("=" * 60)
    print("LOADING ALL DATA INTO FUSEKI")
    print("=" * 60)

    # Wait for Fuseki
    if not wait_for_fuseki():
        return False

    # Clear dataset
    if not clear_dataset():
        print("Warning: Could not clear dataset, continuing anyway...")

    # Define loading order (important for dependencies)
    load_order = [
        "data/ontology.ttl",              # 1. Ontology first
        "data/tolkien_pages_entities.ttl", # 2. Pages/entities
        "data/all_characters_schema.ttl",  # 3. Characters
        "data/metw_integration_cards.ttl", # 4. Cards
        "data/multilingual_labels_only.ttl", # 5. Multilingual labels
        "data/api_alignments.ttl",        # 6. Alignments
        # Add the final KG file if it exists from previous runs
    ]

    # Check if final KG exists (for reloading)
    if os.path.exists(FINAL_KG_FILE):
        load_order.append(FINAL_KG_FILE)
        print(f"Note: Will load existing final KG from {FINAL_KG_FILE}")

    # Also look for any additional .ttl files in data directory
    additional_files = glob.glob("data/*.ttl") + glob.glob("shapes/*.ttl")

    # Filter out already listed files
    additional_files = [f for f in additional_files if f not in load_order]

    # Combine
    all_files = load_order + sorted(additional_files)

    # Load files
    success_count = 0
    total_count = len(all_files)

    for i, filepath in enumerate(all_files, 1):
        if os.path.exists(filepath):
            print(f"\n[{i}/{total_count}] Loading: {os.path.basename(filepath)}")

            if load_turtle_file(filepath):
                success_count += 1
            else:
                print(f"  Skipping due to error")

            # Small delay to avoid overwhelming
            time.sleep(1)
        else:
            print(f"\n[{i}/{total_count}] Missing: {filepath}")

    # Export final KG
    print("\n" + "=" * 60)
    print("EXPORTING FINAL KNOWLEDGE GRAPH")
    print("=" * 60)
    if export_final_kg():
        print("Success : Final KG saved in kg/final_knowledge_graph.ttl")

    # Summary
    print("\n" + "=" * 60)
    print("LOADING SUMMARY")
    print("=" * 60)
    print(f"Files attempted: {total_count}")
    print(f"Files loaded successfully: {success_count}")
    print(f"Files failed: {total_count - success_count}")

    # Test query
    print("\nTesting with a sample query...")
    test_query = "SELECT (COUNT(*) AS ?triples) WHERE { ?s ?p ?o }"

    try:
        response = requests.get(
            f"{FUSEKI_ENDPOINT}/sparql",
            params={"query": test_query, "format": "json"},
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            triples = data['results']['bindings'][0]['triples']['value']
            print(f"Success : Total triples in dataset: {triples}")
        else:
            print("Err : Test query failed")

    except Exception as e:
        print(f"Err : Test error: {e}")

    # Provide useful endpoints
    print("\n" + "=" * 60)
    print("ACCESS ENDPOINTS")
    print("=" * 60)
    print("Fuseki UI:          http://localhost:3030")
    print("SPARQL endpoint:    http://localhost:3030/tolkienKG/sparql")
    print("Dataset endpoint:   http://localhost:3030/tolkienKG")
    print(f"Final KG file:      {FINAL_KG_FILE}")
    print("\nSample queries:")
    print("  - Characters: SELECT ?s ?name WHERE { ?s a <http://schema.org/Person> . ?s <http://schema.org/name> ?name } LIMIT 10")
    print("  - Cards: SELECT ?entity ?card WHERE { ?entity <http://tolkiengateway.net/ontology/hasCardRepresentation> ?card } LIMIT 10")

    return success_count > 0

def create_batch_script():
    """Create a batch script for easy data loading"""

    script_content = """#!/bin/bash
# Automated data loading script for Tolkien Knowledge Graph

echo "========================================"
echo "Tolkien Knowledge Graph - Data Loader"
echo "========================================"

# Check if Fuseki is running
if ! curl -s http://localhost:3030/ > /dev/null; then
    echo "ERROR: Fuseki is not running on http://localhost:3030"
    echo "Start Fuseki first: ./start_fuseki.sh"
    exit 1
fi

# Run the Python loader
python3 load_data_to_fuseki.py

if [ $? -eq 0 ]; then
    echo ""
    echo "SUCCESS: Data loaded successfully!"
    echo ""
    echo "Access endpoints:"
    echo "  Web Interface: http://localhost:3030"
    echo "  Linked Data:   http://localhost:5000"
    echo "  SPARQL:        http://localhost:3030/tolkienKG/sparql"
    echo "  Final KG file: data/output/final_knowledge_graph.ttl"
else
    echo ""
    echo "ERROR: Data loading failed"
    exit 1
fi
"""
    
    with open("load_data.sh", "w") as f:
        f.write(script_content)
    
    os.chmod("load_data.sh", 0o755)
    
    print("\nSuccess : Batch script created: load_data.sh")
    print("  Run: ./load_data.sh")

if __name__ == "__main__":
    # Create batch script
    create_batch_script()
    
    # Run loading
    print("\nStarting data loading process...")
    load_all_data()