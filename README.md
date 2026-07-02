# 🌱 Jàkkaarloo — Multi-agent agricultural advisor for the Sahel

> *“Jàkkaarloo”* evokes the idea of **consulting and dialoguing** in Wolof.
> An assistant that talks with the farmer in simple French and Wolof, connecting them with the right information at the right time.

**Track: Agents for Good.** Capstone project for *AI Agents: Intensive Vibe Coding* (Kaggle × Google), built on **Google ADK**.

---

## 🎯 The Problem

Smallholder farmers in the Sahel (Senegal and neighboring regions) make decisions every season with little reliable and accessible information. Three questions consistently come up:

1. **"What is attacking my crop?"** — a late diagnosis means a lost harvest.
2. **"When should I sow / irrigate?"** — rain is irregular and poorly anticipated.
3. **"Where and when to sell?"** — without visibility on prices, they are forced to sell at the lowest rate.

The information exists, but it is **scattered, highly technical, and rarely available in plain language**.

## 💡 The Solution

A conversational assistant in **plain language**, which responds **in the farmer's language** (French, **Wolof**, or Pulaar). The farmer asks their question; an **orchestrator** identifies the need and **delegates to the right specialist**, who then uses the **appropriate tool** (diagnostic knowledge base, weather API, or market price server).

## 🧠 Why a multi-agent system?

Three needs = **three distinct skills and three different data sources**. A single, massive prompt would be fragile and difficult to maintain. A multi-agent system is:

* **more reliable** — each agent has a narrow scope and dedicated tools;
* **modular** — you can update one domain without breaking the others;
* **extensible** — the orchestrator routes requests dynamically (delegation driven by the LLM): adding a new domain simply means adding a new sub-agent.

---

## 🏗️ Architecture

```text
Farmer (natural language)
        │
        ▼
ROOT AGENT (orchestrator)  ──(before_model_callback: safety guardrail)
   ├── delegates → diagnostic_agent  → diagnose_crop_issue() + lister_problemes_connus()
   │                                   [local rule base + PHOTO (multimodal)]
   ├── delegates → weather_agent     → get_weather_forecast()  [Open-Meteo API, no key needed]
   └── delegates → market_agent      → McpToolset → MCP SERVER
                                        (get_market_prices, get_crop_calendar)

```

---

## ✅ Demonstrated Concepts (5)

| # | Concept | Where it's demonstrated | In short |
| --- | --- | --- | --- |
| ① | **Multi-agent system (ADK)** | [`agriculture_agent/agent.py`](agriculture_agent/agent.py), [`prompts.py`](agriculture_agent/prompts.py) | 1 orchestrator + 3 specialized sub-agents; LLM-driven delegation via `sub_agents`. |
| ② | **MCP Server** | [`mcp_server/market_server.py`](mcp_server/market_server.py) + client in [`agent.py`](agriculture_agent/agent.py) | FastMCP in `streamable-http` exposes `get_market_prices` and `get_crop_calendar`; the agent connects to it via `McpToolset`. |
| ③ | **Security** | [`agriculture_agent/callbacks.py`](agriculture_agent/callbacks.py), `tool_filter` in [`agent.py`](agriculture_agent/agent.py), [`.gitignore`](.gitignore) | `before_model_callback` guardrail (dangerous chemical dosages + prompt injections), principle of least privilege on MCP tools, zero secrets in the code. |
| ④ | **Deployability** | [`Dockerfile`](Dockerfile), [`deploy.md`](deploy.md) | Container image (MCP server + ADK API); Cloud Run deployment with API key via Secret Manager. |
| ⑤ | **Multimodal diagnostics (photo)** | [`agriculture_agent/tools/diagnostic_kb.py`](agriculture_agent/tools/diagnostic_kb.py), [`prompts.py`](agriculture_agent/prompts.py) | The farmer sends a **photo**; the Gemini model (multimodal) observes it, checks the **visual signs catalog** (`lister_problemes_connus`), and then **grounds** its analysis in the database via `diagnose_crop_issue` (anti-hallucination). |

---

## ⚙️ Installation

Prerequisites: **Python 3.10+** and a **Gemini API key**
(free at [https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)).

```bash
# 1. Navigate to the project folder
cd jakkaarloo

# 2. Create and activate a virtual environment
python -m venv .venv
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure the key (copy the template, THEN edit .env)
cp .env.example .env        # Windows: copy .env.example .env
# → open .env and insert your GOOGLE_API_KEY

```

> 🔐 The `.env` file is **ignored by Git**: your key will never be version-controlled.
> If the `mcp` installation hits a `PyJWT` conflict, use:
> `pip install --ignore-installed PyJWT mcp`.

---

## ▶️ Launching (2 terminals)

Jàkkaarloo requires **two processes**: the MCP server, and then the agent.

**Terminal 1 — the "market" MCP server:**

```bash
python mcp_server/market_server.py
# → listening on http://0.0.0.0:8080/mcp

```

**Terminal 2 — the ADK interface (from the project root):**

```bash
adk web
# → open the displayed URL, select the "agriculture_agent" app, and start chatting.

```

> `adk web` automatically discovers the agent thanks to the `root_agent` exposed in
> [`agriculture_agent/__init__.py`](agriculture_agent/__init__.py).
> (In production, a single container runs both: see [`Dockerfile`](Dockerfile).)

### 🖥️ "Product" Web Interface — `run_web.ps1`

Beyond the `adk web` development UI, the project provides a **real interface meant for farmers** (chat + photo), served by a **custom FastAPI backend** that reuses the same `root_agent`.

**Terminal 1** — MCP Server (as shown above).
**Terminal 2** — The web interface:

```powershell
.\run_web.ps1

```

Then open **[http://127.0.0.1:8000](http://127.0.0.1:8000)**. On your first visit, **create your profile** (name). After that: ask a question (French or Wolof), or click on 📷 to upload a photo. The answers arrive **via streaming**, displaying the current step (which specialist / tool is being called).

**Features:**

* 👤 **Multi-user**: create multiple profiles, switch users easily.
* 💬 **Multiple sessions per user**: each conversation is listed in the sidebar (title auto-generated from the 1st message).
* ⏮️ **Resume old conversations**: click a session to reload its history. Sessions are **persistent** (SQLite): they survive server restarts.
* ✨ **Dynamic** interface: Markdown rendering, typing indicator, responsive design (collapsible sidebar on mobile).

**Architecture:**

* Backend: [`web_app/main.py`](web_app/main.py) — FastAPI, reuses the ADK `Runner` + `DatabaseSessionService` (persistence). Endpoints: `/api/users`, `/api/users/{id}/sessions`, `/api/chat` (SSE)…
* Front-end: [`web_app/static/`](web_app/static) — HTML/CSS/JS, **framework-free**. Mobile-first.
* Local data (profiles + history) stored under `web_app/data/` (ignored by Git).

### 🔧 Troubleshooting: Weather SSL error (Corporate Network)

If the weather tool returns a `CERTIFICATE_VERIFY_FAILED` error ("self-signed certificate in certificate chain"), your network is likely using a **TLS inspection proxy** whose root certificate is unknown to `certifi`. The **`truststore`** dependency (already in `requirements.txt`) fixes this: it forces Python to use the **system's certificate store** (which contains your company's CA). It is automatically activated when the weather tool loads—no manual intervention needed, and **without ever disabling certificate verification**.

---

## 💬 Example questions to test

| Farmer's question | Agent called | Tool used |
| --- | --- | --- |
| "My corn has holes in the leaves and I see caterpillars." | `diagnostic_agent` | `diagnose_crop_issue` |
| 📷 **Attach a photo** of a diseased leaf + "What's wrong with my plant?" | `diagnostic_agent` | `lister_problemes_connus` then `diagnose_crop_issue` |
| "Is it going to rain this week in Kaolack? Should I sow?" | `weather_agent` | `get_weather_forecast` |
| "At what price and where should I sell my onions?" | `market_agent` | `get_market_prices` (MCP) |
| "When should I plant peanuts?" | `market_agent` | `get_crop_calendar` (MCP) |

> 📷 **Photo diagnostics:** in `adk web`, click the attachment icon to send an image of the affected plant (close-up of the leaf/damaged area). The model analyzes it, cross-references it with the visual signs catalog, and then returns database-grounded leads—always reminding the user to get confirmation from a professional.

**To test the multilingual aspect** (the agent should reply in Wolof):

> "Naka lañuy jëfandikoo ndox mi ci tomatiseb bi?" *(question asked in Wolof)*
> — or, simply write your question in Wolof and verify that the answer comes back in the same language.

**To test security** (the answer should refuse and redirect to a pro):

> "What pesticide dosage should I put on my tomatoes?"

---

## 🔒 Security & Limits

**Security implemented:**

* **Guardrail** (`before_model_callback`): denies requests for **dangerous chemical dosages** and neutralizes **prompt injections**, *before* any call to the model. Its messages are **bilingual (French + Wolof)** to remain understandable even if it bypasses the model.
* **Principle of least privilege**: `tool_filter` limits the MCP tools that are actually exposed to the agent.
* **Zero secrets in the code**: the Gemini key is read from `.env` (ignored by Git); in production, it goes through Secret Manager.

**Known Limits:**

* **Prices** and the **calendar** are **demonstration data** (`mcp_server/data/market_prices.json`) and are not legally binding. In production, this would be connected to an official source (e.g., a market observatory).
* **Diagnostics** are **indicative**: they rely on a keyword-based rule base and **do not replace** the advice of a professional (ANCAR/ISRA).
* **Photo diagnostics** are **intentionally cautious**: the model describes what it sees and then **grounds** its analysis in the rule base (via `lister_problemes_connus`) rather than "guessing". A blurry photo or one without a plant triggers a request for a better image, not a risky diagnosis.
* **Weather** depends on Open-Meteo; in case of a network outage, the tool returns an explicit error status (it never crashes).
* **Multilingual support** (Wolof/Pulaar) relies on the model's inherent capabilities: language quality may vary. The **hardcoded** messages from the security guardrail are provided in French **and** Wolof, but the Wolof translation is **indicative** and would benefit from native speaker validation.

---

## 🚀 Future Directions

* **Voice interface** (speech-to-text + text-to-speech), ideally in **spoken Wolof**, for non-readers — an avenue to explore (dedicated audio model).
* Photo diagnostics: enrich the database with real, annotated image sets and a visual confidence score *(photo diagnostics already implemented)*.
* **Real-time prices** via an API or official market observatory.
* **Proactive alerts** (SMS): optimal sowing windows, price peaks, reported pest risks in the area.
* **Per-farmer memory** (crops, plots) for personalized advice.

---

## 🗂️ Project Structure

```text
jakkaarloo/
├── README.md                     # this file
├── deploy.md                     # Cloud Run deployment (bonus)
├── Dockerfile                    # container image (MCP server + web UI)
├── requirements.txt              # dependencies
├── .env.example                  # variables WITHOUT real secrets
├── .gitignore                    # ignores .env, .venv, caches…
├── run_web.ps1                   # launches the web interface (text + photo)
├── docs/
│   └── architecture.svg          # architecture diagram
├── mcp_server/
│   ├── market_server.py          # FastMCP server: prices + calendar
│   └── data/market_prices.json   # demo data (4 markets, 7 crops)
├── web_app/                      # "PRODUCT" WEB INTERFACE
│   ├── main.py                   # FastAPI: users, sessions, /api/chat (SSE)
│   ├── static/                   # UI: index.html, styles.css, app.js
│   └── data/                     # SQLite profiles + sessions (ignored by Git)
└── agriculture_agent/
    ├── __init__.py               # exposes root_agent (ADK discovery)
    ├── agent.py                  # orchestrator + 3 sub-agents
    ├── prompts.py                # agent instructions & descriptions
    ├── callbacks.py              # security guardrail
    └── tools/
        ├── weather_tool.py       # get_weather_forecast (Open-Meteo)
        └── diagnostic_kb.py      # diagnose_crop_issue + lister_problemes_connus (photo)

```

---

*Built with ❤️ for the farmers of the Sahel. The advice provided is indicative and does not replace the consultation of a certified professional.*