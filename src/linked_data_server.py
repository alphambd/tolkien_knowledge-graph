"""
Linked Data Interface for Tolkien Knowledge Graph
Requirements 8: Linked Data interface serving Turtle and HTML
"""
from flask import Flask, request, render_template_string
import requests
from rdflib import Graph, Namespace, Literal, URIRef
from rdflib.plugins.sparql import prepareQuery
import urllib.parse

app = Flask(__name__)

# Configuration
SPARQL_ENDPOINT = "http://localhost:3030/tolkienKG/sparql"
BASE_URI = "http://tolkiengateway.net/resource/"

# Namespaces
SCHEMA = Namespace("http://schema.org/")
TGW = Namespace("http://tolkiengateway.net/resource/")
TGWO = Namespace("http://tolkiengateway.net/ontology/")
RDF = Namespace("http://www.w3.org/1999/02/22-rdf-syntax-ns#")
RDFS = Namespace("http://www.w3.org/2000/01/rdf-schema#")

# HTML template
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{{ entity_name }} - Tolkien Knowledge Graph</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        h1 { color: #2c3e50; }
        .property { margin: 15px 0; }
        .prop-name { font-weight: bold; color: #2980b9; }
        .prop-value a { color: #27ae60; text-decoration: none; }
        .prop-value a:hover { text-decoration: underline; }
        .format-links { margin: 20px 0; padding: 10px; background: #f8f9fa; }
        .uri { font-family: monospace; color: #7f8c8d; font-size: 0.9em; }
        table { border-collapse: collapse; width: 100%%; margin: 20px 0; }
        th, td { border: 1px solid #ddd; padding: 12px; text-align: left; }
        th { background-color: #f2f2f2; }
    </style>
</head>
<body>
    <h1>{{ entity_name }}</h1>

    <div class="uri">
        <strong>URI:</strong> <a href="{{ entity_uri }}">{{ entity_uri }}</a>
    </div>

    <div class="format-links">
        <strong>Available formats:</strong>
        <a href="?format=turtle">Turtle</a> |
        <a href="?format=json">JSON-LD</a> |
        <a href="?format=xml">RDF/XML</a>
    </div>

    {% if description %}
    <div class="property">
        <span class="prop-name">Description:</span>
        <span class="prop-value">{{ description }}</span>
    </div>
    {% endif %}

    {% if properties %}
    <h2>Properties</h2>
    <table>
        <thead>
            <tr>
                <th>Property</th>
                <th>Value</th>
            </tr>
        </thead>
        <tbody>
            {% for prop in properties %}
            <tr>
                <td class="prop-name">{{ prop.pretty_name }}</td>
                <td class="prop-value">
                    {% if prop.is_uri %}
                    <a href="{{ prop.value }}">{{ prop.display_value }}</a>
                    {% else %}
                    {{ prop.display_value }}
                    {% endif %}
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
    {% endif %}

    {% if links %}
    <h2>Related Links</h2>
    <ul>
        {% for link in links %}
        <li><a href="{{ link.url }}">{{ link.label }}</a></li>
        {% endfor %}
    </ul>
    {% endif %}

    <hr>
    <p>
        <small>
            Data extracted from <a href="https://tolkiengateway.net">Tolkien Gateway</a>.
            <a href="http://localhost:3030/tolkienKG">SPARQL Endpoint</a>
        </small>
    </p>
</body>
</html>
"""


def query_sparql(entity_uri, format="turtle"):
    """Execute a SPARQL query to get entity description"""

    # Query for entity description (all properties)
    sparql_query = """
    PREFIX schema: <http://schema.org/>
    PREFIX tgw: <http://tolkiengateway.net/resource/>
    PREFIX tgwo: <http://tolkiengateway.net/ontology/>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT DISTINCT ?property ?value WHERE {
        <%s> ?property ?value .
        FILTER (!isBlank(?value))
    }
    ORDER BY ?property
    """ % entity_uri

    # Query for entity type and label
    type_query = """
    PREFIX schema: <http://schema.org/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT ?type ?label WHERE {
        <%s> a ?type .
        OPTIONAL { <%s> rdfs:label ?label }
        OPTIONAL { <%s> schema:name ?label }
    }
    """ % (entity_uri, entity_uri, entity_uri)

    try:
        # Execute queries
        params = {
            'query': sparql_query,
            'format': 'json'
        }

        response = requests.get(SPARQL_ENDPOINT, params=params, timeout=10)

        if response.status_code == 200:
            return response.json()
        else:
            print(f"SPARQL error: {response.status_code}")
            return None

    except Exception as e:
        print(f"Query error: {e}")
        return None


def generate_turtle(entity_uri, data):
    """Generate Turtle representation from query results"""
    if not data or 'results' not in data or 'bindings' not in data['results']:
        return "# No data found for " + entity_uri

    g = Graph()

    # Add namespaces
    g.bind("schema", SCHEMA)
    g.bind("tgw", TGW)
    g.bind("tgwo", TGWO)
    g.bind("rdf", RDF)
    g.bind("rdfs", RDFS)

    # Parse results and add triples
    for binding in data['results']['bindings']:
        prop = binding['property']['value']
        value = binding['value']

        # Create proper RDF terms
        subject = URIRef(entity_uri)
        predicate = URIRef(prop)

        if value['type'] == 'uri':
            obj = URIRef(value['value'])
        elif value['type'] == 'literal' and 'datatype' in value:
            obj = Literal(value['value'], datatype=value['datatype'])
        elif value['type'] == 'literal' and 'xml:lang' in value:
            obj = Literal(value['value'], lang=value['xml:lang'])
        else:
            obj = Literal(value['value'])

        g.add((subject, predicate, obj))

    return g.serialize(format='turtle')


def format_property_name(prop_uri):
    """Format property URI for display"""
    if 'schema.org' in prop_uri:
        return prop_uri.split('/')[-1].replace('_', ' ')
    elif 'tolkiengateway.net/ontology' in prop_uri:
        return prop_uri.split('/')[-1].replace('_', ' ')
    else:
        return prop_uri


@app.route('/resource/<path:entity_name>')
def entity_description(entity_name):
    """Linked Data interface - returns Turtle or HTML based on Accept header"""

    # Decode URL-encoded entity name
    entity_name = urllib.parse.unquote(entity_name)

    # Construct full URI (use your actual URI pattern)
    entity_uri = f"{BASE_URI}{entity_name.replace(' ', '_')}"

    # Check format parameter or Accept header
    format_param = request.args.get('format', '').lower()
    accept_header = request.headers.get('Accept', '')

    # Query SPARQL endpoint
    data = query_sparql(entity_uri)

    # Return Turtle if requested
    if format_param == 'turtle' or 'text/turtle' in accept_header:
        turtle_data = generate_turtle(entity_uri, data)
        return turtle_data, 200, {'Content-Type': 'text/turtle'}

    # Return HTML (default)
    properties = []
    description = None

    if data and 'results' in data and 'bindings' in data['results']:
        for binding in data['results']['bindings']:
            prop_uri = binding['property']['value']
            value = binding['value']

            # Extract display values
            prop_name = format_property_name(prop_uri)

            if value['type'] == 'uri':
                display_value = value['value'].split('/')[-1].replace('_', ' ')
                is_uri = True
            else:
                display_value = value['value']
                is_uri = False

            # Special handling for description
            if 'description' in prop_name.lower() or 'abstract' in prop_name.lower():
                description = display_value
                continue

            properties.append({
                'name': prop_uri,
                'pretty_name': prop_name,
                'value': value['value'] if is_uri else None,
                'display_value': display_value,
                'is_uri': is_uri
            })

    # Additional links
    links = [
        {'url': f'https://tolkiengateway.net/wiki/{entity_name.replace(" ", "_")}',
         'label': 'Tolkien Gateway Page'},
        {'url': f'http://localhost:3030/tolkienKG?query={urllib.parse.quote(f"SELECT * WHERE {{ <{entity_uri}> ?p ?o }}")}',
         'label': 'SPARQL Query'}
    ]

    html = render_template_string(
        HTML_TEMPLATE,
        entity_name=entity_name,
        entity_uri=entity_uri,
        description=description,
        properties=properties,
        links=links
    )

    return html, 200, {'Content-Type': 'text/html'}


@app.route('/')
def home():
    """Home page with instructions"""
    return """
    <h1>Tolkien Knowledge Graph - Linked Data Interface</h1>
    <p>Access entities via: <code>/resource/&lt;entity_name&gt;</code></p>
    <p>Examples:</p>
    <ul>
        <li><a href="/resource/Gandalf">/resource/Gandalf</a> (HTML)</li>
        <li><a href="/resource/Gandalf?format=turtle">/resource/Gandalf?format=turtle</a> (Turtle)</li>
        <li><a href="/resource/Elrond">/resource/Elrond</a></li>
        <li><a href="/resource/Aragorn">/resource/Aragorn</a></li>
    </ul>
    <p>SPARQL Endpoint: <a href="http://localhost:3030/tolkienKG">http://localhost:3030/tolkienKG</a></p>
    """


if __name__ == '__main__':
    print("=" * 60)
    print("Linked Data Interface - Tolkien Knowledge Graph")
    print("=" * 60)
    print(f"Server starting on http://localhost:5000")
    print(f"SPARQL endpoint: {SPARQL_ENDPOINT}")
    print("\nTest with:")
    print("  http://localhost:5000/resource/Gandalf")
    print("  curl -H 'Accept: text/turtle' http://localhost:5000/resource/Gandalf")
    print("=" * 60)

    app.run(host='0.0.0.0', port=5000, debug=True)