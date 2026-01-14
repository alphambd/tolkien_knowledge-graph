from flask import Flask, request, render_template, Response
import requests
import re

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
    """Nettoyer les valeurs - VERSION FINALE"""
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

    # Nettoyer 'dated' (HTML/markup)
    if property_uri == "http://tolkiengateway.net/ontology/dated":
        value = re.sub(r'\{\{.*?\}\}', '', value)  # Enlève {{...}}
        value = re.sub(r'\|.*?=', ' ', value)      # Enlève |param=value
        value = re.sub(r'\}\}', '', value)         # Enlève les }} restants
        value = re.sub(r'website=VanityFair', '', value)  # Enlève website=

    # Nettoyage pour alternateName
    if property_uri == "http://schema.org/alternateName":
        value = value.replace("' (Q)'", " (Quenya), ")
        value = value.replace("' (S)'", " (Sindarin), ")
        value = value.replace("' (H)'", " (Haradrim), ")
        value = value.replace("' (K)'", " (Khuzdul), ")
        value = value.rstrip(', ')
        if value.endswith('(See below'):
            value = value.replace('(See below', '').strip().rstrip(',')

    # Nettoyer description (ajouter espaces)
    if property_uri == "http://schema.org/description":
        value = re.sub(r'([a-z])([A-Z])', r'\1 \2', value)

    # Nettoyer weapon (ajouter virgules)
    if property_uri == "http://tolkiengateway.net/ontology/weapon":
        value = re.sub(r'([a-z])([A-Z])', r'\1, \2', value)

    # Corriger "Maia (Wizard"
    if property_uri == "http://tolkiengateway.net/ontology/people":
        if value == "Maia (Wizard":
            value = "Maia (Wizard)"

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


if __name__ == '__main__':
    print("✅ Linked Data Interface ready!")
    print("🌐 HTML: http://localhost:5000/resource/Gandalf")
    print("📥 Download: http://localhost:5000/resource/Gandalf?format=ttl")
    print("🔍 Fuseki: http://localhost:3030/")
    app.run(debug=True, port=5000, host='0.0.0.0')