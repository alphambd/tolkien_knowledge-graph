from flask import Flask, request, render_template, Response
import requests
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
        # Vérifier si on veut télécharger en Turtle via paramètre
        if request.args.get('format') == 'ttl':
            return get_entity_turtle(entity_uri, entity_name, download=True)
        return render_entity_html(entity_uri, entity_name)
    else:
        # Return Turtle pour la négociation de contenu
        return get_entity_turtle(entity_uri, entity_name, download=False)


def render_entity_html(entity_uri, entity_name):
    """Render HTML page for entity"""
    # Get entity data
    query = f"""
    PREFIX schema: <http://schema.org/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT ?property ?value WHERE {{
        {{
            <{entity_uri}> ?property ?value .
            FILTER(isLiteral(?value))
        }}
        UNION
        {{
            <{entity_uri}> ?property ?value .
            FILTER(!isLiteral(?value))
        }}
        UNION
        {{
            ?value ?property <{entity_uri}> .
        }}
    }}
    LIMIT 50
    """

    properties = []
    try:
        response = requests.get(
            SPARQL_ENDPOINT,
            params={'query': query},
            headers={'Accept': 'application/sparql-results+json'},
            timeout=10
        )

        if response.status_code == 200:
            results = response.json()
            for binding in results['results']['bindings']:
                properties.append({
                    'property': binding['property']['value'],
                    'value': binding['value']['value']
                })
    except:
        pass

    return render_template('entity.html',
                           entity_uri=entity_uri,
                           entity_name=entity_name,
                           properties=properties)


def get_entity_turtle(entity_uri, entity_name, download=False):
    """Get Turtle representation of entity"""
    query = f"""
    CONSTRUCT {{
        <{entity_uri}> ?p ?o .
        ?s ?p2 <{entity_uri}> .
    }}
    WHERE {{
        {{ <{entity_uri}> ?p ?o . }}
        UNION
        {{ ?s ?p2 <{entity_uri}> . }}
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
                # Pour téléchargement avec nom de fichier
                return Response(
                    response.text,
                    mimetype='text/turtle',
                    headers={
                        'Content-Disposition': f'attachment; filename="{entity_name}.ttl"'
                    }
                )
            else:
                # Pour négociation de contenu standard
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
    print(" Linked Data Interface ready!")
    print(" HTML: http://localhost:5000/resource/Gandalf")
    print(" Turtle: curl -H 'Accept: text/turtle' http://localhost:5000/resource/Gandalf")
    print(" Download: http://localhost:5000/resource/Gandalf?format=ttl")
    app.run(debug=True, port=5000, host='0.0.0.0')