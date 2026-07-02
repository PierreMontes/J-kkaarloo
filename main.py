"""
Interface web de Jàkkaarloo — backend FastAPI (multi-utilisateurs).

# ==========================================================================
# CONCEPT DÉMONTRÉ : DÉPLOYABILITÉ / PRODUIT (interface utilisateur dédiée)
# --------------------------------------------------------------------------
# Vraie interface pour les agriculteurs, servie par un FastAPI maison qui
# RÉUTILISE le `root_agent` via le `Runner` d'ADK.
#
# NOUVEAUTÉS :
#   - Sessions PERSISTANTES (DatabaseSessionService → SQLite) : on peut
#     reprendre une ancienne conversation même après redémarrage.
#   - Multi-UTILISATEURS : un petit registre JSON (ADK ne liste pas les users) ;
#     chaque utilisateur a plusieurs sessions (gérées par ADK via user_id).
#
# Endpoints :
#   POST   /api/users                                  → créer un utilisateur
#   GET    /api/users                                  → lister les utilisateurs
#   GET    /api/users/{uid}/sessions                   → lister les sessions
#   POST   /api/users/{uid}/sessions                   → créer une session
#   GET    /api/users/{uid}/sessions/{sid}             → reprendre (historique)
#   DELETE /api/users/{uid}/sessions/{sid}             → supprimer une session
#   POST   /api/chat                                   → dialoguer (streaming SSE)
#
# Modèle : gemini-3.5-flash (texte + photo).
# Le serveur MCP (port 8080) doit tourner pour les questions de marché.
# ==========================================================================
"""

import base64
import json
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService
from google.genai import types

# Importer root_agent déclenche l'injection de truststore (via l'outil météo).
from agriculture_agent import root_agent

APP_NAME = "jakkaarloo"
_BASE = Path(__file__).parent
_STATIC_DIR = _BASE / "static"
_DATA_DIR = _BASE / "data"
_DATA_DIR.mkdir(exist_ok=True)
_USERS_FILE = _DATA_DIR / "users.json"
# Base SQLite pour les sessions. DatabaseSessionService utilise un moteur ASYNC
# → driver « aiosqlite » obligatoire (dialecte sqlite+aiosqlite), chemin en
# slashes pour l'URL SQLAlchemy.
_DB_URL = f"sqlite+aiosqlite:///{(_DATA_DIR / 'jakkaarloo_sessions.db').as_posix()}"

# Un seul service de sessions (persistant) et un seul Runner, réutilisés partout.
_session_service = DatabaseSessionService(db_url=_DB_URL)
_runner = Runner(app_name=APP_NAME, agent=root_agent, session_service=_session_service)

_TITRE_DEFAUT = "Nouvelle conversation"


# --- Petit registre d'utilisateurs (fichier JSON) --------------------------
# ADK identifie un utilisateur par un simple `user_id` mais ne sait pas LISTER
# les utilisateurs : on tient donc un registre local léger.
def _charger_users() -> list[dict]:
    if _USERS_FILE.exists():
        return json.loads(_USERS_FILE.read_text(encoding="utf-8"))
    return []


def _sauver_users(users: list[dict]) -> None:
    _USERS_FILE.write_text(
        json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _maintenant() -> str:
    return datetime.now(timezone.utc).isoformat()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    try:
        await _runner.close()  # ferme proprement le toolset MCP
    except Exception:  # noqa: BLE001
        pass


app = FastAPI(title="Jàkkaarloo", lifespan=lifespan)


# ===========================================================================
# UTILISATEURS
# ===========================================================================
class UserIn(BaseModel):
    name: str
    region: str = ""
    crops: list[str] = []


@app.post("/api/users")
async def creer_utilisateur(u: UserIn):
    """Crée un utilisateur (nom, région, cultures) et renvoie sa fiche."""
    users = _charger_users()
    entree = {
        "id": "u-" + uuid.uuid4().hex[:12],
        "name": (u.name or "").strip() or "Agriculteur",
        "region": (u.region or "").strip(),
        "crops": [c.strip() for c in (u.crops or []) if c.strip()],
        "created_at": _maintenant(),
    }
    users.append(entree)
    _sauver_users(users)
    return entree


@app.get("/api/users")
async def lister_utilisateurs():
    """Liste les utilisateurs connus (pour l'écran de sélection)."""
    return _charger_users()


# ===========================================================================
# SESSIONS
# ===========================================================================
@app.get("/api/users/{user_id}/sessions")
async def lister_sessions(user_id: str):
    """Liste les sessions d'un utilisateur, la plus récente en premier."""
    reponse = await _session_service.list_sessions(
        app_name=APP_NAME, user_id=user_id
    )
    items = [
        {
            "id": s.id,
            "titre": (s.state or {}).get("titre", _TITRE_DEFAUT),
            "last_update_time": s.last_update_time,
        }
        for s in reponse.sessions
    ]
    items.sort(key=lambda x: x["last_update_time"] or 0, reverse=True)
    return items


@app.post("/api/users/{user_id}/sessions")
async def creer_session(user_id: str):
    """Crée une nouvelle session (conversation vide) pour l'utilisateur."""
    sid = "s-" + uuid.uuid4().hex[:12]
    await _session_service.create_session(
        app_name=APP_NAME,
        user_id=user_id,
        session_id=sid,
        state={"titre": _TITRE_DEFAUT},
    )
    return {"id": sid, "titre": _TITRE_DEFAUT}


def _transcript(session) -> list[dict]:
    """Reconstruit l'historique lisible d'une session à partir de ses events
    (on ignore les appels d'outils et les réponses techniques)."""
    messages = []
    for ev in (session.events or []):
        content = getattr(ev, "content", None)
        if not content or not getattr(content, "parts", None):
            continue
        texte = ""
        a_image = False
        for p in content.parts:
            t = getattr(p, "text", None)
            if t and t.startswith(_MARQUEUR_CTX):
                continue  # consigne interne : on ne l'affiche pas dans l'historique
            if t:
                texte += t
            if getattr(p, "inline_data", None):
                a_image = True
        texte = texte.strip()
        if not texte and not a_image:
            continue  # event purement technique (outil, transfert…)
        role = "user" if getattr(content, "role", "") == "user" else "agent"
        messages.append({"role": role, "text": texte, "has_image": a_image})
    return messages


@app.get("/api/users/{user_id}/sessions/{session_id}")
async def reprendre_session(user_id: str, session_id: str):
    """Renvoie l'historique d'une session pour la REPRENDRE."""
    session = await _session_service.get_session(
        app_name=APP_NAME, user_id=user_id, session_id=session_id
    )
    if session is None:
        raise HTTPException(status_code=404, detail="Session introuvable")
    return {
        "id": session.id,
        "titre": (session.state or {}).get("titre", _TITRE_DEFAUT),
        "messages": _transcript(session),
    }


@app.delete("/api/users/{user_id}/sessions/{session_id}")
async def supprimer_session(user_id: str, session_id: str):
    """Supprime définitivement une session."""
    await _session_service.delete_session(
        app_name=APP_NAME, user_id=user_id, session_id=session_id
    )
    return {"ok": True}


# ===========================================================================
# CHAT (streaming SSE)
# ===========================================================================
class ChatInput(BaseModel):
    user_id: str
    session_id: str
    message: str = ""
    image_base64: Optional[str] = None
    image_mime: Optional[str] = None
    lang: str = "fr"  # langue de réponse souhaitée ("fr" ou "wo")


# Marqueur d'une consigne INTERNE (contexte profil + langue) glissée dans le
# message : le modèle la lit mais on la masque du transcript affiché.
_MARQUEUR_CTX = "[[CTX]]"


def _directive_contexte(profil: dict, lang: str) -> str:
    """Construit une consigne interne : profil de l'agriculteur + langue.
    Rend les réponses contextuelles (météo de sa région, ses cultures…)."""
    nom = profil.get("name", "")
    region = profil.get("region", "")
    crops = ", ".join(profil.get("crops", []) or [])
    langue = "wolof" if lang == "wo" else "français"
    bits = []
    if nom:
        bits.append(f"l'agriculteur s'appelle {nom}")
    if region:
        bits.append(f"il est à {region} (utilise cette ville par défaut pour la météo)")
    if crops:
        bits.append(f"ses cultures : {crops}")
    contexte = " ; ".join(bits) if bits else "profil non renseigné"
    return (
        f"{_MARQUEUR_CTX} Contexte à utiliser sans jamais le mentionner : "
        f"{contexte}. Réponds en {langue}. N'utilise pas d'emoji."
    )


_STATUT_OUTILS = {
    "transfer_to_agent": "Orientation vers le bon spécialiste…",
    "diagnose_crop_issue": "Analyse du problème…",
    "lister_problemes_connus": "Analyse de la photo…",
    "get_weather_forecast": "Consultation de la météo…",
    "get_market_prices": "Consultation des prix du marché…",
    "get_crop_calendar": "Consultation du calendrier cultural…",
}


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


def _construire_message(inp: ChatInput, directive: str = "") -> types.Content:
    parts = []
    texte = inp.message.strip()
    if texte:
        parts.append(types.Part(text=texte))
    if inp.image_base64:
        if not texte:
            parts.append(
                types.Part(text="Voici une photo de ma plante. Qu'est-ce qui ne va pas ?")
            )
        donnees = base64.b64decode(inp.image_base64)
        parts.append(
            types.Part.from_bytes(data=donnees, mime_type=inp.image_mime or "image/jpeg")
        )
    if not parts:
        parts.append(types.Part(text="Bonjour"))
    if directive:  # consigne interne (profil + langue), ajoutée en dernier
        parts.append(types.Part(text=directive))
    return types.Content(role="user", parts=parts)


@app.post("/api/chat")
async def chat(inp: ChatInput) -> StreamingResponse:
    """Dialogue avec l'agent ; réponse en streaming (Server-Sent Events)."""
    session = await _session_service.get_session(
        app_name=APP_NAME, user_id=inp.user_id, session_id=inp.session_id
    )
    if session is None:  # défensif : crée la session si le client ne l'a pas fait
        session = await _session_service.create_session(
            app_name=APP_NAME,
            user_id=inp.user_id,
            session_id=inp.session_id,
            state={"titre": _TITRE_DEFAUT},
        )

    # Sur le PREMIER message, on donne un titre à la session (aperçu du message).
    state_delta = None
    titre_actuel = (session.state or {}).get("titre")
    if inp.message.strip() and titre_actuel in (None, "", _TITRE_DEFAUT):
        state_delta = {"titre": inp.message.strip()[:60]}

    # Consigne interne : profil de l'agriculteur (depuis le registre) + langue.
    profils = {u["id"]: u for u in _charger_users()}
    directive = _directive_contexte(profils.get(inp.user_id, {}), inp.lang)
    nouveau_message = _construire_message(inp, directive)

    async def flux():
        partiel_envoye = False
        try:
            async for event in _runner.run_async(
                user_id=inp.user_id,
                session_id=inp.session_id,
                new_message=nouveau_message,
                state_delta=state_delta,
                run_config=RunConfig(streaming_mode=StreamingMode.SSE),
            ):
                if not (event.content and event.content.parts):
                    continue
                for part in event.content.parts:
                    appel = getattr(part, "function_call", None)
                    if appel:
                        libelle = _STATUT_OUTILS.get(appel.name)
                        if libelle:
                            yield _sse({"type": "status", "text": libelle})
                        continue
                    texte = getattr(part, "text", None)
                    if not texte:
                        continue
                    if getattr(event, "partial", False):
                        partiel_envoye = True
                        yield _sse({"type": "delta", "text": texte})
                    else:
                        if not partiel_envoye:
                            yield _sse({"type": "delta", "text": texte})
                        partiel_envoye = False
            yield _sse({"type": "done"})
        except Exception as e:  # noqa: BLE001
            yield _sse({"type": "error", "text": f"{type(e).__name__}: {e}"})

    return StreamingResponse(flux(), media_type="text/event-stream")


# ===========================================================================
# Fichiers statiques
# ===========================================================================
@app.get("/")
async def index() -> FileResponse:
    return FileResponse(_STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")
