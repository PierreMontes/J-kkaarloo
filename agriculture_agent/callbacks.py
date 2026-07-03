"""
Garde-fou de sécurité de Jàkkaarloo (before_model_callback).

# ==========================================================================
# CONCEPT DÉMONTRÉ : SÉCURITÉ DES AGENTS (guardrail « before_model_callback »)
# --------------------------------------------------------------------------
# ADK permet d'intercepter CHAQUE requête AVANT qu'elle n'atteigne le LLM.
# On branche ici `safety_guardrail` sur l'agent racine (voir agent.py) :
#
#   - retourne None            -> la requête passe normalement au modèle ;
#   - retourne un LlmResponse  -> COURT-CIRCUITE le modèle et renvoie
#                                 directement notre réponse sûre.
#
# Deux protections sont implémentées :
#   (a) DANGER PHYTOSANITAIRE : on refuse de donner des dosages de produits
#       chimiques dangereux et on redirige vers un professionnel.
#   (b) INJECTION DE PROMPT : on neutralise les tentatives de détournement
#       des instructions de l'agent.
#
# Ces filtres agissent en DÉFENSE EN PROFONDEUR, en complément des consignes
# données dans les prompts (qui, seules, restent contournables).
# ==========================================================================
"""

import re
import unicodedata
from typing import Optional

from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmRequest, LlmResponse
from google.genai import types


def _normaliser(texte: str) -> str:
    """Minuscules + suppression des accents : la détection ne doit pas
    dépendre de la casse ni des accents (« Dosage » = « dosage »)."""
    texte = texte.lower()
    texte = unicodedata.normalize("NFKD", texte)
    return "".join(c for c in texte if not unicodedata.combining(c))


# --- (a) Détection de demandes de dosages dangereux ------------------------
# On bloque quand la requête combine une INTENTION de quantité/dosage avec un
# PRODUIT chimique — ou dès qu'un produit interdit/très toxique est cité.

_INTENTIONS_DOSAGE = [
    "dose", "dosage", "combien de", "quelle quantite", "quantite de",
    "combien mettre", "combien mettre de", "ml de", "litres de", "grammes de",
    "cuillere", "concentration", "melanger", "melange", "diluer", "dilution",
    "par litre", "par hectare",
]

_PRODUITS_CHIMIQUES = [
    "pesticide", "insecticide", "herbicide", "fongicide", "acaricide",
    "produit chimique", "produit phyto", "phytosanitaire", "engrais chimique",
]

# Produits notoirement dangereux / interdits : on refuse tout conseil de dose,
# quelle que soit la formulation.
_PRODUITS_DANGEREUX = [
    "paraquat", "gramoxone", "ddt", "endosulfan", "parathion", "aldicarbe",
    "lindane", "methomyl", "monocrotophos",
]

# NB : le garde-fou COURT-CIRCUITE le modèle, donc ces messages ne sont pas
# traduits par Gemini. Pour rester accessibles quelle que soit la langue de
# l'agriculteur, ils sont BILINGUES (français + wolof). Les lignes en wolof
# sont une traduction INDICATIVE, à faire valider par un locuteur natif.
_REPONSE_DANGER = (
    "Pour votre sécurité, je ne peux pas indiquer de dosage de produit "
    "chimique. Un mauvais dosage est dangereux pour vous, vos cultures et "
    "l'environnement.\n\n"
    "Adressez-vous à un professionnel qui prescrira le produit HOMOLOGUÉ "
    "et la dose adaptée à votre situation : l'agent **ANCAR** de votre zone, "
    "ou l'**ISRA**. En attendant, je peux vous aider à identifier le problème "
    "et vous proposer des mesures préventives sans produit chimique.\n\n"
    "(Wolof) Ngir sa wér-gu-yaram, duma la mën a wax doseb garab kimik. "
    "Gisal ab kilifa mbay (ANCAR walla ISRA). Man, mën naa la dimbali ngir "
    "xam li jot sa mbay te jox la yar yu saxal."
)


# --- (b) Détection de tentatives d'injection de prompt ---------------------
# Motifs classiques cherchant à faire ignorer les consignes de l'agent ou à
# exfiltrer ses instructions système.
_MOTIFS_INJECTION = [
    r"ignore[a-z ]*\b(les|tes|ces|toutes)?\b[a-z ]*instructions",
    r"ignore[a-z ]*(previous|above|prior)[a-z ]*instructions",
    r"oublie[a-z ]*(tes|les|ces)?[a-z ]*(instructions|consignes|regles)",
    r"n['e ]?(es|est)[a-z ]*plus[a-z ]*(un|une|l['e ]?)?assistant",
    r"tu n['e ]?es plus",
    r"fais semblant",
    r"pretends? (to be|d['e ]?etre)",
    r"(revele|montre|affiche|donne)[a-z ']*\b(ton|tes|le|ta)\b[a-z ']*(prompt|instructions|systeme|consignes)",
    r"system prompt",
    r"nouvelles? instructions",
    r"a partir de maintenant tu",
    r"desormais tu (dois|vas|es)",
    r"jailbreak",
    r"mode developpeur",
    r"developer mode",
]

_REPONSE_INJECTION = (
    "Je reste Jàkkaarloo, votre conseiller agricole. Je ne peux pas "
    "changer de rôle ni révéler mes instructions internes.\n\n"
    "Posez-moi plutôt une question sur vos cultures : diagnostic d'un "
    "problème, météo pour semer/irriguer, ou prix de vente sur les marchés.\n\n"
    "(Wolof) Man mooy Jàkkaarloo, sa ndimbalu mbay. Mënuma soppi sama "
    "liggéey. Laajal ma ci sa mbay : jàngat sa mbay, ngelaw li, walla njëg "
    "yi ci marse yi."
)


def _texte_utilisateur(llm_request: LlmRequest) -> str:
    """Extrait et concatène le texte des messages de rôle « user ».

    ADK range l'historique dans llm_request.contents (liste de Content).
    On ne regarde que le rôle « user » : ce sont les seules entrées non
    fiables (saisies par un tiers) qu'un garde-fou doit contrôler."""
    morceaux = []
    for content in (llm_request.contents or []):
        if getattr(content, "role", None) != "user":
            continue
        for part in (getattr(content, "parts", None) or []):
            texte = getattr(part, "text", None)
            if texte:
                morceaux.append(texte)
    return _normaliser(" ".join(morceaux))


def _reponse_sure(message: str) -> LlmResponse:
    """Fabrique une réponse de court-circuit (rôle « model ») qui remplace
    l'appel au LLM par notre message sûr."""
    return LlmResponse(
        content=types.Content(
            role="model",
            parts=[types.Part(text=message)],
        )
    )


def safety_guardrail(
    callback_context: CallbackContext,
    llm_request: LlmRequest,
) -> Optional[LlmResponse]:
    """Garde-fou exécuté AVANT chaque appel au modèle (before_model_callback).

    Retourne :
      - un LlmResponse sûr si la requête est dangereuse ou malveillante
        (elle est alors bloquée, le LLM n'est pas appelé) ;
      - None sinon (la requête suit son cours normal).
    """
    texte = _texte_utilisateur(llm_request)
    if not texte:
        return None  # rien à contrôler

    # (b) Injection de prompt — on traite en premier : c'est une attaque sur
    # le fonctionnement même de l'agent.
    for motif in _MOTIFS_INJECTION:
        if re.search(motif, texte):
            return _reponse_sure(_REPONSE_INJECTION)

    # (a) Dosage dangereux.
    # Cas 1 : un produit interdit/très toxique est cité -> refus direct.
    if any(prod in texte for prod in _PRODUITS_DANGEREUX):
        return _reponse_sure(_REPONSE_DANGER)

    # Cas 2 : intention de dosage ET produit chimique évoqués ensemble.
    intention = any(mot in texte for mot in _INTENTIONS_DOSAGE)
    produit = any(mot in texte for mot in _PRODUITS_CHIMIQUES)
    if intention and produit:
        return _reponse_sure(_REPONSE_DANGER)

    # Aucun problème détecté : on laisse passer au modèle.
    return None
