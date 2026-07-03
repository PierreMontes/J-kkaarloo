"""
Outil météo de Jàkkaarloo — prévisions à 7 jours via l'API Open-Meteo.

# ==========================================================================
# CONCEPT DÉMONTRÉ : OUTIL D'AGENT (function tool) + source de données EXTERNE
# --------------------------------------------------------------------------
# `get_weather_forecast` est une fonction Python simple avec une docstring
# soignée. ADK l'expose automatiquement comme outil au « weather_agent » :
# le LLM lit la docstring pour décider quand l'appeler et avec quel argument.
#
# CHOIX TECHNIQUE : Open-Meteo est GRATUIT et SANS CLÉ API. C'est décisif ici
# — pas de secret à gérer, et l'outil reste utilisable par n'importe qui.
# ==========================================================================
"""

from typing import Any, Dict

import requests

# --- Confiance TLS via le magasin de certificats du système d'exploitation --
# POURQUOI : sur un réseau d'entreprise, un proxy d'inspection TLS ré-signe le
# trafic avec un certificat racine « maison ». Ce certificat est installé dans
# le magasin de Windows (les navigateurs marchent) mais PAS dans le bundle
# `certifi` de `requests` → erreur « CERTIFICATE_VERIFY_FAILED : self-signed
# certificate in certificate chain » sur des API comme Open-Meteo.
# `truststore` fait utiliser à Python le magasin de certificats de l'OS, ce qui
# règle le problème SANS JAMAIS désactiver la vérification (on reste sécurisé).
try:
    import truststore

    truststore.inject_into_ssl()
except Exception:  # noqa: BLE001 — dépendance optionnelle : on dégrade en douceur
    # Sans truststore, la vérification standard (certifi) s'applique. Hors
    # proxy d'entreprise, tout fonctionne ; derrière un proxy, l'outil
    # renverra un statut d'erreur explicite au lieu de planter.
    pass

# --- Géocodage local des grandes villes ------------------------------------
# On évite un appel réseau supplémentaire pour les villes les plus courantes,
# et on garantit des coordonnées correctes même si l'API de géocodage change.
_VILLES_SENEGAL = {
    "dakar": (14.6928, -17.4467),
    "thies": (14.7910, -16.9256),
    "thiès": (14.7910, -16.9256),
    "touba": (14.8500, -15.8833),
    "kaolack": (14.1500, -16.0667),
    "saint-louis": (16.0326, -16.4818),
    "saint louis": (16.0326, -16.4818),
    "ziguinchor": (12.5833, -16.2719),
    "diourbel": (14.6556, -16.2314),
    "louga": (15.6144, -16.2244),
    "tambacounda": (13.7708, -13.6673),
    "matam": (15.6559, -13.2554),
    "fatick": (14.3390, -16.4110),
    "kolda": (12.8833, -14.9500),
}

_TIMEOUT = 10  # secondes — évite de bloquer l'agent si le réseau est lent.


def _geocoder(ville: str) -> tuple[float, float] | None:
    """Retourne (latitude, longitude) pour une ville.
    1) Table locale (rapide, hors-ligne) ; 2) API de géocodage Open-Meteo.
    Retourne None si la ville reste introuvable."""
    cle = ville.strip().lower()
    if cle in _VILLES_SENEGAL:
        return _VILLES_SENEGAL[cle]

    # Repli : géocodage en ligne (toujours sans clé).
    try:
        rep = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": ville, "count": 1, "language": "fr", "format": "json"},
            timeout=_TIMEOUT,
        )
        rep.raise_for_status()
        resultats = rep.json().get("results")
        if resultats:
            r = resultats[0]
            return (r["latitude"], r["longitude"])
    except requests.RequestException:
        # On ne propage pas : l'appelant gérera le None proprement.
        return None
    return None


def get_weather_forecast(city: str) -> Dict[str, Any]:
    """Renvoie les prévisions météo à 7 jours pour une ville (Sénégal et au-delà).

    Utilise cet outil pour aider l'agriculteur à décider QUAND SEMER,
    s'il doit IRRIGUER, ou anticiper de fortes pluies.

    Args:
        city: Nom de la ville (ex. « Dakar », « Kaolack », « Saint-Louis »).

    Returns:
        Dictionnaire structuré :
          - statut : "ok", "ville_inconnue" ou "erreur_reseau"
          - ville : nom demandé
          - previsions : liste de 7 jours, chacun avec
                {date, pluie_mm, temp_min_c, temp_max_c}
          - jours_de_pluie : nombre de jours avec pluie prévue (>1 mm)
          - pluie_totale_mm : cumul de pluie sur 7 jours
          - resume : phrase de synthèse prête à lire
        Ne lève JAMAIS d'exception : en cas de souci réseau, renvoie un statut
        d'erreur explicite que l'agent pourra reformuler à l'agriculteur.
    """
    coords = _geocoder(city)
    if coords is None:
        return {
            "statut": "ville_inconnue",
            "ville": city,
            "message": "Ville introuvable. Vérifiez l'orthographe ou donnez une ville proche.",
        }

    latitude, longitude = coords
    try:
        rep = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": latitude,
                "longitude": longitude,
                "daily": "precipitation_sum,temperature_2m_max,temperature_2m_min",
                "forecast_days": 7,
                "timezone": "auto",
            },
            timeout=_TIMEOUT,
        )
        rep.raise_for_status()
        daily = rep.json()["daily"]
    except (requests.RequestException, KeyError, ValueError) as e:
        # Robustesse : réseau coupé, API modifiée, JSON inattendu…
        return {
            "statut": "erreur_reseau",
            "ville": city,
            "message": f"Prévisions momentanément indisponibles ({type(e).__name__}). Réessayez plus tard.",
        }

    # Mise en forme jour par jour + agrégats utiles à la décision agricole.
    previsions = []
    pluie_totale = 0.0
    jours_de_pluie = 0
    for date, pluie, tmax, tmin in zip(
        daily["time"],
        daily["precipitation_sum"],
        daily["temperature_2m_max"],
        daily["temperature_2m_min"],
    ):
        pluie = pluie or 0.0
        previsions.append(
            {
                "date": date,
                "pluie_mm": round(pluie, 1),
                "temp_min_c": tmin,
                "temp_max_c": tmax,
            }
        )
        pluie_totale += pluie
        if pluie > 1.0:  # seuil : une trace <1 mm n'est pas une « pluie utile »
            jours_de_pluie += 1

    resume = (
        f"Sur 7 jours à {city} : {jours_de_pluie} jour(s) de pluie prévu(s), "
        f"cumul d'environ {round(pluie_totale)} mm."
    )

    return {
        "statut": "ok",
        "ville": city,
        "previsions": previsions,
        "jours_de_pluie": jours_de_pluie,
        "pluie_totale_mm": round(pluie_totale, 1),
        "resume": resume,
    }
