"""
Base de connaissances de diagnostic des cultures — Jàkkaarloo.

# ==========================================================================
# CONCEPT DÉMONTRÉ : OUTIL D'AGENT adossé à une BASE DE RÈGLES locale
# --------------------------------------------------------------------------
# `diagnose_crop_issue` applique un moteur de règles simple (mots-clés →
# diagnostic) avec un SCORING par correspondance, et renvoie les 3 pistes
# les plus probables. Aucune dépendance réseau : fiable et instantané.
#
# CHOIX DE CONCEPTION (sécurité & éthique) :
#   - On ne donne JAMAIS de dosage de produit phytosanitaire dangereux.
#   - On rappelle SYSTÉMATIQUEMENT de faire confirmer par un professionnel
#     (ANCAR / ISRA au Sénégal). Un diagnostic à distance reste indicatif.
# ==========================================================================
"""

import re
import unicodedata
from typing import Any, Dict, List

# Contacts institutionnels sénégalais pour confirmation d'un diagnostic.
_RAPPEL_PRO = (
    "Diagnostic indicatif : à faire confirmer par un professionnel avant "
    "tout traitement (ex. agent ANCAR de votre zone, ou ISRA). Emportez si "
    "possible une photo et un échantillon de la plante atteinte."
)

# --- Base de règles ---------------------------------------------------------
# Chaque règle associe des MOTS-CLÉS de symptômes à un diagnostic, un conseil
# (préventif/cultural, sans dosage chimique) et un niveau de gravité.
# « cultures » limite la règle à certaines cultures (None = toutes).
# « signes_visuels » décrit ce qu'on VOIT sur une photo : ce champ sert au
# diagnostic par image (l'outil `lister_problemes_connus` l'expose au modèle
# pour qu'il aligne son observation visuelle sur le vocabulaire de la base).
_REGLES: List[Dict[str, Any]] = [
    {
        "id": "chenille_legionnaire",
        "mots_cles": ["chenille", "ver", "vers", "trou", "trous", "feuilles mangees",
                      "feuilles trouees", "larve", "epis mange"],
        "cultures": ["mais", "mil", "sorgho"],
        "diagnostic": "Attaque de chenilles (probable chenille légionnaire d'automne).",
        "signes_visuels": "Trous irréguliers et déchiquetés dans les feuilles ; "
                          "amas de déjections (petites crottes) dans les cornets ; "
                          "chenille rayée parfois visible au cœur du plant.",
        "conseil": "Inspecter les cornets le matin, écraser manuellement les jeunes "
                   "chenilles, favoriser les prédateurs naturels. Si l'attaque est "
                   "forte, consulter l'ANCAR pour un traitement homologué et dosé.",
        "gravite": "élevée",
    },
    {
        "id": "pucerons",
        "mots_cles": ["puceron", "pucerons", "petites betes", "collant", "miellat",
                      "feuilles recroquevillees", "fourmis"],
        "cultures": None,
        "diagnostic": "Colonies de pucerons (insectes piqueurs-suceurs).",
        "signes_visuels": "Amas de petits insectes verts ou noirs sous les feuilles "
                          "et sur les jeunes pousses ; feuilles déformées et "
                          "collantes (miellat) ; fourmis qui montent sur la plante.",
        "conseil": "Doucher les feuilles à l'eau, préserver les coccinelles, éviter "
                   "l'excès d'azote. Solution de savon noir possible en prévention.",
        "gravite": "moyenne",
    },
    {
        "id": "mouche_blanche",
        "mots_cles": ["mouche blanche", "mouches blanches", "feuilles enroulees",
                      "nuage blanc", "feuilles jaunes enroulees"],
        "cultures": ["tomate", "niebe", "oignon"],
        "diagnostic": "Mouches blanches (vectrices possibles de virus, ex. TYLCV).",
        "signes_visuels": "Petits insectes blancs qui s'envolent en nuage quand on "
                          "secoue la plante ; feuilles jaunies et enroulées vers le "
                          "haut ; plants rabougris.",
        "conseil": "Poser des pièges jaunes englués, arracher et détruire les plants "
                   "très atteints, éviter les cultures sensibles en continu.",
        "gravite": "élevée",
    },
    {
        "id": "mildiou",
        "mots_cles": ["tache", "taches", "moisissure", "duvet", "poudre blanche",
                      "feutrage", "taches brunes", "pourriture feuille"],
        "cultures": ["tomate", "oignon"],
        "diagnostic": "Maladie fongique de type mildiou/oïdium (champignon).",
        "signes_visuels": "Taches brunes ou huileuses sur feuilles et tiges ; duvet "
                          "blanc-gris au revers des feuilles par temps humide ; "
                          "parfois poudre blanche sur le dessus.",
        "conseil": "Aérer la culture, éviter d'arroser le feuillage le soir, retirer "
                   "les feuilles atteintes. Traitement préventif à valider avec l'ANCAR.",
        "gravite": "moyenne",
    },
    {
        "id": "rouille",
        "mots_cles": ["rouille", "taches orange", "pustules", "poudre orange",
                      "taches rouille"],
        "cultures": ["arachide", "mil", "mais"],
        "diagnostic": "Rouille (champignon) — pustules orangées sur les feuilles.",
        "signes_visuels": "Petites pustules poudreuses orange à brun-rouille, "
                          "surtout au revers des feuilles ; feuilles qui jaunissent "
                          "puis se dessèchent.",
        "conseil": "Choisir des variétés tolérantes, espacer les plants pour aérer, "
                   "détruire les résidus de culture infectés après récolte.",
        "gravite": "moyenne",
    },
    {
        "id": "striga",
        "mots_cles": ["striga", "petites fleurs violettes", "herbe parasite",
                      "plante parasite", "fleurs roses au pied"],
        "cultures": ["mil", "mais", "sorgho", "riz local"],
        "diagnostic": "Striga (plante parasite des céréales, fleurs violacées).",
        "signes_visuels": "Petite plante à fleurs violacées/roses poussant AU PIED "
                          "des céréales ; culture hôte rabougrie et jaunâtre autour "
                          "des touffes de striga.",
        "conseil": "Arracher le striga AVANT floraison, pratiquer la rotation avec "
                   "des légumineuses (niébé), enrichir le sol en matière organique.",
        "gravite": "élevée",
    },
    {
        "id": "criquets",
        "mots_cles": ["criquet", "criquets", "sauterelle", "sauterelles", "essaim",
                      "tout mange", "champ devore", "invasion"],
        "cultures": None,
        "diagnostic": "Attaque de criquets/sauterelles (ravageurs mobiles).",
        "signes_visuels": "Nombreux insectes sauteurs ou volants sur la parcelle ; "
                          "feuillage rasé très rapidement, parfois réduit aux "
                          "nervures ; essaim parfois visible.",
        "conseil": "Signaler IMMÉDIATEMENT à la DPV / ANCAR : la lutte anti-acridienne "
                   "est organisée à l'échelle régionale. Ne pas traiter seul.",
        "gravite": "élevée",
    },
    {
        "id": "stress_hydrique",
        "mots_cles": ["fletri", "fletrissement", "fane", "seche", "manque d'eau",
                      "plante molle", "feuilles tombantes"],
        "cultures": None,
        "diagnostic": "Stress hydrique probable (manque d'eau / forte chaleur).",
        "signes_visuels": "Feuilles molles, tombantes ou enroulées aux heures "
                          "chaudes ; sol sec et craquelé ; la plante se redresse "
                          "souvent le soir ou après arrosage.",
        "conseil": "Arroser tôt le matin ou en soirée, pailler le sol pour garder "
                   "l'humidité. Vérifier la météo avant de semer (voir agent météo).",
        "gravite": "moyenne",
    },
    {
        "id": "carence_azote",
        "mots_cles": ["feuilles jaunes", "jaunissement", "pale", "croissance lente",
                      "plante chetive", "vieilles feuilles jaunes"],
        "cultures": None,
        "diagnostic": "Carence en azote probable (jaunissement des feuilles âgées).",
        "signes_visuels": "Jaunissement qui commence par les VIEILLES feuilles (du "
                          "bas) et remonte ; plante globalement pâle et peu "
                          "vigoureuse, entre-nœuds courts.",
        "conseil": "Apporter du compost/fumier bien décomposé, associer une "
                   "légumineuse fixatrice d'azote (niébé) en rotation.",
        "gravite": "faible",
    },
    {
        "id": "pourriture_racines",
        "mots_cles": ["racines pourries", "galles", "racines abimees", "pourriture",
                      "plante qui deperit", "nematode"],
        "cultures": None,
        "diagnostic": "Problème racinaire (pourriture ou nématodes).",
        "signes_visuels": "Plante qui dépérit sans cause visible sur le feuillage ; "
                          "à l'arrachage, racines brunes et molles ou renflements "
                          "(galles) sur les racines.",
        "conseil": "Améliorer le drainage, éviter l'excès d'eau, pratiquer la "
                   "rotation des cultures. Faire analyser un plant par l'ISRA si possible.",
        "gravite": "moyenne",
    },
]


def _normaliser(texte: str) -> str:
    """Minuscules + suppression des accents pour comparer les mots-clés
    quelle que soit la façon dont l'agriculteur écrit ses symptômes."""
    texte = texte.strip().lower()
    texte = unicodedata.normalize("NFKD", texte)
    return "".join(c for c in texte if not unicodedata.combining(c))


def _tokeniser(texte: str) -> List[str]:
    """Découpe un texte en mots (normalisés, sans accents), en ignorant les
    mots trop courts (articles/particules « de », « la », « d' »…) qui
    n'apportent pas de sens au diagnostic."""
    mots = re.split(r"[^a-z0-9]+", _normaliser(texte))
    return [m for m in mots if len(m) >= 3]


def _mots_correspondent(a: str, b: str) -> bool:
    """Deux mots « correspondent » s'ils sont identiques OU s'ils partagent
    une racine commune d'au moins 4 lettres.

    POURQUOI : les agriculteurs conjuguent/accordent librement
    (« jaunes » ≈ « jaunissent », « taches » ≈ « tache », « fletri » ≈
    « fletrissement »). Comparer la racine évite de rater ces variantes,
    sans recourir à un lemmatiseur lourd."""
    if a == b:
        return True
    n = min(len(a), len(b))
    if n < 4:  # mots courts : on exige l'égalité stricte (évite les faux positifs)
        return False
    prefixe = 0
    while prefixe < n and a[prefixe] == b[prefixe]:
        prefixe += 1
    return prefixe >= 4


def _cle_presente(mot_cle: str, mots_symptomes: List[str]) -> bool:
    """Un mot-clé (éventuellement composé de plusieurs mots) est présent si
    CHACUN de ses mots trouve une correspondance dans les symptômes."""
    mots_du_cle = _tokeniser(mot_cle)
    if not mots_du_cle:
        return False
    return all(
        any(_mots_correspondent(mc, ms) for ms in mots_symptomes)
        for mc in mots_du_cle
    )


def diagnose_crop_issue(culture: str, symptomes: str) -> Dict[str, Any]:
    """Propose un diagnostic à partir d'une culture et de symptômes décrits.

    Utilise cet outil quand l'agriculteur décrit un PROBLÈME sur sa culture
    (feuilles abîmées, insectes, taches, flétrissement, etc.).

    Args:
        culture: Nom de la culture concernée (ex. « maïs », « tomate »).
        symptomes: Description libre des symptômes observés
            (ex. « des trous dans les feuilles et des petites chenilles »).

    Returns:
        Dictionnaire structuré :
          - statut : "ok" ou "aucune_piste"
          - culture : culture analysée
          - pistes : liste (max 3) triée par pertinence, chacune avec
                {diagnostic, conseil, gravite, score}
          - rappel : rappel de confirmation par un professionnel (ANCAR/ISRA)
        Ne renvoie JAMAIS de dosage de produit dangereux (choix de sécurité).
    """
    culture_norm = _normaliser(culture)
    mots_symptomes = _tokeniser(symptomes)

    resultats: List[Dict[str, Any]] = []
    for regle in _REGLES:
        # Filtre par culture : on ignore les règles qui ne concernent pas
        # la culture citée (sauf règles universelles, cultures=None).
        if regle["cultures"] is not None:
            if not any(_normaliser(c) == culture_norm for c in regle["cultures"]):
                continue

        # Scoring : nombre de mots-clés de la règle retrouvés dans les symptômes
        # (correspondance tolérante par racine, voir _cle_presente).
        score = sum(
            1 for mot in regle["mots_cles"] if _cle_presente(mot, mots_symptomes)
        )
        if score > 0:
            resultats.append(
                {
                    "diagnostic": regle["diagnostic"],
                    "conseil": regle["conseil"],
                    "gravite": regle["gravite"],
                    "score": score,
                }
            )

    # Tri par score décroissant, on garde les 3 meilleures pistes.
    resultats.sort(key=lambda r: r["score"], reverse=True)
    top = resultats[:3]

    if not top:
        return {
            "statut": "aucune_piste",
            "culture": culture,
            "pistes": [],
            "rappel": _RAPPEL_PRO,
            "message": "Aucune piste claire avec ces symptômes. Décrivez plus "
                       "précisément (couleur, insectes visibles, partie atteinte) "
                       "ou consultez directement un agent ANCAR.",
        }

    return {
        "statut": "ok",
        "culture": culture,
        "pistes": top,
        "rappel": _RAPPEL_PRO,
    }


def lister_problemes_connus(culture: str = "") -> Dict[str, Any]:
    """Renvoie le CATALOGUE des problèmes que la base sait reconnaître, avec
    pour chacun ses SIGNES VISUELS caractéristiques.

    # CONCEPT DÉMONTRÉ : ANCRAGE du diagnostic par PHOTO (multimodal).
    # Cet outil est pensé pour le diagnostic à partir d'une image : après avoir
    # observé la photo, l'agent consulte ce catalogue pour rapprocher ce qu'il
    # VOIT des problèmes réellement connus de la base, puis appelle
    # `diagnose_crop_issue` avec le bon vocabulaire. Objectif : éviter que le
    # modèle « invente » un diagnostic non fondé à partir d'une image.

    Args:
        culture: (optionnel) filtre par culture (ex. « maïs »). Laissé vide,
            renvoie tous les problèmes connus.

    Returns:
        Dictionnaire structuré :
          - statut : "ok"
          - culture : filtre appliqué ("toutes" si vide)
          - problemes : liste de
                {diagnostic, signes_visuels, gravite, cultures,
                 mots_cles_exemples}
            où `mots_cles_exemples` aide à formuler l'argument `symptomes`
            de `diagnose_crop_issue`.
    """
    culture_norm = _normaliser(culture) if culture else ""

    problemes: List[Dict[str, Any]] = []
    for regle in _REGLES:
        # Filtre optionnel par culture (les règles universelles passent toujours).
        if culture_norm and regle["cultures"] is not None:
            if not any(_normaliser(c) == culture_norm for c in regle["cultures"]):
                continue
        problemes.append(
            {
                "diagnostic": regle["diagnostic"],
                "signes_visuels": regle["signes_visuels"],
                "gravite": regle["gravite"],
                "cultures": regle["cultures"] if regle["cultures"] else "toutes",
                # On expose quelques mots-clés pour guider l'appel suivant.
                "mots_cles_exemples": regle["mots_cles"][:4],
            }
        )

    return {
        "statut": "ok",
        "culture": culture if culture else "toutes",
        "problemes": problemes,
    }
