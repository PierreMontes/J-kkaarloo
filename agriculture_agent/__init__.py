"""Paquet de l'agent Jàkkaarloo.

# CONCEPT : DÉCOUVERTE PAR ADK
# `adk web` / `adk run` cherchent une variable `root_agent` dans le paquet.
# On la réexporte ici pour que l'agent soit automatiquement détecté.
"""

from .agent import root_agent

__all__ = ["root_agent"]
