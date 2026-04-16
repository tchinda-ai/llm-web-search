# 🔍 LLM App with Web Search

A research assistant that combines **real-time web search** with a **cloud LLM** (via NVIDIA NIM) to deliver structured, source-cited answers — fully containerised, two commands to run.

> 📺 Watch the original demo video: **[YouTube →](https://youtu.be/kNgx0AifVo0)**

---

## 🔀 Two Editions — Choose Your Architecture

This project ships two fully independent configurations on separate branches, representing different architectural trade-offs:

| | `main` ← **you are here** | `feature/local-llm` |
|---|---|---|
| **LLM backend** | NVIDIA NIM (cloud API) | Ollama (runs locally in Docker) |
| **Inference speed** | Fast — cloud GPUs | Slow on CPU, fast with local GPU |
| **Privacy** | Queries sent to NVIDIA | 100% local — nothing leaves your machine |
| **API cost** | Free tier available | Free — no external calls |
| **Docker services** | 2 (`searxng` + `app`) | 4 (`ollama` + `model-init` + `searxng` + `app`) |
| **First-run time** | ~30 seconds | ~10 min (4.7 GB model download) |
| **Disk space needed** | ~1.5 GB (images only) | ~6.5 GB (images + model weights) |
| **RAM needed** | 2 GB | 8 GB |
| **Model switching** | Edit `.env`, restart | Pull new model, update config |

---

## 🏗 Architecture (`main` — NVIDIA NIM)

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Browser                            │
│                      http://localhost:8501                       │
└──────────────────────────────┬──────────────────────────────────┘
                               │ HTTP
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│               Streamlit App  (llm-web-search container)          │
│                                                                  │
│  1. enrich_query()    — appends year for time-sensitive queries  │
│  2. get_web_urls()    — queries SearXNG JSON API                 │
│  3. crawl_webpages()  — headless Chromium via crawl4ai           │
│  4. build_context()   — keyword-ranks paragraphs + source URLs   │
│  5. call_llm()        — streams answer from NVIDIA NIM           │
└────────┬───────────────────────────────────┬────────────────────┘
         │ HTTP :8080                         │ HTTPS
         ▼                                    ▼
┌─────────────────────┐           ┌───────────────────────────────┐
│      SearXNG        │           │     NVIDIA NIM Cloud API      │
│  (self-hosted)      │           │  integrate.api.nvidia.com/v1  │
│                     │           │                               │
│  · Google (HTML)    │           │  Model: configurable via      │
│  · Google News      │           │  NVIDIA_MODEL env var         │
│  · Bing             │           │                               │
│  · Brave            │           │  Examples:                    │
│  · DuckDuckGo       │           │  · meta/llama-3.3-70b         │
│  · Wikipedia        │           │  · mistralai/mixtral-8x22b    │
│                     │           │  · google/gemma-7b            │
│  Returns: JSON with │           │  · nvidia/nemotron-70b        │
│  title+snippet+url  │           └───────────────────────────────┘
└─────────────────────┘
```

### Request Flow (step by step)

```
User enters prompt
      │
      ▼
enrich_query()              — appends current year for time-sensitive queries
      │                       "top fintech cameroon" → "top fintech cameroon 2026"
      ▼
get_web_urls()              — sends enriched query to SearXNG JSON API
      │                       returns: list[url] + snippet_context string
      │                       (snippets = fast first-pass context, no crawl needed)
      ▼
check_robots_txt()          — filters out URLs that disallow crawling
      │
      ▼
crawl_webpages()            — spawns headless Chromium via crawl4ai
      │                       JS-rendered pages fully execute (text_mode=False)
      │                       BM25 filters most relevant paragraphs per page
      │                       fallback: raw_markdown if BM25 returns empty
      ▼
build_context_from_crawl()  — scores paragraphs by keyword overlap with query
      │                       prepends SearXNG snippets as lightweight context layer
      │                       embeds [Source: URL] labels in each chunk
      │                       truncates at 6000 chars
      ▼
call_llm()                  — sends system_prompt + context + question
      │                       to NVIDIA NIM via OpenAI-compatible API
      │                       streamed response (token-by-token)
      ▼
st.write_stream()           — renders answer live in browser
st.expander("📚 Sources")   — lists all crawled source URLs
```

---

## 🏗 Architecture (`feature/local-llm` — Ollama)

The local branch adds two extra Docker services to host the LLM on-device:

```
┌─────────────────────────────────────────────────────────────────┐
│               Streamlit App  (llm-web-search container)          │
│  (identical pipeline — only call_llm() target changes)           │
└────────┬──────────────────────┬──────────────────────────────────┘
         │ HTTP :8080            │ HTTP :11434
         ▼                       ▼
┌─────────────────┐    ┌──────────────────────────┐
│    SearXNG      │    │         Ollama            │◄── model-init
│  (identical)    │    │   llama3.1:8b served      │    (one-shot pull)
└─────────────────┘    └──────────────────────────┘
```

**Startup dependency chain** (unique to `feature/local-llm`):
```
ollama starts → healthy → model-init pulls llama3.1:8b → exits 0
searxng starts (parallel) → healthy
                                   └────────────────► app starts
```

---

## 🐳 Infrastructure

### `main` (this branch) — 2 services

| Container | Image | Role | Port |
|---|---|---|---|
| `searxng` | `searxng/searxng:latest` | Self-hosted meta-search engine (JSON API) | `8080` |
| `llm-web-search` | Custom (`Dockerfile`) | Streamlit pipeline orchestrator | `8501` |
| `llm-web-search-api`| Custom (`Dockerfile`) | Flask REST API (JSON/SSE) | `5005` |

### `feature/local-llm` — 4 services

| Container | Image | Role | Port |
|---|---|---|---|
| `ollama` | `ollama/ollama:latest` | Local LLM HTTP server | `11434` |
| `model-init` | `ollama/ollama:latest` | One-shot model downloader — exits after pulling | — |
| `searxng` | `searxng/searxng:latest` | Self-hosted meta-search engine (JSON API) | `8080` |
| `llm-web-search` | Custom (`Dockerfile`) | Streamlit pipeline orchestrator | `8501` |

### Volumes

| Volume | Branch | Purpose |
|---|---|---|
| `ollama_data` | `feature/local-llm` only | Persists downloaded model weights across restarts |
| `./searxng/` | Both | Mounted config — `settings.yml` controls engines + rate-limiting |

---

## 📦 Dependencies

### Python — `main` branch

| Package | Version | Role |
|---|---|---|
| `streamlit` | 1.42.0 | Web UI — widgets, streaming, layout |
| `Crawl4AI` | 0.4.248 | Async headless browser crawler |
| `Markdown` | 3.7 | Markdown processing (used by Crawl4AI internally) |
| `openai` | ≥1.0.0 | OpenAI-compatible client → NVIDIA NIM endpoint |

### Python — `feature/local-llm` branch

Same as above, but `openai` is replaced by:

| Package | Version | Role |
|---|---|---|
| `ollama` | 0.4.7 | Python client for the local Ollama REST API |

### Docker images (both branches)

| Image | Role |
|---|---|
| `python:3.11-slim` | Base image for the Streamlit app container |
| `searxng/searxng:latest` | Self-hosted privacy-respecting meta-search |
| `ollama/ollama:latest` | *(local-llm only)* LLM runtime + model storage |

### System dependencies (Dockerfile)

Chromium + Playwright system libraries — required by Crawl4AI for headless browser rendering of JavaScript-heavy pages. Installed via `apt-get` in the Dockerfile.

---

## ✅ Prerequisites

### `main` (NVIDIA NIM)

| Requirement | Notes |
|---|---|
| **Docker Desktop** | ≥ 4.x |
| **NVIDIA NIM API key** | Free at [build.nvidia.com](https://build.nvidia.com/) |
| **RAM** | 2 GB Docker allocation is sufficient |
| **Disk** | ~1.5 GB |

### `feature/local-llm` (Ollama)

| Requirement | Notes |
|---|---|
| **Docker Desktop** | ≥ 4.x, **8 GB RAM** allocated minimum |
| **Disk** | ~6.5 GB (`llama3.1:8b` ≈ 4.7 GB + images) |
| **First-run internet** | Required to pull model weights |

---

## 🚀 Quick Start (`main` — NVIDIA NIM)

```sh
# 1. Clone
git clone <repo-url>
cd llm-app-with-web-search-demo

# 2. Configure your API key
cp .env.example .env
# Edit .env — add your NVIDIA_API_KEY and optionally change NVIDIA_MODEL

# 3. Start (2 containers, ~30 seconds)
make docker-up

# 4. Open
open http://localhost:8501
```

### Switching models — zero code changes

```sh
# Edit .env:
NVIDIA_MODEL=mistralai/mixtral-8x22b-instruct

# Restart the app container:
docker compose restart app
```

Browse all available models at [build.nvidia.com/explore/discover](https://build.nvidia.com/explore/discover).

---

## 🚀 Quick Start (`feature/local-llm` — Ollama)

```sh
git checkout feature/local-llm

# First run downloads llama3.1:8b (~4.7 GB) — grab a coffee ☕
make docker-up

# Follow progress (watch model-init finish)
make docker-logs

open http://localhost:8501
```

---

### Useful commands (both branches)

```sh
make docker-up     # Build and start all services (detached)
make docker-down   # Stop and remove containers
make docker-logs   # Follow logs from all services
make run           # Run Streamlit locally (requires activated venv)
make setup         # Create venv and install Python dependencies
make help          # List all available commands
```

---

## ⚖️ Pros & Cons

### `main` — NVIDIA NIM (Cloud LLM)

| | Detail |
|---|---|
| ✅ **Fast inference** | Cloud GPUs deliver responses in 1-3s vs 5-30s on CPU |
| ✅ **Large model quality** | Access to 70B+ models (Llama 3.3, Mixtral, Nemotron) that far exceed local quality |
| ✅ **Instant startup** | No model download — stack is ready in ~30 seconds |
| ✅ **Easy model switching** | Change one line in `.env`, restart the container |
| ✅ **Low resource usage** | Only 2 Docker containers, 2 GB RAM |
| ❌ **Requires API key** | Registration needed at build.nvidia.com |
| ❌ **Queries leave your machine** | Prompts and context are sent to NVIDIA's servers |
| ❌ **Free tier limits** | High volume usage may require a paid plan |
| ❌ **Internet dependency** | LLM calls fail without connectivity |

### `feature/local-llm` — Ollama (Local LLM)

| | Detail |
|---|---|
| ✅ **100% private** | No query, context, or answer ever leaves your machine |
| ✅ **No API costs** | Unlimited usage, no per-token billing |
| ✅ **No rate limits** | Both SearXNG and Ollama are self-hosted |
| ✅ **Offline after setup** | LLM works without internet once models are pulled |
| ✅ **Fully open source** | Streamlit + Ollama + SearXNG + Crawl4AI — all MIT/Apache |
| ❌ **Slow on CPU** | 5-30s per response; needs local NVIDIA GPU for real-time speed |
| ❌ **High first-run cost** | ~4.7 GB model download; not suitable for low-bandwidth setups |
| ❌ **Memory pressure** | Requires 8 GB+ RAM allocated to Docker |
| ❌ **Lower quality ceiling** | `llama3.1:8b` is strong but not 70B-class |

### Shared limitations (both branches)

| Limitation | Detail |
|---|---|
| **Crawl reliability** | JS-heavy or bot-protected pages may return empty content |
| **Niche language pages** | French/regional content scores low on English BM25 (raw markdown fallback mitigates this) |
| **Context window cap** | Context truncated at 6000 chars — very long pages lose detail |
| **SearXNG engine drift** | Search engines change HTML periodically; individual SearXNG engines occasionally break |
| **No conversation memory** | Each query is stateless — follow-up questions have no prior context |

---

## 🧠 Design Decisions

### Why SearXNG instead of calling DuckDuckGo directly?
Docker/server IPs are aggressively rate-limited (HTTP 202) by DuckDuckGo. SearXNG runs server-side with its own outbound IP and distributes requests across multiple engines simultaneously, bypassing this entirely.

### Why remove ChromaDB from the web search flow?
An earlier version used ChromaDB to embed and semantically query crawled content. For **ephemeral** web content (crawled per query, discarded after), this added 30-60s of latency and was a frequent source of `InvalidCollectionException` bugs. The replacement — `build_context_from_crawl()` — uses keyword overlap scoring: simpler, faster, zero failure modes, and embeds source URLs directly in the context string for LLM citation.

### Why BM25 with a raw markdown fallback?
BM25 is keyword-dependent. French-language or niche regional pages (e.g. Cameroonian fintech events) score near zero against English queries, making BM25 filter out all content. The raw markdown fallback ensures the pipeline always has *something* to pass to the LLM rather than silently returning empty context.

### Why `text_mode=False` in the crawler?
Many African/regional websites are JS-rendered (React, Vue). `text_mode=True` blocks JavaScript execution and returns empty HTML shells. `text_mode=False` allows Chromium to fully render pages before content extraction.

### Why does `main` use `openai` instead of a dedicated NVIDIA SDK?
NVIDIA NIM exposes an OpenAI-compatible REST API (`/v1/chat/completions`). Using the standard `openai` Python library means zero vendor lock-in — the same code can target OpenAI, Azure, NVIDIA, or any other OpenAI-compatible provider by changing `base_url` and `api_key`.

---

## 📁 Project Structure

```
.
├── app.py                    # Full pipeline — search, crawl, context, LLM
├── Dockerfile                # Streamlit app image (Python 3.11 + Playwright/Chromium)
├── docker-compose.yml        # Service orchestration (2 services on main, 4 on local-llm)
├── Makefile                  # Dev shortcuts
├── .env.example              # API key + model config template (main branch)
├── entrypoint-ollama.sh      # Ollama startup helper (feature/local-llm branch)
├── searxng/
│   └── settings.yml          # SearXNG engine config (engines, rate-limiting, formats)
└── requirements/
    ├── requirements.txt      # Runtime dependencies
    └── requirements-dev.txt  # Linting (ruff)
```

---

## ⚡️ API Usage

The Flask REST API runs on port **5005** and provides both synchronous and streaming endpoints.

### 1. Health Check
```sh
curl http://localhost:5005/health
```

### 2. Standard Query (Synchronous)
```sh
curl -X POST http://localhost:5005/ask \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "top fintech companies in Cameroon",
    "web_search": true
  }'
```

### 3. Event Extraction (JSON)
If the query is detected as an event search, it returns structured JSON matching the event schema.
```sh
curl -X POST http://localhost:5005/ask \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "upcoming tech conferences in Africa 2026",
    "web_search": true
  }'
```

### 4. Streaming Answer (SSE)
```sh
curl -N -X POST http://localhost:5005/ask/stream \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "explain blockchain",
    "web_search": false
  }'
```
