#!/usr/bin/env python3
"""
API MediaWiki pour récupérer les liens Wikipedia depuis Tolkien Gateway
"""

import requests
import json
from rdflib import Graph, URIRef, Namespace
import time
import sys

print("=" * 70)
print("API MEDIAWIKI POUR LES ALIGNEMENTS DBpedia/YAGO")
print("=" * 70)

# Configuration de l'API Tolkien Gateway
API_URL = "https://tolkiengateway.net/w/api.php"

# Namespaces
TGW = Namespace("http://tolkiengateway.net/resource/")
DBPEDIA = Namespace("http://dbpedia.org/resource/")
YAGO = Namespace("http://yago-knowledge.org/resource/")
OWL = Namespace("http://www.w3.org/2002/07/owl#")


def get_external_links_api(page_title):
    """Utilise l'API MediaWiki pour récupérer les liens externes"""

    params = {
        "action": "query",
        "titles": page_title,
        "prop": "extlinks",
        "ellimit": "max",
        "format": "json"
    }

    try:
        response = requests.get(API_URL, params=params, timeout=10)
        data = response.json()

        wikipedia_links = []
        pages = data.get("query", {}).get("pages", {})

        for page_id, page_info in pages.items():
            if page_id != "-1" and "extlinks" in page_info:
                for link in page_info["extlinks"]:
                    url = link.get("*", "")
                    # Filtrer les liens Wikipedia
                    if any(wiki in url.lower() for wiki in ["wikipedia.org", "wiki/"]):
                        wikipedia_links.append(url)

        return wikipedia_links
    except Exception as e:
        print(f" Erreur API pour '{page_title}': {e}")
        return []


def extract_wikipedia_title(url):
    """Extrait le titre depuis l'URL Wikipedia"""
    if "wikipedia.org/wiki/" in url:
        title = url.split("wiki/")[-1]
        # Nettoyer
        title = title.split("#")[0]  # Enlever les ancres
        title = title.split("?")[0]  # Enlever les paramètres
        title = title.replace("_", " ")
        return title
    return None


def main():
    """Fonction principale"""

    # Liste de test (5 personnages pour la démo)
    test_characters = ["Elrond", "Gandalf", "Aragorn", "Galadriel", "Sauron"]

    g = Graph()
    alignments_created = 0

    print("\n CONNEXION À L'API MEDIAWIKI DE TOLKIEN GATEWAY...")
    print(f"URL API: {API_URL}")
    print(f"Paramètre: prop=extlinks (récupère les liens externes)")
    print()

    for character in test_characters:
        print(f"\n Analyse de: {character}")

        # 1. Appel API MediaWiki
        print(f"    Appel API: action=query, titles={character}, prop=extlinks")
        external_links = get_external_links_api(character)

        if not external_links:
            print(f"   Warning: Aucun lien externe trouvé")
            continue

        print(f"    {len(external_links)} lien(s) externe(s) trouvé(s)")

        # 2. Filtrer les liens Wikipedia
        wikipedia_links = []
        for link in external_links:
            if "wikipedia.org" in link.lower():
                wikipedia_links.append(link)
                print(f"   Wikipedia: {link}")

        if not wikipedia_links:
            print(f"    Aucun lien Wikipedia trouvé")
            continue

        # 3. Prendre le premier lien Wikipedia (le plus pertinent)
        wiki_url = wikipedia_links[0]
        wiki_title = extract_wikipedia_title(wiki_url)

        if wiki_title:
            # 4. Créer les alignements RDF
            tgw_uri = TGW[character.replace(" ", "_")]
            dbpedia_uri = DBPEDIA[wiki_title.replace(" ", "_")]
            yago_uri = YAGO[wiki_title.replace(" ", "_")]

            # 5. Ajouter les triplets owl:sameAs
            g.add((tgw_uri, OWL.sameAs, dbpedia_uri))
            g.add((tgw_uri, OWL.sameAs, yago_uri))

            alignments_created += 2

            print(f"    Alignements créés:")
            print(f"      {tgw_uri}")
            print(f"        owl:sameAs {dbpedia_uri}")
            print(f"        owl:sameAs {yago_uri}")
        else:
            print(f"    Impossible d'extraire le titre Wikipedia")

        # Pause pour respecter l'API
        time.sleep(1)

    # Sauvegarder les résultats
    if alignments_created > 0:
        output_file = "data/api_alignments.ttl"
        g.serialize(output_file, format="turtle")

        print("\n" + "=" * 70)
        print(" RÉSULTATS DE L'API MEDIAWIKI")
        print("=" * 70)
        print(f"Personnages analysés: {len(test_characters)}")
        print(f"Liens Wikipedia trouvés: {sum(1 for c in test_characters if get_external_links_api(c))}")
        print(f"Alignements créés: {alignments_created} triplets owl:sameAs")
        print(f"Fichier généré: {output_file}")

        # Afficher un exemple JSON de l'API
        print(f"\n EXEMPLE DE RÉPONSE API (Elrond):")
        example_response = {
            "query": {
                "pages": {
                    "12345": {
                        "pageid": 12345,
                        "ns": 0,
                        "title": "Elrond",
                        "extlinks": [
                            {"*": "https://en.wikipedia.org/wiki/Elrond"},
                            {"*": "https://lotr.fandom.com/wiki/Elrond"}
                        ]
                    }
                }
            }
        }
        print(json.dumps(example_response, indent=2)[:300] + "...")

    else:
        print("\n Aucun alignement créé. Vérifiez la connexion à l'API.")


if __name__ == "__main__":
    main()