# Déploiement de Jàkkaarloo (bonus)

Ce guide décrit un déploiement reproductible sur **Google Cloud Run**. Le
déploiement live n'est pas obligatoire pour le concours : l'objectif ici est
de montrer que le projet **est déployable** et que la **clé API reste secrète**
(injectée via Secret Manager, jamais dans l'image ni dans le code).

> Prérequis : un projet Google Cloud, `gcloud` installé et authentifié, la
> facturation activée, et une clé API Gemini.

---

## 1. Variables de travail

```bash
export PROJECT_ID="votre-projet-gcp"
export REGION="europe-west1"
export SERVICE="jakkaarloo"
export REPO="jakkaarloo-repo"

gcloud config set project "$PROJECT_ID"
```

## 2. Activer les API nécessaires

```bash
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com
```

## 3. Stocker la clé Gemini dans Secret Manager

**C'est le point clé de sécurité** : la clé n'est jamais dans le dépôt ni dans
l'image. Elle vit dans Secret Manager et n'est injectée qu'à l'exécution.

```bash
# Crée le secret et y met la valeur (remplacez par votre vraie clé).
printf "VOTRE_CLE_GEMINI" | gcloud secrets create GOOGLE_API_KEY \
  --data-file=- --replication-policy=automatic

# Autorise le compte de service de Cloud Run à lire le secret.
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
gcloud secrets add-iam-policy-binding GOOGLE_API_KEY \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

## 4. Construire et pousser l'image

```bash
# Dépôt d'images Artifact Registry.
gcloud artifacts repositories create "$REPO" \
  --repository-format=docker --location="$REGION"

IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/${SERVICE}:latest"

# Build à distance via Cloud Build (utilise notre Dockerfile).
gcloud builds submit --tag "$IMAGE"
```

## 5. Déployer sur Cloud Run

```bash
gcloud run deploy "$SERVICE" \
  --image "$IMAGE" \
  --region "$REGION" \
  --allow-unauthenticated \
  --port 8000 \
  --set-env-vars "GOOGLE_GENAI_USE_VERTEXAI=FALSE,JAKKAARLOO_MODEL=gemini-3.5-flash,MCP_MARKET_URL=http://localhost:8080/mcp" \
  --set-secrets "GOOGLE_API_KEY=GOOGLE_API_KEY:latest"
```

- `--set-secrets` monte le secret comme variable d'environnement `GOOGLE_API_KEY`.
- Le conteneur lance le **serveur MCP** en arrière-plan puis l'**interface web
  FastAPI** (`web_app.main:app`) sur `$PORT` (voir `Dockerfile`).

À la fin, `gcloud` affiche l'URL publique du service (`.../run.app`).

## 6. Vérifier

```bash
SERVICE_URL=$(gcloud run services describe "$SERVICE" --region "$REGION" --format='value(status.url)')
curl -s "$SERVICE_URL/" | grep -o "Jàkkaarloo"   # la page de chat se sert bien
```

Ouvrez ensuite l'URL du service dans un navigateur : l'interface de chat
Jàkkaarloo s'affiche (texte + photo). L'endpoint `/api/chat` renvoie la réponse
de l'agent en streaming (SSE).

---

## Alternative : Vertex AI Agent Engine

ADK peut aussi être déployé sur **Vertex AI Agent Engine** (service géré pour
agents). Dans ce cas, `GOOGLE_GENAI_USE_VERTEXAI=TRUE` et l'authentification se
fait via le compte de service du projet (pas de clé API en clair). Voir la
documentation Google ADK « Deploy to Agent Engine ».

## Rappel sécurité

- ❌ Ne jamais committer `.env` ni de clé (déjà bloqué par `.gitignore`).
- ✅ Secrets uniquement via Secret Manager (ou variables d'environnement du
  service), injectés à l'exécution.
- ✅ `tool_filter` limite les outils MCP réellement exposés à l'agent.
