"""
Serveur MCP « marché agricole » de Jàkkaarloo.

# ==========================================================================
# CONCEPT DÉMONTRÉ : SERVEUR MCP (Model Context Protocol)
# --------------------------------------------------------------------------
# Ce module expose des données de marché comme des OUTILS distants via le
# protocole MCP, servis par FastMCP en transport « streamable-http ».
# L'agent « market_agent » (dans agriculture_agent/agent.py) s'y connecte via
# un McpToolset : il découvre et appelle ces outils SANS les avoir en local.
#
# POURQUOI un serveur séparé ?  Les prix et le calendrier cultural sont des
# données « métier » qui évoluent (source externe, mise à jour régulière).
# Les isoler derrière MCP permet de les faire évoluer, sécuriser et déployer
# indépendamment des agents — c'est tout l'intérêt du protocole.
# ==========================================================================

Lancement (dans un terminal dédié) :
    python mcp_server/market_server.py
Le serveur écoute alors sur http://0.0.0.0:8080/mcp
"""

import json
import unicodedata
from pathlib import Path
from typing import Any, Dict

from mcp.server.fastmcp import FastMCP

# --- Instance FastMCP -------------------------------------------------------
# host/port sont fixés ici pour que le client (McpToolset) sache où se
# connecter. 0.0.0.0 rend le serveur joignable aussi depuis un conteneur.
mcp = FastMCP("marche-agricole", host="0.0.0.0", port=8080)

# --- Chargement des données -------------------------------------------------
# On calcule le chemin RELATIF à ce fichier : le serveur fonctionne quel que
# soit le répertoire courant d'où on le lance.
_FICHIER_DONNEES = Path(__file__).parent / "data" / "market_prices.json"


def _charger_donnees() -> Dict[str, Any]:
    """Charge le JSON des prix. Recharge à chaque appel pour refléter une
    éventuelle mise à jour du fichier sans redémarrer le serveur."""
    with open(_FICHIER_DONNEES, "r", encoding="utf-8") as f:
        return json.load(f)


def _normaliser(texte: str) -> str:
    """Normalise un nom de culture pour une comparaison tolérante :
    minuscules, sans accents, sans espaces superflus.
    Ex. « Maïs », « MAIS », «  mais  » → « mais »."""
    texte = texte.strip().lower()
    # Décompose les accents (é -> e + ´) puis retire les diacritiques.
    texte = unicodedata.normalize("NFKD", texte)
    texte = "".join(c for c in texte if not unicodedata.combining(c))
    return texte


# Synonymes courants → clé canonique utilisée dans le JSON.
# Rend l'outil robuste au vocabulaire réel des agriculteurs.
_SYNONYMES = {
    "cacahuete": "arachide",
    "cacahuètes": "arachide",
    "haricot": "niebe",
    "niebe": "niebe",
    "cowpea": "niebe",
    "riz": "riz local",
    "paddy": "riz local",
    "ognon": "oignon",
    "mil souna": "mil",
}


def _resoudre_culture(culture: str, donnees: Dict[str, Any]) -> str | None:
    """Retrouve la clé exacte du JSON à partir d'une saisie libre.
    Retourne None si la culture est inconnue."""
    cible = _normaliser(culture)
    # 1) Table de synonymes.
    if cible in _SYNONYMES:
        cible = _normaliser(_SYNONYMES[cible])
    # 2) Correspondance sur les clés normalisées du JSON.
    for cle in donnees["cultures"]:
        if _normaliser(cle) == cible:
            return cle
    return None


def _cultures_disponibles(donnees: Dict[str, Any]) -> list[str]:
    """Liste lisible des cultures connues (pour les messages d'erreur)."""
    return [c["nom_affiche"] for c in donnees["cultures"].values()]


@mcp.tool()
def get_market_prices(culture: str) -> Dict[str, Any]:
    """Renvoie les prix de marché (FCFA/kg) d'une culture au Sénégal.

    Utilise cet outil quand l'agriculteur demande OÙ ou À QUEL PRIX vendre,
    ou veut comparer les marchés.

    Args:
        culture: Nom de la culture (ex. « arachide », « mil », « tomate »,
            « oignon », « niébé », « maïs », « riz local »).

    Returns:
        Dictionnaire structuré :
          - statut : "ok" ou "culture_inconnue"
          - culture : nom affiché
          - prix_par_marche : {marché: prix_FCFA_par_kg}
          - meilleur_marche / meilleur_prix : où vendre le plus cher
          - tendance_30j : "hausse" | "stable" | "baisse"
          - variation_30j_pct : variation en pourcentage sur 30 jours
          - date_maj / devise : métadonnées
        Si la culture est inconnue, renvoie la liste des cultures disponibles.
    """
    try:
        donnees = _charger_donnees()
    except Exception as e:  # noqa: BLE001 — on ne veut jamais planter le serveur
        return {"statut": "erreur", "message": f"Données indisponibles : {e}"}

    cle = _resoudre_culture(culture, donnees)
    if cle is None:
        # Validation d'entrée : on GUIDE l'utilisateur au lieu d'échouer.
        return {
            "statut": "culture_inconnue",
            "culture_demandee": culture,
            "cultures_disponibles": _cultures_disponibles(donnees),
            "message": "Culture non reconnue. Voici les cultures suivies.",
        }

    fiche = donnees["cultures"][cle]
    prix = fiche["prix_par_marche"]
    # Le marché le plus intéressant = celui qui paie le plus cher.
    meilleur_marche = max(prix, key=prix.get)

    return {
        "statut": "ok",
        "culture": fiche["nom_affiche"],
        "devise": donnees["meta"]["devise"],
        "prix_par_marche": prix,
        "meilleur_marche": meilleur_marche,
        "meilleur_prix": prix[meilleur_marche],
        "tendance_30j": fiche["tendance_30j"],
        "variation_30j_pct": fiche["variation_30j_pct"],
        "date_maj": donnees["meta"]["date_maj"],
        "avertissement": "Prix indicatifs de démonstration, à vérifier localement.",
    }


@mcp.tool()
def get_crop_calendar(culture: str) -> Dict[str, Any]:
    """Renvoie le calendrier cultural d'une culture : fenêtres de semis et de
    récolte, et durée du cycle.

    Utilise cet outil quand l'agriculteur demande QUAND SEMER ou QUAND RÉCOLTER
    une culture donnée.

    Args:
        culture: Nom de la culture (ex. « arachide », « niébé », « oignon »).

    Returns:
        Dictionnaire structuré :
          - statut : "ok" ou "culture_inconnue"
          - culture : nom affiché
          - fenetre_semis / fenetre_recolte : périodes recommandées
          - duree_cycle_jours : durée moyenne du cycle
          - note : conseil agronomique complémentaire
        Si la culture est inconnue, renvoie la liste des cultures disponibles.
    """
    try:
        donnees = _charger_donnees()
    except Exception as e:  # noqa: BLE001
        return {"statut": "erreur", "message": f"Données indisponibles : {e}"}

    cle = _resoudre_culture(culture, donnees)
    if cle is None:
        return {
            "statut": "culture_inconnue",
            "culture_demandee": culture,
            "cultures_disponibles": _cultures_disponibles(donnees),
            "message": "Culture non reconnue. Voici les cultures suivies.",
        }

    fiche = donnees["cultures"][cle]
    cal = fiche["calendrier"]
    return {
        "statut": "ok",
        "culture": fiche["nom_affiche"],
        "fenetre_semis": cal["semis"],
        "fenetre_recolte": cal["recolte"],
        "duree_cycle_jours": cal["duree_cycle_jours"],
        "note": cal["note"],
    }


if __name__ == "__main__":
    # CONCEPT DÉMONTRÉ : transport MCP « streamable-http ».
    # C'est ce transport que le client McpToolset attend (voir agent.py).
    mcp.run(transport="streamable-http")
