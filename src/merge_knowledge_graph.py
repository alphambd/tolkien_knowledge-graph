"""
merge_knowledge_graph.py - VERSION AMÉLIORÉE
Merges all Turtle files including multilingual labels
"""
from rdflib import Graph, Namespace, RDF, RDFS
import os

def merge_all_knowledge_graphs():
    """Merges all Turtle files in the project into a single KG."""

    print("=" * 60)
    print("COMPLETE KNOWLEDGE GRAPH MERGE WITH MULTILINGUAL SUPPORT")
    print("=" * 60)

    # Initialize final graph
    final_graph = Graph()

    # Namespaces
    SCHEMA = Namespace("http://schema.org/")
    TGW = Namespace("http://tolkiengateway.net/resource/")
    TGWO = Namespace("http://tolkiengateway.net/ontology/")

    # Bind namespaces
    final_graph.bind("schema", SCHEMA)
    final_graph.bind("tgw", TGW)
    final_graph.bind("tgwo", TGWO)
    final_graph.bind("rdfs", RDFS)
    final_graph.bind("rdf", RDF)

    # Fichiers à fusionner
    files_to_merge = [
        ("data/ontology.ttl", "Ontology Definitions"),
        ("data/all_characters_schema.ttl", "Characters"),
        ("data/tolkien_pages_entities.ttl", "Pages/Entities"),
        ("data/metw_integration_cards.ttl", "METW Cards"),
        ("data/multilingual_labels_only.ttl", "Multilingual Labels"),
        ("data/api_alignments.ttl", "DBpedia/YAGO Alignments"),
        #("data/elrond_schema.ttl", "Elrond Example"),  # ← Optionnel
    ]

    total_triples = 0

    print("\n CHARGEMENT ET FUSION DES FICHIERS:")
    print("-" * 60)

    # Merge each file
    for file_path, description in files_to_merge:
        if os.path.exists(file_path):
            try:
                temp_graph = Graph()
                temp_graph.parse(file_path, format="turtle")

                # Add to final graph
                for triple in temp_graph:
                    final_graph.add(triple)

                triples_count = len(temp_graph)
                total_triples += triples_count
                print(f"✓ {description:30} : {triples_count:6} triples")

                # Stats spéciales pour les labels multilingues
                if "Multilingual" in description:
                    lang_stats = {}
                    for s, p, o in temp_graph.triples((None, RDFS.label, None)):
                        if hasattr(o, 'language') and o.language:
                            lang = o.language
                            lang_stats[lang] = lang_stats.get(lang, 0) + 1

                    if lang_stats:
                        print(f"  {" ":30}   Labels par langue: ", end="")
                        langs = []
                        for lang, count in sorted(lang_stats.items()):
                            langs.append(f"{lang}:{count}")
                        print(", ".join(langs))

            except Exception as e:
                print(f"✗ {description:30} : ERROR - {e}")
        else:
            print(f"✗ {description:30} : FILE MISSING ({file_path})")

    # Sauvegarder le graphe final
    output_file = "kg/final_knowledge_graph.ttl"
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    final_graph.serialize(output_file, format="turtle")

    # Statistiques détaillées
    print("\n" + "=" * 60)
    print("MERGE RESULTS")
    print("=" * 60)
    print(f"Final file          : {output_file}")
    print(f"Total triples       : {len(final_graph):,}")
    print(f"File size           : {os.path.getsize(output_file) / 1024:.1f} KB")

    # Vue d'ensemble des types d'entités
    print("\n ENTITY TYPES OVERVIEW:")
    entity_types = {}
    for s, p, o in final_graph.triples((None, RDF.type, None)):
        type_name = str(o).split("/")[-1]
        entity_types[type_name] = entity_types.get(type_name, 0) + 1

    for type_name, count in sorted(entity_types.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"  {type_name:20} : {count:5} entities")

    # Statistiques multilingues
    print("\n MULTILINGUAL STATISTICS:")
    lang_stats = {}
    person_count = 0
    for s, p, o in final_graph.triples((None, RDFS.label, None)):
        if hasattr(o, 'language') and o.language:
            lang = o.language
            lang_stats[lang] = lang_stats.get(lang, 0) + 1

    for lang, count in sorted(lang_stats.items(), key=lambda x: x[1], reverse=True):
        print(f"  {lang:5} labels : {count:6}")

    # Compter les personnages avec labels multilingues
    persons_with_multilingual = set()
    for s, p, o in final_graph.triples((None, RDFS.label, None)):
        if hasattr(o, 'language'):
            persons_with_multilingual.add(s)

    print(f"  Persons with multilingual labels : {len(persons_with_multilingual)}")

    # Alignements
    print(f"\n EXTERNAL ALIGNMENTS:")
    alignments = 0
    for s, p, o in final_graph.triples((None, None, None)):
        if "sameAs" in str(p) or "owl:sameAs" in str(p):
            alignments += 1
    print(f"  owl:sameAs alignments : {alignments}")

    print("\n MERGE COMPLETED SUCCESSFULLY!")
    return final_graph


if __name__ == "__main__":
    merge_all_knowledge_graphs()