import requests
import json

endpoint = "http://localhost:3030/tolkienKG/query"


def explore_graph():
    print("🔍 EXPLORATION DU GRAPHE TOLKIEN")
    print("=" * 60)

    queries = {
        "1. Nombre total de triplets": "SELECT (COUNT(*) AS ?total) WHERE { ?s ?p ?o }",
        "2. Nombre d'entités distinctes": "SELECT (COUNT(DISTINCT ?s) AS ?entities) WHERE { ?s ?p ?o }",
        "3. Top 10 des classes": """
            SELECT ?class (COUNT(*) AS ?count) WHERE {
                ?s a ?class .
            }
            GROUP BY ?class
            ORDER BY DESC(?count)
            LIMIT 10
        """,
        "4. Top 20 des entités (par propriétés)": """
            SELECT ?entity (COUNT(?p) AS ?props) WHERE {
                ?entity ?p ?o .
            }
            GROUP BY ?entity
            ORDER BY DESC(?props)
            LIMIT 20
        """,
        "5. Personnages avec noms": """
            PREFIX schema: <http://schema.org/>
            SELECT ?entity ?name WHERE {
                ?entity a schema:Person .
                ?entity schema:name ?name .
                FILTER(LANG(?name) = "en")
            }
            LIMIT 15
        """,
        "6. Lieux": """
            PREFIX schema: <http://schema.org/>
            SELECT ?place ?name WHERE {
                ?place a schema:Place .
                ?place schema:name ?name .
                FILTER(LANG(?name) = "en")
            }
            LIMIT 15
        """
    }

    for name, query in queries.items():
        print(f"\n{name}")
        print("-" * 40)

        try:
            response = requests.get(endpoint, params={'query': query}, timeout=10)
            if response.status_code == 200:
                results = response.json()
                for binding in results['results']['bindings']:
                    # Afficher proprement
                    row = []
                    for var in results['head']['vars']:
                        if var in binding:
                            val = binding[var]['value']
                            # Raccourcir les URIs
                            if val.startswith('http://tolkiengateway.net/resource/'):
                                val = val.split('/')[-1]
                            elif val.startswith('http://schema.org/'):
                                val = 'schema:' + val.split('/')[-1]
                            row.append(f"{var}: {val}")
                    print(" | ".join(row))
            else:
                print(f"Erreur: {response.status_code}")
        except Exception as e:
            print(f"Exception: {e}")


def find_entities_with_most_data():
    """Trouve les entités avec le plus de données"""
    print("\n\n ENTITÉS LES PLUS RICHES (pour l'interface)")
    print("=" * 60)

    query = """
    SELECT ?entity (COUNT(?p) AS ?propCount) WHERE {
        ?entity ?p ?o .
        FILTER(STRSTARTS(STR(?entity), "http://tolkiengateway.net/resource/"))
    }
    GROUP BY ?entity
    ORDER BY DESC(?propCount)
    LIMIT 20
    """

    try:
        response = requests.get(endpoint, params={'query': query}, timeout=10)
        if response.status_code == 200:
            results = response.json()
            print("Entité | Nombre de propriétés")
            print("-" * 40)
            for binding in results['results']['bindings']:
                entity = binding['entity']['value'].split('/')[-1]
                count = binding['propCount']['value']
                print(f"{entity:30} | {count:>3}")
    except Exception as e:
        print(f"Erreur: {e}")


if __name__ == "__main__":
    explore_graph()
    find_entities_with_most_data()