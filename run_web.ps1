# ===========================================================================
# Lance l'INTERFACE WEB de Jàkkaarloo (backend FastAPI + UI de chat).
#
# Mode texte + photo (modèle gemini-3.5-flash lu depuis .env). Pour les
# questions de marché, le serveur MCP doit tourner dans un AUTRE terminal :
#     python mcp_server\market_server.py
#
# USAGE (depuis la racine du projet) :
#     .\run_web.ps1
# Puis ouvrez http://127.0.0.1:8000 dans votre navigateur.
# ===========================================================================

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot
& "$PSScriptRoot\.venv\Scripts\Activate.ps1"

# Force le modèle texte+photo, même si une variable est restée en mémoire dans
# ce terminal. (uvicorn lit cette variable ; load_dotenv ne l'écrase pas.)
$env:JAKKAARLOO_MODEL = "gemini-3.5-flash"

# Terminal propre pour la démo (masque les UserWarning « EXPERIMENTAL »).
$env:PYTHONWARNINGS = "ignore::UserWarning"

Write-Host ""
Write-Host "  INTERFACE WEB Jakkaarloo -> http://127.0.0.1:8000" -ForegroundColor Green
Write-Host "  Rappel : le serveur MCP doit tourner dans un autre terminal." -ForegroundColor DarkYellow
Write-Host ""

# Serveur ASGI. --reload pratique en dev (recharge au changement de code).
python -m uvicorn web_app.main:app --host 127.0.0.1 --port 8000 --reload
