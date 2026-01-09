# Tolkien Knowledge Graph

This project builds a Knowledge Graph from the Tolkien Gateway wiki,
inspired by DBpedia and YAGO. The KG is enriched with external datasets
and exposed through SPARQL and Linked Data interfaces.




# Tolkien Knowledge Graph Project

## Project Overview
This project aims to build a **Knowledge Graph (KG)** from the Tolkien Gateway wiki, inspired by DBpedia and YAGO. 
The KG will represent characters, items, and locations from Tolkien's legendarium, enriched with external datasets and accessible via SPARQL and Linked Data interfaces.

## Sources of Data
- **Tolkien Gateway**: main wiki for extracting characters, places, and items.
- **Middle-earth: The Wizards (METW) cards**: JSON dataset of collectible cards.
- **The Lord of the Rings wiki CSV**: additional character data.
- Optional multilingual wikis or Wikipedia for labels in multiple languages.

## Technologies Planned
- **Programming Language**: Python 3.x
- **Triplestore**: Apache Fuseki
- **RDF Library**: rdflib
- **API Access**: MediaWiki API via HTTP requests (requests library)
- **RDF Output Format**: Turtle (.ttl)

## Project Structure




## Question : `list=allpages` avec distinction page/entity

**Script :** `generate_wiki_pages_entities.py`

**Ce qui a été fait :**
- Utilisation de l'API MediaWiki avec `action=query` et `list=allpages`
- Gestion de la pagination via le paramètre `continue` (token `apcontinue`)
- Récupération exhaustive de **23,038 pages** de Tolkien Gateway
- Pour chaque page X, création de deux URIs distinctes :
  - `http://example.org/tolkien/page/X` (le document wiki)
  - `http://example.org/tolkien/resource/X` (l'entité réelle)
- Lien établi via `foaf:primaryTopic` : `page/X → resource/X`
- Inspiration DBpedia/YAGO : même distinction conceptuelle

**Résultats :**
- Fichier RDF : `data/tolkien_pages_entities.ttl` (7.5 MB)
- Triples générés : 115,190
- Données dans Fuseki : 137,610 triples (avec métadonnées)