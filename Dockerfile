# ---------------------------------------------------------------------------
# Image conteneur de Jàkkaarloo.
#
# CONCEPT DÉMONTRÉ : DÉPLOYABILITÉ
# Un seul conteneur exécute DEUX processus :
#   1) le serveur MCP « marché » (en arrière-plan, sur le port 8080) ;
#   2) l'interface web FastAPI (web_app.main) qui sert l'UI + l'agent sur $PORT.
# L'agent se connecte au serveur MCP via localhost, à l'intérieur du conteneur.
#
# ⚠️ AUCUN SECRET n'est copié dans l'image. La clé Gemini est injectée à
#    l'exécution via une variable d'environnement (voir deploy.md :
#    Secret Manager sur Cloud Run).
# ---------------------------------------------------------------------------
FROM python:3.11-slim

# Bonnes pratiques Python en conteneur : pas de .pyc, logs non bufferisés.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 1) Dépendances d'abord (meilleure mise en cache des couches Docker).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 2) Code applicatif.
COPY . .

# Le serveur MCP tourne en local dans le conteneur ; l'agent s'y connecte ici.
ENV MCP_MARKET_URL=http://localhost:8080/mcp
# Cloud Run fournit $PORT ; 8000 par défaut en local.
ENV PORT=8000
EXPOSE 8000

# Démarre le serveur MCP en tâche de fond, puis l'interface web au premier plan.
# `exec` fait d'uvicorn le processus principal (bonne gestion des signaux).
CMD ["sh", "-c", "python mcp_server/market_server.py & exec uvicorn web_app.main:app --host 0.0.0.0 --port ${PORT}"]
