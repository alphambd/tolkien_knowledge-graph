"""
sparql_implicit_facts.py - SPARQL queries that reveal implicit facts
"""
import requests
import json

SPARQL_ENDPOINT = "http://localhost:3030/tolkienKG/sparql"

def query_implicit_facts():
    """Execute SPARQL queries that find implicit facts"""
    
    queries = {
        "implicit_family_relationships": """
            PREFIX schema: <http://schema.org/>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            
            # Find family relationships through inference
            SELECT ?person1 ?person2 ?relationship WHERE {
                {
                    # Direct parent-child (explicit)
                    ?person1 schema:children ?person2 .
                    BIND("child of" AS ?relationship)
                }
                UNION
                {
                    # Implicit: Grandparent through inference
                    ?person1 schema:children ?child .
                    ?child schema:children ?person2 .
                    BIND("grandchild of" AS ?relationship)
                }
                UNION
                {
                    # Implicit: Siblings through shared parents
                    ?parent schema:children ?person1 .
                    ?parent schema:children ?person2 .
                    FILTER(?person1 != ?person2)
                    BIND("sibling of" AS ?relationship)
                }
                UNION
                {
                    # Implicit: Related through sameAs links
                    ?person1 owl:sameAs ?same .
                    ?same schema:relatedTo ?person2 .
                    FILTER(?person1 != ?person2)
                    BIND("related through sameAs" AS ?relationship)
                }
            }
            ORDER BY ?person1 ?person2
            LIMIT 20
        """,
        
        "implicit_type_inheritance": """
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX schema: <http://schema.org/>
            
            # Find all types including inherited ones
            SELECT ?entity ?explicitType ?superType WHERE {
                ?entity rdf:type ?explicitType .
                ?explicitType rdfs:subClassOf* ?superType .
                FILTER(?explicitType != ?superType)
                FILTER(strstarts(str(?explicitType), "http://schema.org/"))
                FILTER(strstarts(str(?superType), "http://schema.org/"))
            }
            ORDER BY ?entity
            LIMIT 15
        """,
        
        "transitive_related_to": """
            PREFIX schema: <http://schema.org/>
            
            # Find transitive relationships (A relatedTo B, B relatedTo C → A relatedTo C)
            SELECT DISTINCT ?entity1 ?entity3 WHERE {
                ?entity1 schema:relatedTo+ ?entity3 .
                FILTER(!EXISTS { ?entity1 schema:relatedTo ?entity3 })
                FILTER(?entity1 != ?entity3)
            }
            ORDER BY ?entity1
            LIMIT 20
        """,
        
        "implicit_card_connections": """
            PREFIX tgwo: <http://tolkiengateway.net/ontology/>
            PREFIX schema: <http://schema.org/>
            
            # Entities connected through cards
            SELECT ?entity1 ?entity2 (COUNT(DISTINCT ?card) AS ?sharedCards) WHERE {
                ?entity1 tgwo:hasCardRepresentation ?card .
                ?entity2 tgwo:hasCardRepresentation ?card .
                FILTER(?entity1 != ?entity2)
            }
            GROUP BY ?entity1 ?entity2
            HAVING (?sharedCards > 0)
            ORDER BY DESC(?sharedCards)
            LIMIT 15
        """,
        
        "multilingual_label_coverage": """
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX schema: <http://schema.org/>
            
            # Check which entities have multilingual labels
            SELECT ?entity ?name (COUNT(DISTINCT ?lang) AS ?languages) (GROUP_CONCAT(DISTINCT ?lang; separator=", ") AS ?langList) WHERE {
                ?entity a schema:Person .
                ?entity schema:name ?name .
                OPTIONAL {
                    ?entity rdfs:label ?label .
                    BIND(LANG(?label) AS ?lang)
                }
            }
            GROUP BY ?entity ?name
            HAVING (?languages > 1)
            ORDER BY DESC(?languages)
            LIMIT 20
        """
    }
    
    print("=" * 70)
    print("IMPLICIT FACTS DISCOVERY WITH SPARQL")
    print("=" * 70)
    
    results = {}
    
    for query_name, sparql_query in queries.items():
        print(f"\n[{query_name}]")
        print("-" * 50)
        
        try:
            response = requests.get(
                SPARQL_ENDPOINT,
                params={'query': sparql_query},
                headers={'Accept': 'application/sparql-results+json'},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                bindings = data.get('results', {}).get('bindings', [])
                
                if bindings:
                    # Display header
                    vars_list = data['head']['vars']
                    header = " | ".join(vars_list)
                    print(header)
                    print("-" * len(header))
                    
                    # Display rows
                    for binding in bindings[:10]:  # First 10 results
                        row = []
                        for var in vars_list:
                            if var in binding:
                                value = binding[var]['value']
                                # Shorten URIs for display
                                if value.startswith('http://tolkiengateway.net/resource/'):
                                    value = value.split('/')[-1].replace('_', ' ')
                                elif value.startswith('http://schema.org/'):
                                    value = 'schema:' + value.split('/')[-1]
                                row.append(str(value)[:30])
                            else:
                                row.append("")
                        print(" | ".join(row))
                    
                    if len(bindings) > 10:
                        print(f"... and {len(bindings) - 10} more results")
                    
                    results[query_name] = {
                        'count': len(bindings),
                        'sample': bindings[:3]
                    }
                else:
                    print("No results found")
            else:
                print(f"Error: {response.status_code}")
                
        except Exception as e:
            print(f"Query failed: {e}")
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY OF IMPLICIT FACTS FOUND")
    print("=" * 70)
    
    for query_name, data in results.items():
        print(f"{query_name}: {data['count']} implicit facts discovered")
    
    return results

def create_implicit_facts_endpoint():
    """Create a Flask endpoint that serves queries with implicit facts"""
    
    endpoint_code = """
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)
SPARQL_ENDPOINT = "http://localhost:3030/tolkienKG/sparql"

IMPLICIT_QUERIES = {
    "family_tree": \"""
        PREFIX schema: <http://schema.org/>
        SELECT ?person ?parent ?grandparent WHERE {
            ?person schema:parent ?parent .
            OPTIONAL {
                ?parent schema:parent ?grandparent .
            }
        }
        LIMIT 50
    \""",
    
    "related_through_cards": \"""
        PREFIX tgwo: <http://tolkiengateway.net/ontology/>
        SELECT ?entity1 ?entity2 (GROUP_CONCAT(?cardName; separator=", ") AS ?sharedCards) WHERE {
            ?entity1 tgwo:hasCardRepresentation ?card .
            ?card schema:name ?cardName .
            ?entity2 tgwo:hasCardRepresentation ?card .
            FILTER(?entity1 != ?entity2)
        }
        GROUP BY ?entity1 ?entity2
        LIMIT 20
    \""",
    
    "multilingual_entities": \"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT ?entity (COUNT(DISTINCT ?lang) AS ?languages) WHERE {
            ?entity rdfs:label ?label .
            BIND(LANG(?label) AS ?lang)
        }
        GROUP BY ?entity
        HAVING (?languages > 1)
        ORDER BY DESC(?languages)
        LIMIT 20
    \"""
}

@app.route('/api/implicit/<query_name>')
def get_implicit_facts(query_name):
    '''Returns implicit facts from the knowledge graph'''
    
    if query_name not in IMPLICIT_QUERIES:
        return jsonify({"error": "Query not found"}), 404
    
    try:
        response = requests.get(
            SPARQL_ENDPOINT,
            params={'query': IMPLICIT_QUERIES[query_name]},
            headers={'Accept': 'application/sparql-results+json'},
            timeout=10
        )
        
        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({"error": "SPARQL query failed"}), 500
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/implicit')
def list_implicit_queries():
    '''Lists all available implicit fact queries'''
    return jsonify({
        "available_queries": list(IMPLICIT_QUERIES.keys()),
        "description": "These queries reveal implicit facts through inference"
    })

if __name__ == '__main__':
    print("Implicit Facts API running on http://localhost:5001")
    print("Available endpoints:")
    print("  /api/implicit - List queries")
    print("  /api/implicit/<query_name> - Execute query")
    app.run(port=5001, debug=False)
"""
    
    # Save the endpoint code
    with open("implicit_facts_api.py", "w") as f:
        f.write(endpoint_code)
    
    print("\n✓ Implicit facts API created: implicit_facts_api.py")
    print("\nTo start the API:")
    print("  python implicit_facts_api.py")
    print("\nThen access:")
    print("  http://localhost:5001/api/implicit")
    print("  http://localhost:5001/api/implicit/family_tree")

if __name__ == "__main__":
    # Test queries
    query_implicit_facts()
    
    # Create API endpoint
    create_implicit_facts_endpoint()