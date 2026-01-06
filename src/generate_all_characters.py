import requests
import re
import os
import time
from urllib.parse import quote
from rdflib import Graph, URIRef, Literal, Namespace, RDF, RDFS

# ---------------------------
# Configuration
# ---------------------------
TOlkien = Namespace("http://example.org/tolkien/")
FUSEKI_ENDPOINT = "http://localhost:3030/tolkienKG"
API_URL = "https://tolkiengateway.net/w/api.php"


# ---------------------------
# Fonctions auxiliaires améliorées
# ---------------------------
def safe_uri_name(name):
    """
    Convertit un nom en une version sûre pour une URI.
    Gère les parenthèses, guillemets, et caractères spéciaux.
    """
    safe = name.strip()

    # Gestion spéciale pour les parenthèses contenant des descriptions
    # Ex: "Adrahil (Captain of the Left Wing)" -> "Adrahil"
    if " (" in safe and safe.endswith(")"):
        # Extraire le nom principal sans la description entre parenthèses
        safe = safe.split(" (")[0].strip()

    # Supprimer les guillemets
    safe = safe.replace('"', '').replace("'", "")

    # Liste des caractères à remplacer par des underscores
    chars_to_replace = [" ", ":", "(", ")", "[", "]", "{", "}",
                        "|", "\\", "/", "#", ",", ";", ".", "!"]

    for char in chars_to_replace:
        safe = safe.replace(char, "_")

    # Remplacer les séquences de multiples underscores par un seul
    safe = re.sub(r"_+", "_", safe)

    # Supprimer les underscores en début et fin
    safe = safe.strip("_")

    return safe


def extract_description_from_name(name):
    """
    Extrait la description entre parenthèses d'un nom.
    Ex: "Adrahil (Captain of the Left Wing)" -> "Captain of the Left Wing"
    """
    name = name.strip()
    if " (" in name and name.endswith(")"):
        description = name.split(" (")[1].rstrip(")").strip()
        return description
    return None


def parse_wiki_value(value, namespace):
    """
    Parse a wiki value.
    - If it contains one or more links [[X]] or [[X|Y]], return a list of URIRefs.
    - Otherwise, return a single Literal.
    """
    # Trouver tous les liens [[X]] ou [[X|Y]]
    links = re.findall(r"\[\[([^\|\]]+)(?:\|([^\]]+))?\]\]", value)
    if links:
        uris = []
        for link in links:
            entity_name = link[0].strip()  # la cible du lien
            safe_name = safe_uri_name(entity_name)
            uris.append(URIRef(namespace[safe_name]))
        return uris
    # Si pas de lien, retourner valeur brute comme Literal
    return [Literal(value.strip())]


def get_characters_from_category(category, limit=None):
    """
    Récupère les personnages d'une catégorie Wikipedia.
    """
    members = []
    cmcontinue = ""
    count = 0

    print(f"Récupération des personnages de la catégorie: {category}")

    while True:
        params = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": f"Category:{category}",
            "cmlimit": "max",  # Utiliser max (500) au lieu de 50
            "format": "json",
        }
        if cmcontinue:
            params["cmcontinue"] = cmcontinue

        try:
            r = requests.get(API_URL, params=params, timeout=15).json()
        except Exception as e:
            print(f"Erreur lors de la récupération: {e}")
            break

        if "query" in r:
            batch = r["query"]["categorymembers"]
            for m in batch:
                members.append(m["title"])
                count += 1
                if limit and count >= limit:
                    break

        if limit and count >= limit:
            break

        if "continue" in r:
            cmcontinue = r["continue"]["cmcontinue"]
            # Petite pause pour ne pas surcharger l'API
            time.sleep(0.5)
        else:
            break

    print(f"  {len(members)} personnages trouvés")
    return members


def get_infobox(title):
    """
    Récupère le contenu de l'infobox d'une page Wikipedia.
    Version robuste avec meilleure gestion d'erreurs.
    """
    params = {
        "action": "query",
        "prop": "revisions",
        "rvprop": "content",
        "titles": title,
        "format": "json"
    }

    try:
        # Faire la requête avec un timeout
        response = requests.get(API_URL, params=params, timeout=15)

        # Vérifier si la réponse est valide
        if response.status_code != 200:
            # Ne pas afficher d'erreur pour les pages normales qui n'existent pas
            return ""

        # Essayer de parser le JSON
        try:
            data = response.json()
        except ValueError:  # JSON invalide
            # Silencieux pour ne pas polluer la sortie
            return ""

        # Vérifier la structure attendue
        if "query" not in data:
            return ""

        pages = data.get("query", {}).get("pages", {})
        if not pages:
            return ""

        # Prendre la première page
        page = next(iter(pages.values()))

        # Vérifier si la page existe (pageid négatif ou 'missing' présent)
        if page.get("missing") is not None or page.get("pageid", 0) <= 0:
            # Page n'existe pas - c'est normal pour certains noms
            return ""

        # Récupérer le contenu
        revisions = page.get("revisions", [])
        if revisions:
            return revisions[0].get("*", "")

        return ""

    except requests.exceptions.Timeout:
        # Timeout silencieux
        return ""
    except requests.exceptions.ConnectionError:
        # Erreur de connexion silencieuse
        return ""
    except Exception:
        # Toute autre exception - retourner vide silencieusement
        return ""


def wait_for_fuseki(max_retries=10):
    """
    Attend que Fuseki soit disponible.
    """
    for i in range(max_retries):
        try:
            response = requests.get("http://localhost:3030/", timeout=2)
            if response.status_code == 200:
                print("✓ Fuseki est accessible")
                return True
        except:
            if i < max_retries - 1:
                print(f"  Tentative {i + 1}/{max_retries} - En attente de Fuseki...")
                time.sleep(2)
    return False


# ---------------------------
# Création du graphe RDF
# ---------------------------
g = Graph()

# Ajouter la déclaration du namespace
g.bind("tolkien", TOlkien)

print("=" * 50)
print("Début de la génération du graphe RDF - TOUS LES PERSONNAGES")
print("=" * 50)

# Récupérer TOUS les personnages (sans limite)
characters = get_characters_from_category("Third_Age_characters")

# Compteurs pour le suivi
total_characters = len(characters)
characters_with_infobox = 0
characters_without_infobox = 0
characters_with_errors = 0

print(f"\nTraitement de {total_characters} personnages...")
print("(Les personnages sans infobox seront ignorés silencieusement)")
print("")

start_time = time.time()

for index, name in enumerate(characters, 1):
    # Afficher la progression tous les 20 personnages
    if index % 20 == 0:
        elapsed = time.time() - start_time
        print(
            f"[Progression: {index}/{total_characters}] - {characters_with_infobox} infoboxes parsées - Temps: {elapsed:.1f}s")

    # Extraire la description si présente
    description = extract_description_from_name(name)

    # Créer un nom sûr pour l'URI
    safe_name = safe_uri_name(name)
    character_uri = URIRef(TOlkien[safe_name])

    # Ajouter les métadonnées de base
    g.add((character_uri, RDF.type, TOlkien.Character))
    g.add((character_uri, RDF.type, RDFS.Resource))
    g.add((character_uri, TOlkien.originalName, Literal(name)))

    # Ajouter la description si elle existe
    if description:
        g.add((character_uri, TOlkien.descriptionNote, Literal(description)))

    # Récupérer et parser l'infobox
    try:
        infobox_text = get_infobox(name)
        if not infobox_text:
            characters_without_infobox += 1
            continue  # Passer au suivant silencieusement

        characters_with_infobox += 1
        fields_parsed = 0

        for line in infobox_text.split("\n"):
            line = line.strip()
            if line.startswith("|"):
                parts = line[1:].split("=", 1)
                if len(parts) == 2:
                    field, value = parts
                    field = field.strip()
                    value = value.strip()

                    if not field or not value:
                        continue

                    # Nettoyer le nom du champ
                    safe_field = safe_uri_name(field)

                    try:
                        objects = parse_wiki_value(value, TOlkien)
                        for obj in objects:
                            g.add((character_uri, TOlkien[safe_field], obj))
                        fields_parsed += 1
                    except Exception:
                        # Erreur mineure sur un champ, on continue
                        pass

        # Afficher le succès pour ce personnage
        print(f"  [{index}] {name}: {fields_parsed} champs parsés")

    except Exception as e:
        characters_with_errors += 1
        # Erreur majeure sur ce personnage, on continue avec les autres
        print(f"  [{index}] ✗ Erreur sur {name}: {str(e)[:50]}...")

    # Petite pause pour ne pas surcharger l'API
    time.sleep(0.1)

# ---------------------------
# Sérialisation et envoi
# ---------------------------
elapsed_total = time.time() - start_time

print("\n" + "=" * 50)
print("SÉRIALISATION DU GRAPHE RDF")
print("=" * 50)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_FILE = os.path.join(PROJECT_ROOT, "data", "all_characters.ttl")

# Créer le dossier data s'il n'existe pas
os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

# Sérialiser le graphe RDF
try:
    g.serialize(OUTPUT_FILE, format="turtle")
    print(f"✓ RDF généré: {OUTPUT_FILE}")
    print(f"✓ Taille du fichier: {os.path.getsize(OUTPUT_FILE) / 1024:.1f} KB")
    print(f"✓ Total de triplets: {len(g)}")

    # Compter les personnages uniques dans le graphe
    characters_in_graph = len(set(s for s, p, o in g if (s, RDF.type, TOlkien.Character) in g))
    print(f"✓ Personnages dans le graphe: {characters_in_graph}")

except Exception as e:
    print(f"✗ Erreur lors de la sérialisation: {e}")
    # Sauvegarde de secours
    backup_file = OUTPUT_FILE.replace(".ttl", ".nt")
    g.serialize(backup_file, format="nt")
    print(f"✓ Sauvegarde NTriples: {backup_file}")

print("\n" + "=" * 50)
print("RÉSUMÉ FINAL")
print("=" * 50)
print(f"Personnages total dans la catégorie: {total_characters}")
print(f"Personnages avec infobox traités: {characters_with_infobox}")
print(f"Personnages sans infobox: {characters_without_infobox}")
print(f"Personnages avec erreurs: {characters_with_errors}")
print(f"Temps total d'exécution: {elapsed_total:.1f} secondes")
print(f"Triplets RDF générés: {len(g)}")

print("\n" + "=" * 50)
print("ENVOI À FUSEKI")
print("=" * 50)

# Vérifier et envoyer à Fuseki
if os.path.exists(OUTPUT_FILE):
    if wait_for_fuseki():
        try:
            with open(OUTPUT_FILE, "rb") as f:
                r = requests.post(
                    FUSEKI_ENDPOINT,
                    data=f,
                    headers={"Content-Type": "text/turtle"},
                    timeout=60
                )
                if r.status_code in [200, 201, 204]:
                    print("✅ RDF ajouté avec succès à Fuseki!")
                    print(f"   {len(g)} triplets - {characters_with_infobox} personnages")
                else:
                    print(f"✗ Erreur Fuseki: {r.status_code}")
                    if r.text:
                        print(f"  Message: {r.text[:200]}...")
        except requests.exceptions.ConnectionError:
            print("⚠  Fuseki n'est plus accessible")
        except Exception as e:
            print(f"✗ Erreur lors de l'envoi: {e}")
    else:
        print("⚠  Fuseki n'est pas accessible")
        print("   Pour démarrer Fuseki:")
        print("   cd ~/Téléchargements/Semantic_WEB/Fusiki/apache-jena-fuseki-4.9.0")
        print("   ./fuseki-server --update --mem /tolkienKG")
else:
    print("✗ Fichier RDF non trouvé")

print("\n" + "=" * 50)
print("TERMINÉ!")
print("=" * 50)