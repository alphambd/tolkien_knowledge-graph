from flask import Flask, request, render_template, Response, jsonify
import requests
import re
import json

app = Flask(__name__, template_folder='../templates')
SPARQL_ENDPOINT = "http://localhost:3030/tolkienKG/query"
BASE_URI = "http://tolkiengateway.net/resource/"


@app.route('/')
def home():
    return render_template('home.html')


@app.route('/resource/<entity_name>')
def linked_data(entity_name):
    """Linked Data interface with content negotiation"""
    entity_uri = BASE_URI + entity_name

    # Check if entity exists
    check_query = f"ASK {{ <{entity_uri}> ?p ?o . }}"
    try:
        response = requests.get(
            SPARQL_ENDPOINT,
            params={'query': check_query},
            headers={'Accept': 'application/sparql-results+json'},
            timeout=5
        )

        if response.status_code != 200 or not response.json()['boolean']:
            return "Entity not found", 404
    except:
        return "Error connecting to SPARQL endpoint", 500

    # Content negotiation
    accept_header = request.headers.get('Accept', '')

    if 'text/html' in accept_header or not accept_header:
        if request.args.get('format') == 'ttl':
            return get_entity_turtle(entity_uri, entity_name, download=True)
        return render_entity_html(entity_uri, entity_name)
    else:
        return get_entity_turtle(entity_uri, entity_name, download=False)


def render_entity_html(entity_uri, entity_name):
    """Render HTML page for entity - VERSION FINALE COMPLÈTE"""
    # 1. Récupérer TOUTES les propriétés littérales
    query_all = f"""
    SELECT ?property ?value WHERE {{
        <{entity_uri}> ?property ?value .
        FILTER (isLiteral(?value))
    }}
    ORDER BY ?property
    """

    # 2. Récupérer les relatedTo
    query_related = f"""
    SELECT ?value WHERE {{
        <{entity_uri}> <http://schema.org/relatedTo> ?value .
    }}
    ORDER BY ?value
    """

    properties = []
    literal_values = {}

    # Récupérer et traiter les littéraux
    try:
        response = requests.get(
            SPARQL_ENDPOINT,
            params={'query': query_all, 'format': 'json'},
            timeout=10
        )

        if response.status_code == 200:
            results = response.json()

            # Regrouper les valeurs par propriété
            for binding in results['results']['bindings']:
                prop_uri = binding['property']['value']
                value = binding['value']['value']

                if prop_uri not in literal_values:
                    literal_values[prop_uri] = []

                literal_values[prop_uri].append(value)

            # Traiter chaque propriété
            for prop_uri, values in literal_values.items():
                if prop_uri == "http://www.w3.org/2000/01/rdf-schema#label":
                    # On ignore rdfs:label puisqu'on a schema:name
                    continue
                elif prop_uri == "http://schema.org/birthDate":
                    # Fusionner les dates de naissance
                    merged = " and ".join(sorted(set(values)))
                    properties.append({
                        'property': prop_uri,
                        'value': clean_value(merged, prop_uri)
                    })
                elif len(values) == 1:
                    # Une seule valeur
                    properties.append({
                        'property': prop_uri,
                        'value': clean_value(values[0], prop_uri)
                    })
                else:
                    # Valeurs multiples uniques
                    unique_values = sorted(set(values))
                    for val in unique_values:
                        properties.append({
                            'property': prop_uri,
                            'value': clean_value(val, prop_uri)
                        })

    except Exception as e:
        print(f"Error literals: {e}")

    # Récupérer et traiter les relatedTo
    try:
        response = requests.get(
            SPARQL_ENDPOINT,
            params={'query': query_related, 'format': 'json'},
            timeout=10
        )

        if response.status_code == 200:
            results = response.json()
            for binding in results['results']['bindings']:
                value = binding['value']['value']

                # Créer un nom d'affichage propre
                if value.startswith(BASE_URI):
                    display_name = value.replace(BASE_URI, "").replace("_", " ")
                else:
                    # Extraire le dernier segment de l'URI
                    parts = value.split('/')
                    last_part = parts[-1] if parts else value
                    display_name = last_part.replace("_", " ").replace("%20", " ")

                properties.append({
                    'property': "http://schema.org/relatedTo",
                    'value': value,
                    'display_value': display_name
                })

    except Exception as e:
        print(f"Error relatedTo: {e}")

    # Trier les propriétés intelligemment
    properties.sort(key=lambda x: sort_key(x['property'], x.get('value', '')))

    return render_template('entity.html',
                           entity_uri=entity_uri,
                           entity_name=entity_name,
                           properties=properties)


def sort_key(property_uri, value):
    """Clé de tri intelligente"""
    # Priorité 0: Nom
    if property_uri == "http://schema.org/name":
        return (0, 0)

    # Priorité 1: Description
    if property_uri == "http://schema.org/description":
        return (1, 0)

    # Priorité 2: Informations d'identité
    if property_uri in [
        "http://schema.org/additionalType",
        "http://schema.org/alternateName",
        "http://schema.org/birthDate",
        "http://schema.org/gender"
    ]:
        return (2, list([
            "http://schema.org/additionalType",
            "http://schema.org/alternateName",
            "http://schema.org/birthDate",
            "http://schema.org/gender"
        ]).index(property_uri))

    # Priorité 3: Autres propriétés schema.org
    if "schema.org" in property_uri:
        return (3, property_uri)

    # Priorité 4: relatedTo (à la fin)
    if property_uri == "http://schema.org/relatedTo":
        return (5, value.lower())

    # Priorité 5: Ontologie Tolkien
    if "tolkiengateway.net/ontology" in property_uri:
        return (4, property_uri)

    # Priorité 6: Autres
    return (6, property_uri)


def clean_value(value, property_uri=""):
    """Nettoyer les valeurs - VERSION AMÉLIORÉE"""
    if not isinstance(value, str):
        return value

    # Nettoyages généraux
    value = value.replace("''", "'").strip()

    # Nettoyages spécifiques par propriété
    if property_uri == "http://schema.org/alternateName":
        value = value.replace("' (Q)'", " (Quenya), ")
        value = value.replace("' (S)'", " (Sindarin), ")
        value = value.replace("' (H)'", " (Haradrim), ")
        value = value.replace("' (K)'", " (Khuzdul), ")
        value = value.rstrip(', ')
        # Supprimer le texte problématique
        if value.endswith('(See below'):
            value = value.replace('(See below', '').strip().rstrip(',')

    elif property_uri == "http://schema.org/birthDate":
        # S'assurer que "Timeless Halls" est présent si disponible
        if "Creation of the Ainur" in value and "Timeless" not in value:
            # On pourrait chercher dans les autres valeurs, mais on garde simple
            pass

    elif property_uri == "http://schema.org/description":
        # Ajouter des espaces entre les titres
        value = re.sub(r'([a-z])([A-Z])', r'\1 \2', value)

    elif property_uri == "http://tolkiengateway.net/ontology/dates":
        value = value.replace(', - ', ' - ')

    elif property_uri == "http://tolkiengateway.net/ontology/died":
        if value.startswith('Sailed west on'):
            value = value.replace('Sailed west on ', '')

    elif property_uri == "http://tolkiengateway.net/ontology/weapon":
        value = re.sub(r'([a-z])([A-Z])', r'\1, \2', value)

    elif property_uri == "http://tolkiengateway.net/ontology/people":
        if value == "Maia (Wizard":
            value = "Maia (Wizard)"

    # Supprimer les espaces multiples
    value = ' '.join(value.split())

    return value


def clean_value(value, property_uri=""):
    """Nettoyer les valeurs - DERNIÈRES CORRECTIONS"""
    if not isinstance(value, str):
        return value

    value = value.replace("''", "'").strip()

    # Nettoyer les dates (virgules à la fin)
    if property_uri in ["http://tolkiengateway.net/ontology/dates",
                        "http://tolkiengateway.net/ontology/died",
                        "http://tolkiengateway.net/ontology/sailedwest"]:
        value = value.rstrip(',')
        value = value.replace(', - ', ' - ')

    # Supprimer "Sailed west on" si présent
    if property_uri == "http://tolkiengateway.net/ontology/died":
        if value.startswith('Sailed west on '):
            value = value.replace('Sailed west on ', '')

    # Supprimer les espaces multiples
    value = ' '.join(value.split())

    return value

def get_entity_turtle(entity_uri, entity_name, download=False):
    """Get Turtle representation of entity"""
    query = f"""
    CONSTRUCT {{
        <{entity_uri}> ?p ?o .
    }}
    WHERE {{
        <{entity_uri}> ?p ?o .
        FILTER (isLiteral(?o) || ?p = <http://schema.org/relatedTo>)
    }}
    LIMIT 100
    """

    try:
        response = requests.get(
            SPARQL_ENDPOINT,
            params={'query': query},
            headers={'Accept': 'text/turtle'},
            timeout=10
        )

        if response.status_code == 200:
            if download:
                return Response(
                    response.text,
                    mimetype='text/turtle',
                    headers={'Content-Disposition': f'attachment; filename="{entity_name}.ttl"'}
                )
            else:
                return Response(response.text, mimetype='text/turtle')
        else:
            return "Error fetching RDF data", 500
    except Exception as e:
        print(f"Error: {e}")
        return "Error connecting to SPARQL endpoint", 500


@app.route('/download/<entity_name>.ttl')
def download_turtle(entity_name):
    """Route alternative pour télécharger Turtle"""
    entity_uri = BASE_URI + entity_name
    return get_entity_turtle(entity_uri, entity_name, download=True)



# ---------------------------
# IMPLICIT FACTS SECTION
# ---------------------------

@app.route('/implicit-facts')
def implicit_facts_home():
    """Home page for implicit facts discovery"""
    return render_template('implicit_facts.html')

@app.route('/api/implicit-facts/<query_name>')
def get_implicit_facts_api(query_name):
    """API endpoint for implicit facts"""
    
    IMPLICIT_QUERIES = {
        "family_relationships": """
            PREFIX schema: <http://schema.org/>
            
            # Find family relationships
            SELECT ?person1 ?person2 ?relationship WHERE {
                {
                    # Direct parent-child
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
        
        "most_described": """
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
    
if __name__ == '__main__':
    print("- Linked Data Interface ready!")
    print("- HTML: http://localhost:5000/resource/Gandalf")
    print("- Download: http://localhost:5000/resource/Gandalf?format=ttl")
    print("- Fuseki: http://localhost:3030/")
    app.run(debug=True, port=5001, host='0.0.0.0')