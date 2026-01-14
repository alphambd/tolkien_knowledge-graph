"""
check_data_structure.py - Vérifie quelles propriétés existent vraiment
"""
import requests
import json

SPARQL_ENDPOINT = "http://localhost:3030/tolkienKG/sparql"

def check_existing_properties():
    """Vérifie quelles propriétés existent dans vos données"""
    
    queries = {
        "Toutes les propriétés utilisées": """
            SELECT DISTINCT ?property (COUNT(*) AS ?count) WHERE {
                ?s ?property ?o .
            }
            GROUP BY ?property
            ORDER BY DESC(?count)
            LIMIT 20
        """,
        
        "Types d'entités": """
            SELECT DISTINCT ?type (COUNT(*) AS ?count) WHERE {
                ?s a ?type .
            }
            GROUP BY ?type
            ORDER BY DESC(?count)
        """,
        
        "Propriétés pour les Personnes": """
            SELECT DISTINCT ?property WHERE {
                ?person a <http://schema.org/Person> .
                ?person ?property ?value .
            }
            LIMIT 20
        """,
        
        "Labels avec langues": """
            SELECT ?entity ?label (LANG(?label) AS ?lang) WHERE {
                ?entity rdfs:label ?label .
                FILTER(LANG(?label) != "")
            }
            LIMIT 10
        """
    }
    
    print("=" * 70)
    print("VÉRIFICATION DE LA STRUCTURE DES DONNÉES")
    print("=" * 70)
    
    for name, query in queries.items():
        print(f"\n{name}")
        print("-" * 50)
        
        try:
            response = requests.get(
                SPARQL_ENDPOINT,
                params={'query': query, 'format': 'json'},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                bindings = data.get('results', {}).get('bindings', [])
                
                if bindings:
                    for binding in bindings:
                        row = []
                        for var in data['head']['vars']:
                            if var in binding:
                                value = binding[var]['value']
                                # Raccourcir les URIs
                                if 'schema.org' in value:
                                    value = 'schema:' + value.split('/')[-1]
                                elif 'tolkiengateway.net/ontology' in value:
                                    value = 'tgwo:' + value.split('/')[-1]
                                elif 'rdfs#' in value:
                                    value = 'rdfs:' + value.split('#')[-1]
                                row.append(f"{var}: {value}")
                        print(" | ".join(row))
                else:
                    print("AUCUN RÉSULTAT")
            else:
                print(f"Erreur: {response.status_code}")
                
        except Exception as e:
            print(f"Erreur: {e}")

if __name__ == "__main__":
    check_existing_properties()