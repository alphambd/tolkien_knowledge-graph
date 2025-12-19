# WS_Project

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
