"""Outils locaux des agents Jàkkaarloo (météo + diagnostic).

On réexporte les fonctions-outils pour un import court et lisible dans
agent.py :  ``from .tools import get_weather_forecast, diagnose_crop_issue``
"""

from .diagnostic_kb import diagnose_crop_issue, lister_problemes_connus
from .weather_tool import get_weather_forecast

__all__ = [
    "get_weather_forecast",
    "diagnose_crop_issue",
    "lister_problemes_connus",
]
