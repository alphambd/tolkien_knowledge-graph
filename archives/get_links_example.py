print("DÉMONSTRATION DES ALIGNEMENTS")
print("=" * 50)

# Montre le concept même sans API
alignments = {
    "Gandalf": "https://en.wikipedia.org/wiki/Gandalf → http://dbpedia.org/resource/Gandalf",
    "Aragorn": "https://en.wikipedia.org/wiki/Aragorn → http://dbpedia.org/resource/Aragorn",
    "Elrond": "https://en.wikipedia.org/wiki/Elrond → http://dbpedia.org/resource/Elrond"
}

for char, links in alignments.items():
    print(f"{char}:")
    print(f"  {links}")
    print()

print("Ces alignements sont ajoutés au KG avec owl:sameAs")