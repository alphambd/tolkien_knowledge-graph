import requests

FUSEKI_QUERY_ENDPOINT = "http://localhost:3030/tolkienKG/query"


def query_infoboxes():
    """Query all infobox data from Fuseki."""

    headers = {
        "Accept": "application/sparql-results+json",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    print("=" * 70)
    print("INFOBOX TEMPLATES QUERY TOOL")
    print("=" * 70)

    # 1. Count total items
    query1 = """
    PREFIX tolkien: <http://example.org/tolkien/>

    SELECT (COUNT(DISTINCT ?item) as ?total_items)
    WHERE {
      ?item tolkien:templateType ?template .
    }
    """

    print("\n1. Total infobox items:")
    results = execute_query(query1, headers)
    if results:
        count = results["results"]["bindings"][0]["total_items"]["value"]
        print(f"   {count} items extracted from infoboxes")

    # 2. Templates distribution
    query2 = """
    PREFIX tolkien: <http://example.org/tolkien/>

    SELECT ?template (COUNT(?item) as ?count)
    WHERE {
      ?item tolkien:templateType ?template .
    }
    GROUP BY ?template
    ORDER BY DESC(?count)
    """

    print("\n2. Templates distribution:")
    results = execute_query(query2, headers)
    if results:
        print("   Template                  Count")
        print("   " + "-" * 40)
        for row in results["results"]["bindings"]:
            template = row["template"]["value"]
            count = row["count"]["value"]
            print(f"   {template:25} {count:>5}")

    # 3. Categories overview
    query3 = """
    PREFIX tolkien: <http://example.org/tolkien/>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

    SELECT ?category (COUNT(?item) as ?count)
    WHERE {
      ?item rdf:type ?category .
      FILTER(STRSTARTS(STR(?category), "http://example.org/tolkien/"))
    }
    GROUP BY ?category
    ORDER BY DESC(?count)
    """

    print("\n3. Categories overview:")
    results = execute_query(query3, headers)
    if results:
        for row in results["results"]["bindings"]:
            category = row["category"]["value"].split("/")[-1]
            count = row["count"]["value"]
            print(f"   {category:15} : {count} items")

    # 4. Sample data from each template
    query4 = """
    PREFIX tolkien: <http://example.org/tolkien/>

    SELECT DISTINCT ?template ?name
    WHERE {
      ?item tolkien:templateType ?template .
      ?item tolkien:pageTitle ?name .
    }
    ORDER BY ?template ?name
    LIMIT 30
    """

    print("\n4. Sample items (template + name):")
    results = execute_query(query4, headers)
    if results:
        print("   Template                Name")
        print("   " + "-" * 60)
        current_template = None
        for row in results["results"]["bindings"]:
            template = row["template"]["value"]
            name = row["name"]["value"]
            if template != current_template:
                print(f"\n   [{template}]")
                current_template = template
            print(f"     - {name}")


def execute_query(sparql_query, headers):
    """Execute a SPARQL query."""
    params = {"query": sparql_query}

    try:
        response = requests.post(
            FUSEKI_QUERY_ENDPOINT,
            data=params,
            headers=headers,
            timeout=10
        )

        if response.status_code == 200:
            return response.json()
        else:
            print(f"   Error: {response.status_code}")
            return None

    except Exception as e:
        print(f"   Connection error: {e}")
        return None


def search_by_template(template_name):
    """Search for specific template data."""

    headers = {
        "Accept": "application/sparql-results+json",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    query = f"""
    PREFIX tolkien: <http://example.org/tolkien/>

    SELECT ?item ?name ?property ?value
    WHERE {{
      ?item tolkien:templateType "{template_name}" .
      ?item tolkien:pageTitle ?name .
      ?item ?property ?value .
      FILTER(STRSTARTS(STR(?property), "http://example.org/tolkien/"))
      FILTER(?property != tolkien:templateType)
      FILTER(?property != tolkien:pageTitle)
    }}
    ORDER BY ?name ?property
    LIMIT 50
    """

    print(f"\nSearching for template: {template_name}")
    results = execute_query(query, headers)

    if results and results["results"]["bindings"]:
        current_item = None
        for row in results["results"]["bindings"]:
            item = row["item"]["value"]
            name = row["name"]["value"]
            prop = row["property"]["value"].split("/")[-1]
            value = row["value"]["value"]

            if item != current_item:
                print(f"\n📄 {name}")
                current_item = item
            print(f"   {prop:20} : {value}")
    else:
        print(f"   No data found for template: {template_name}")


if __name__ == "__main__":
    query_infoboxes()

    # Example: Search for specific template
    print("\n" + "=" * 70)
    print("SEARCH SPECIFIC TEMPLATE")
    print("=" * 70)

    templates_to_search = ["Actor", "Book", "Battle", "Film infobox"]

    for template in templates_to_search:
        search_by_template(template)
        print("\n" + "-" * 70)