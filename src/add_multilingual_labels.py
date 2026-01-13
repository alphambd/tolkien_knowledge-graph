"""
add_multilingual_labels_final_fixed.py
Version avec tags de langue corrects
"""
from rdflib import Graph, Literal, Namespace, RDFS, URIRef, RDF

def add_multilingual_final():
    print("=" * 60)
    print("AJOUT MULTILINGUE AVEC TAGS DE LANGUE CORRECTS")
    print("=" * 60)

    # Charger le graphe COMPLET
    g = Graph()
    g.parse("kg/final_knowledge_graph.ttl", format="turtle")

    # Namespace
    SCHEMA1 = Namespace("http://schema.org/")

    # Trouver les personnages
    persons = []
    for s, p, o in g.triples((None, RDF.type, SCHEMA1.Person)):
        for s2, p2, name in g.triples((s, SCHEMA1.name, None)):
            if str(name).strip():
                persons.append((str(s), str(name).strip()))
                break

    print(f"✅ {len(persons)} personnages trouvés")

    # Traductions améliorées
    translations = {
        # Personnages avec traductions réelles
        "Frodo Baggins": {
            "fr": "Frodon Sacquet",
            "es": "Frodo Bolsón",
            "de": "Frodo Beutlin",
            "it": "Frodo Baggins",
            "en": "Frodo Baggins"
        },
        "Samwise Gamgee": {
            "fr": "Samsagace Gamegie",
            "es": "Samsagaz Gamyi",
            "de": "Samweis Gamdschie",
            "it": "Samvise Gamgee",
            "en": "Samwise Gamgee"
        },
        "Meriadoc Brandybuck": {
            "fr": "Meriadoc Brandebouc",
            "es": "Meriadoc Brandigamo",
            "de": "Meriadoc Brandybuter",
            "it": "Meriadoc Brandibuck",
            "en": "Meriadoc Brandybuck"
        },
        "Peregrin Took": {
            "fr": "Peregrin Touque",
            "es": "Peregrin Tuk",
            "de": "Peregrin Tuk",
            "it": "Peregrino Tuc",
            "en": "Peregrin Took"
        },
        # Autres personnages (gardent leur nom)
        "Gandalf": ["en", "fr", "es", "de", "it"],
        "Aragorn": ["en", "fr", "es", "de", "it"],
        "Elrond": ["en", "fr", "es", "de", "it"],
        "Sauron": ["en", "fr", "es", "de", "it"],
        "Legolas": ["en", "fr", "es", "de", "it"],
        "Gimli": ["en", "fr", "es", "de", "it"],
        "Galadriel": ["en", "fr", "es", "de", "it"],
        "Boromir": ["en", "fr", "es", "de", "it"],
        "Saruman": ["en", "fr", "es", "de", "it"],
        "Théoden": ["en", "fr", "es", "de", "it"],
        "Éowyn": ["en", "fr", "es", "de", "it"],
        "Faramir": ["en", "fr", "es", "de", "it"],
        "Gollum": ["en", "fr", "es", "de", "it"],
        "Treebeard": ["en", "fr", "es", "de", "it"],
        "Tom Bombadil": ["en", "fr", "es", "de", "it"],
    }

    # Ajouter labels
    added = 0

    for uri, name in persons:
        uri_ref = URIRef(uri)

        # Personnages avec traductions spéciales
        if name in translations and isinstance(translations[name], dict):
            for lang, label in translations[name].items():
                g.add((uri_ref, RDFS.label, Literal(label, lang=lang)))
                added += 1

        # Personnages avec mêmes noms dans toutes langues
        elif name in translations:
            for lang in translations[name]:
                g.add((uri_ref, RDFS.label, Literal(name, lang=lang)))
                added += 1

        # Tous les autres: anglais + français
        else:
            g.add((uri_ref, RDFS.label, Literal(name, lang="en")))
            g.add((uri_ref, RDFS.label, Literal(name, lang="fr")))
            added += 2

    # Crée un nouveau graphe avec seulement les labels
    labels_only = Graph()
    for s, p, o in g.triples((None, RDFS.label, None)):
        labels_only.add((s, p, o))

    output = "data/multilingual_labels_only.ttl"
    labels_only.serialize(output, format="turtle")


    # Vérification
    print(f"\n📊 STATISTIQUES:")
    print(f"Personnages: {len(persons)}")
    print(f"Labels ajoutés: {added}")

    # Compter les langues
    print(f"\n🌍 RÉPARTITION PAR LANGUE:")
    lang_count = {}
    for s, p, o in g.triples((None, RDFS.label, None)):
        if hasattr(o, 'language') and o.language:
            lang = o.language
            lang_count[lang] = lang_count.get(lang, 0) + 1

    for lang, count in sorted(lang_count.items()):
        print(f"  {lang}: {count} labels")

    # Exemples
    print(f"\n EXEMPLES MULTILINGUES:")
    test_names = ["Frodo Baggins", "Gandalf", "Elrond", "Samwise Gamgee"]
    for name in test_names:
        for uri, pname in persons:
            if pname == name:
                print(f"\n{name}:")
                labels = list(g.objects(URIRef(uri), RDFS.label))
                for label in labels:
                    if hasattr(label, 'language'):
                        print(f"  {label.language}: {label}")
                break

if __name__ == "__main__":
    add_multilingual_final()