"""
Assemblage des agents de Jàkkaarloo.

# ==========================================================================
# CONCEPT DÉMONTRÉ : SYSTÈME MULTI-AGENTS (Google ADK)
# --------------------------------------------------------------------------
# On définit UN agent racine (orchestrateur) et TROIS sous-agents spécialisés.
# La délégation est pilotée par le LLM : l'orchestrateur lit la `description`
# de chaque sous-agent et route la question vers le bon spécialiste.
#
# POURQUOI plusieurs agents plutôt qu'un seul gros prompt ?
#   - Fiabilité : chaque agent a un périmètre étroit et des outils dédiés.
#   - Modularité : on peut faire évoluer un domaine sans casser les autres.
#   - Sources hétérogènes : base locale, API météo, serveur MCP distant.
#
# Ce fichier montre aussi, réunis :
#   - un OUTIL local (diagnostic), un OUTIL réseau (météo),
#   - des OUTILS distants via un SERVEUR MCP (marché),
#   - un GARDE-FOU de sécurité (before_model_callback),
#   - la configuration par VARIABLES D'ENVIRONNEMENT (aucun secret en dur).
# ==========================================================================
"""

import os

from dotenv import load_dotenv
from google.adk.agents import LlmAgent

# Import robuste du toolset MCP : le nom actuel est « McpToolset » ; certaines
# versions n'exposent que l'alias historique « MCPToolset ». On gère les deux.
try:
    from google.adk.tools.mcp_tool import (
        McpToolset,
        StreamableHTTPConnectionParams,
    )
except ImportError:  # pragma: no cover — repli défensif
    from google.adk.tools.mcp_tool import (
        MCPToolset as McpToolset,
        StreamableHTTPConnectionParams,
    )

from .callbacks import safety_guardrail
from .prompts import (
    DIAGNOSTIC_DESCRIPTION,
    DIAGNOSTIC_INSTRUCTION,
    MARKET_DESCRIPTION,
    MARKET_INSTRUCTION,
    ROOT_DESCRIPTION,
    ROOT_INSTRUCTION,
    WEATHER_DESCRIPTION,
    WEATHER_INSTRUCTION,
)
from .tools import (
    diagnose_crop_issue,
    get_weather_forecast,
    lister_problemes_connus,
)

# --- Configuration par environnement ---------------------------------------
# load_dotenv lit le fichier .env s'il existe (jamais versionné). Aucune clé
# n'est écrite ici : tout est fourni par l'environnement.
load_dotenv()

# Modèle utilisé par tous les agents. gemini-3.5-flash est multimodal (texte +
# image) : il gère le diagnostic par PHOTO et reste rapide et économique.
# Surchargeable par l'environnement, mais la valeur par défaut suffit.
MODEL = os.getenv("JAKKAARLOO_MODEL", "gemini-3.5-flash")

# URL du serveur MCP « marché » (transport streamable-http).
MCP_MARKET_URL = os.getenv("MCP_MARKET_URL", "http://localhost:8080/mcp")


# --- Sous-agent 1 : diagnostic (texte ET photo) ----------------------------
# Outils LOCAUX : ADK expose automatiquement ces fonctions Python (il lit leur
# signature et leur docstring).
# CONCEPT DÉMONTRÉ : DIAGNOSTIC MULTIMODAL. Le modèle Gemini est nativement
# multimodal : dans `adk web`, une PHOTO jointe par l'agriculteur lui parvient
# directement (les images ne transitent pas par les outils). `lister_problemes_
# connus` sert alors à ANCRER l'observation visuelle dans la base de règles
# avant l'appel à `diagnose_crop_issue` (voir DIAGNOSTIC_INSTRUCTION).
diagnostic_agent = LlmAgent(
    name="diagnostic_agent",
    model=MODEL,
    description=DIAGNOSTIC_DESCRIPTION,
    instruction=DIAGNOSTIC_INSTRUCTION,
    tools=[diagnose_crop_issue, lister_problemes_connus],
)

# --- Sous-agent 2 : météo ---------------------------------------------------
# Outil RÉSEAU (Open-Meteo, sans clé) encapsulé dans une fonction robuste.
weather_agent = LlmAgent(
    name="weather_agent",
    model=MODEL,
    description=WEATHER_DESCRIPTION,
    instruction=WEATHER_INSTRUCTION,
    tools=[get_weather_forecast],
)

# --- Sous-agent 3 : marché (outils distants via SERVEUR MCP) ---------------
# CONCEPT DÉMONTRÉ : connexion à un serveur MCP.
# `tool_filter` restreint explicitement les outils exposés à l'agent
# (principe de moindre privilège = SÉCURITÉ) : même si le serveur offrait
# d'autres outils, l'agent ne verrait que ces deux-là.
market_toolset = McpToolset(
    connection_params=StreamableHTTPConnectionParams(url=MCP_MARKET_URL),
    tool_filter=["get_market_prices", "get_crop_calendar"],
)

market_agent = LlmAgent(
    name="market_agent",
    model=MODEL,
    description=MARKET_DESCRIPTION,
    instruction=MARKET_INSTRUCTION,
    tools=[market_toolset],
)

# --- Agent racine : l'orchestrateur ----------------------------------------
# CONCEPT DÉMONTRÉ : orchestration multi-agents + garde-fou de sécurité.
# `sub_agents` active la délégation LLM ; `before_model_callback` filtre
# chaque requête avant qu'elle n'atteigne le modèle.
root_agent = LlmAgent(
    name="jakkaarloo",
    model=MODEL,
    description=ROOT_DESCRIPTION,
    instruction=ROOT_INSTRUCTION,
    sub_agents=[diagnostic_agent, weather_agent, market_agent],
    before_model_callback=safety_guardrail,
)
