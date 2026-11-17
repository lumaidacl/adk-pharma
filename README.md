# Pharma R&D & Regulatory Radar — Google ADK Live Demo

Enterprise reference project built for the technical talk and live-coding session **"Get started with Agent Development Kit (ADK)"**.

This project demonstrates how a single **Google Agent Development Kit (ADK)** agent (`root_agent`) equipped with real-time Google Search grounding (`google_search`) runs seamlessly across **three local execution modes** and **two managed Google Cloud production runtimes** without changing a single line of agent logic:

- **Local Execution Modes**
  1. **Visual Debugging & Trace UI** (`make web` / `adk web agents`)
  2. **Interactive CLI Terminal** (`make cli` / `adk run agents/pharma_agent`)
  3. **Asynchronous Programmatic Python Runtime** (`make run` / `python runners/run_programmatic.py`)
- **Cloud Production Targets**
  4. **Google Cloud Run** (`make deploy-cloud-run` or `make deploy-cloud-run-docker`)
  5. **Vertex AI Agent Engine** (`make deploy-agent-engine` or `make deploy-agent-engine-sdk`)

---

## Project Structure

```text
adk-pharma/
├── .dockerignore
├── .env.example
├── .gitignore
├── Dockerfile                          # Production container recipe for Cloud Run
├── Makefile                            # Unified local & cloud automation targets
├── README.md
├── requirements.txt
│
├── agents/                             # Dedicated ADK agents workspace
│   ├── __init__.py
│   └── pharma_agent/
│       ├── __init__.py                 # Exposes `agent` for ADK discovery
│       ├── agent.py                    # Concise `root_agent` definition
│       └── prompts.py                  # Agent description & executive system instructions
│
├── runners/                            # Local programmatic execution scripts
│   ├── __init__.py
│   └── run_programmatic.py             # Async `Runner` + `InMemorySessionService` live demo
│
└── deployment/                         # Production cloud runtimes & lifecycle managers
    ├── __init__.py
    ├── cloud_run/
    │   ├── __init__.py
    │   └── server.py                   # FastAPI entrypoint (`get_fast_api_app` + `/healthz`)
    └── vertex_ai/
        ├── __init__.py
        └── agent_engine.py             # Vertex AI Agent Engine SDK (`deploy | list | delete`)
```

---

## Quick Installation Guide

### Prerequisites
- **Python 3.10+**
- **Google AI Studio API Key** for local development ([Get an API key](https://aistudio.google.com/apikey))
- **`gcloud` CLI** (only required for Cloud Run or Vertex AI Agent Engine deployments)

### 1. Create virtual environment & install dependencies

Using `make`:

```bash
make install
make env
```

Or manually:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

### 2. Configure `.env`

For local execution with Google AI Studio, edit `.env`:

```ini
GOOGLE_GENAI_USE_VERTEXAI=FALSE
GOOGLE_API_KEY=AIzaSyYourRealApiKeyHere
```

*(Run `make help` at any time to view all available targets.)*

---

## Running the 3 Local Demo Modes

Run all commands from the **project root directory**:

### Mode 1: Visual Web UI & Trace Inspector (`adk web`)
Launches the interactive ADK Developer UI (`http://localhost:8000`) scoped strictly to `agents/` so only real ADK agents appear in the dropdown:

```bash
make web
# Equivalent to: adk web agents
```

### Mode 2: Interactive Terminal Chat (`adk run`)
Runs `root_agent` in an interactive multi-turn terminal session:

```bash
make cli
# Equivalent to: adk run agents/pharma_agent
```

### Mode 3: Asynchronous Programmatic Streaming (`Runner` + `InMemorySessionService`)
Displays an animated live loading indicator (with elapsed timer and phase updates) while Gemini grounds clinical/regulatory evidence via `google_search`, then streams the executive briefing in real time (`StreamingMode.SSE`) followed by verified search queries and citation sources:

```bash
# Default CRISPR / gene-editing prompt (live spinner + SSE token stream)
make run
# Equivalent to: python -u runners/run_programmatic.py

# Custom prompt with real-time streaming
make run PROMPT="Analyze the latest FDA and EMA regulatory status of dual and triple GLP-1/GIP agonists for obesity and MASH."

# Optional: disable token streaming to compare batch vs. streaming UX
make run STREAM=false
```

---

## Deploying to Google Cloud (Cloud Run & Vertex AI Agent Engine)

### 1. Authenticate & Bootstrap GCP Project
Set `GOOGLE_CLOUD_PROJECT` in `.env` (or pass `PROJECT_ID=<your-project-id>` on the CLI), authenticate with Google Cloud, and enable required APIs + create the GCS staging bucket:

```bash
gcloud auth login
gcloud auth application-default login
make gcp-setup PROJECT_ID=your-gcp-project-id
```

### 2. Deploy to Google Cloud Run

- **Option A — Native ADK CLI deployment** (bundles `agents/pharma_agent`, Cloud Trace, and ADK Web UI):
  ```bash
  make deploy-cloud-run PROJECT_ID=your-gcp-project-id
  ```
- **Option B — Custom production container (`deployment/cloud_run/server.py` + `Dockerfile`)**:
  ```bash
  make deploy-cloud-run-docker PROJECT_ID=your-gcp-project-id
  ```
  *(Test the container locally before deploying with `make docker-run-local`, and clean up with `make delete-cloud-run`.)*

### 3. Deploy to Vertex AI Agent Engine
Wraps `root_agent` inside a managed `AdkApp` with persistent Vertex AI sessions and OpenTelemetry tracing:

- **Option A — Native ADK CLI deployment:**
  ```bash
  make deploy-agent-engine PROJECT_ID=your-gcp-project-id
  ```
- **Option B — Programmatic Python SDK deployment (`deployment/vertex_ai/agent_engine.py`):**
  ```bash
  make deploy-agent-engine-sdk PROJECT_ID=your-gcp-project-id
  ```
  Inspect or tear down deployed Agent Engine instances anytime:
  ```bash
  make list-agent-engines PROJECT_ID=your-gcp-project-id
  make delete-agent-engine PROJECT_ID=your-gcp-project-id
  ```

---

## Live Demo Copy-Paste Prompts

Use these prompts during your live presentation to highlight real-time search grounding, clinical trial verification, and structured executive synthesis:

### Prompt 1 — Gene Editing & CRISPR Regulatory Milestones (FDA / EMA)
```text
Generate an executive briefing on recent regulatory approvals and clinical advances in ex vivo and in vivo CRISPR or gene-editing therapies across the FDA and EMA.
```

### Prompt 2 — Oncology Antibody-Drug Conjugates (ADCs) Competitive Landscape
```text
Analyze recent Phase III clinical readouts and FDA or EMA approvals for TROP2- and HER2-targeted antibody-drug conjugates (ADCs) in solid tumors, detailing sponsor companies and confirmed milestone dates.
```

### Prompt 3 — Alzheimer's Disease & Neurodegeneration Regulatory Radar
```text
Evaluate the current regulatory landscape and most recent FDA and EMA decisions on anti-amyloid therapies for early Alzheimer's disease, including pharmacovigilance requirements (ARIA) and competitive implications.
```

### Prompt 4 — Type 2 Diabetes & Obesity (Oral GLP-1s & Next-Gen Incretins)
```text
Provide an executive briefing on the latest Phase III clinical trial results and FDA or EMA regulatory milestones for oral GLP-1 receptor agonists and next-generation multi-receptor incretin therapies in Type 2 diabetes and obesity.
```
