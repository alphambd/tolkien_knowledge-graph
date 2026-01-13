import requests

# Test les deux
urls = [
    "http://localhost:3030/tolkienKG/query",
    "http://localhost:3030/tolkienKG/sparql"
]

query = "SELECT * WHERE { ?s ?p ?o } LIMIT 1"

for url in urls:
    print(f"\nTest: {url}")
    try:
        r = requests.get(url, params={'query': query}, timeout=3)
        print(f"Status: {r.status_code}")
        if r.status_code == 200:
            print("✅ Works!")
        else:
            print(f"❌ Failed: {r.text[:100]}")
    except Exception as e:
        print(f"❌ Error: {e}")