from flask import Flask, request, jsonify
import requests

app = Flask(__name__)
SPARQL_ENDPOINT = "http://localhost:3030/tolkienKG/sparql"

IMPLICIT_QUERIES = {
    "family_relationships": """
        PREFIX schema: <http://schema.org/>
        
        # Find family relationships (using schema:children which EXISTS in your data)
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
        }
        ORDER BY ?person1 ?person2
        LIMIT 30
    """,
    
    "multilingual_entities": """
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX schema: <http://schema.org/>
        
        # Check which entities have multilingual labels
        SELECT ?entity ?name (COUNT(DISTINCT ?lang) AS ?languages) 
               (GROUP_CONCAT(DISTINCT ?lang; separator=", ") AS ?langList) 
        WHERE {
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
    """,
    
    "transitive_connections": """
        PREFIX schema: <http://schema.org/>
        
        # Find transitive relationships
        SELECT DISTINCT ?entity1 ?entity3 WHERE {
            ?entity1 schema:relatedTo+ ?entity3 .
            FILTER(!EXISTS { ?entity1 schema:relatedTo ?entity3 })
            FILTER(?entity1 != ?entity3)
        }
        ORDER BY ?entity1
        LIMIT 20
    """,
    
    "type_inheritance": """
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
    
    "most_described_characters": """
        PREFIX schema: <http://schema.org/>
        
        # Find characters with most properties
        SELECT ?character ?name (COUNT(?p) AS ?propertyCount) WHERE {
            ?character a schema:Person .
            ?character schema:name ?name .
            ?character ?p ?o .
        }
        GROUP BY ?character ?name
        ORDER BY DESC(?propertyCount)
        LIMIT 10
    """
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
            return jsonify({"error": "SPARQL query failed", "status": response.status_code}), 500
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/implicit')
def list_implicit_queries():
    '''Lists all available implicit fact queries'''
    queries_info = {
        "family_relationships": "Find family relationships (parent/child/grandparent)",
        "multilingual_entities": "Entities with labels in multiple languages",
        "transitive_connections": "Indirect connections through relatedTo",
        "type_inheritance": "Type inheritance chains",
        "most_described_characters": "Characters with most properties"
    }
    
    return jsonify({
        "available_queries": list(IMPLICIT_QUERIES.keys()),
        "queries_info": queries_info,
        "description": "These queries reveal implicit facts through inference",
        "note": "Data based on Tolkien Gateway with schema.org alignment"
    })

@app.route('/')
def home():
    '''Home page with instructions'''
    return '''
    <h1>Tolkien Knowledge Graph - Implicit Facts API</h1>
    <p>Access implicit facts discovered through inference.</p>
    
    <h2>Available Endpoints:</h2>
    <ul>
        <li><a href="/api/implicit">/api/implicit</a> - List all queries</li>
        <li><a href="/api/implicit/family_relationships">/api/implicit/family_relationships</a> - Family relationships</li>
        <li><a href="/api/implicit/multilingual_entities">/api/implicit/multilingual_entities</a> - Multilingual labels</li>
        <li><a href="/api/implicit/transitive_connections">/api/implicit/transitive_connections</a> - Indirect connections</li>
        <li><a href="/api/implicit/type_inheritance">/api/implicit/type_inheritance</a> - Type inheritance</li>
        <li><a href="/api/implicit/most_described_characters">/api/implicit/most_described_characters</a> - Most described characters</li>
    </ul>
    
    <h2>Example Usage:</h2>
    <pre>
    curl http://localhost:5001/api/implicit/family_relationships
    curl -H "Accept: application/json" http://localhost:5001/api/implicit/multilingual_entities
    </pre>
    
    <p><a href="http://localhost:3030">SPARQL Endpoint (Fuseki)</a> | 
       <a href="http://localhost:5000">Linked Data Interface</a></p>
    '''

if __name__ == '__main__':
    print("=" * 60)
    print("IMPLICIT FACTS API - TOLKIEN KNOWLEDGE GRAPH")
    print("=" * 60)
    print("Running on http://localhost:5001")
    print("\nAvailable endpoints:")
    for query_name in IMPLICIT_QUERIES.keys():
        print(f"  http://localhost:5001/api/implicit/{query_name}")
    print("\nHome page: http://localhost:5001")
    print("=" * 60)
    
    app.run(port=5001, debug=False)