# 🔍 LLM App with Web Search

A self-hosted, privacy-first research assistant that combines real-time web search with a local large language model. Ask any question and get structured, source-cited answers synthesised from live web content — with **no external LLM API fees** and **no data leaving your infrastructure**.

> 📺 Watch the original demo video: **[YouTube →](https://youtu.be/kNgx0AifVo0)**

---

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Browser                            │
│                      http://localhost:8501                       │
└──────────────────────────────┬──────────────────────────────────┘
                               │ HTTP
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│               Streamlit App  (app container)                     │
│                                                                  │
│  1. enrich_query()     — adds year for time-sensitive queries    │
│  2. get_web_urls()     — calls SearXNG JSON API                  │
│  3. crawl_webpages()   — headless browser via crawl4ai           │
│  4. build_context()    — keyword-ranks paragraphs w/ source URLs │
│  5. call_llm()         — streams answer from Ollama              │
└────────┬──────────────────────────┬────────────────────────────-┘
         │ HTTP :8080               │ HTTP :11434
         ▼                          ▼
┌─────────────────┐      ┌──────────────────────────┐
│    SearXNG      │      │         Ollama            │
│ (searxng image) │      │   (ollama/ollama image)   │
│                 │      │                           │
│ · Google News   │      │  Model: llama3.1:8b       │
│ · Bing          │      │  (pulled by model-init    │
│ · Brave         │      │   on first run)           │
│ · DuckDuckGo    │      │                           │
│ · Wikipedia     │      └──────────────────────────┘
│                 │
│ Returns JSON:   │        ┌──────────────────────────┐
│ title+snippet   │        │      model-init          │
│ +url per result │        │  (one-shot container)    │
└─────────────────┘        │                          │
                           │  ollama pull llama3.1:8b │
                           │  exits 0 when done       │
                           └──────────────────────────┘
```

### Request Flow (step by step)

```
User enters prompt
      │
      ▼
enrich_query()        — appends current year if query is time-sensitive
      │                 e.g. "top fintech cameroon" → "top fintech cameroon 2026"
      ▼
get_web_urls()        — sends enriched query to SearXNG
      │                 returns: list[url] + snippet_context string
      ▼
check_robots_txt()    — filters out URLs that disallow crawling
      │
      ▼
crawl_webpages()      — spawns headless Chromium via crawl4ai
      │                 BM25 filters most relevant paragraphs per page
      │                 fallback: raw_markdown if BM25 returns empty
      ▼
build_context_from_crawl()
      │                 — scores paragraphs by keyword overlap with query
      │                 — prepends SearXNG snippets as fast context layer
      │                 — embeds [Source: URL] labels in each chunk
      │                 — truncates at 6000 chars
      ▼
call_llm()            — sends system_prompt + context + question to Ollama
      │                 streamed response via ollama Python client
      ▼
st.write_stream()     — renders answer token-by-token in browser
st.expander("Sources") — lists all crawled source URLs
```

---

## 🐳 Infrastructure

| Container | Image | Role | Port |
|---|---|---|---|
| `ollama` | `ollama/ollama:latest` | Serves the local LLM over HTTP | `11434` |
| `model-init` | `ollama/ollama:latest` | One-shot: pulls models on first run, then exits | — |
| `searxng` | `searxng/searxng:latest` | Self-hosted meta-search (JSON API) | `8080` |
| `llm-web-search` | Custom (Dockerfile) | Streamlit app — orchestrates the pipeline | `8501` |

### Startup order (guaranteed by Docker health checks)

```
ollama (starts)
   └─ healthy? ──► model-init (pulls llama3.1:8b) ──► exits 0
                                                           │
searxng (starts in parallel) ──► healthy?                  │
                                         └────────────────►│
                                                    app (starts)
```

### Volumes

| Volume | Purpose |
|---|---|
| `ollama_data` | Persists downloaded model weights — models survive container restarts |
| `./searxng/` | Mounted config dir — `settings.yml` controls engines and rate limiting |

---

## 📦 Dependencies

### Python (`requirements/requirements.txt`)

| Package | Version | Role |
|---|---|---|
| `streamlit` | 1.42.0 | Web UI framework — handles routing, widgets, streaming |
| `Crawl4AI` | 0.4.248 | Async headless browser crawler — extracts page content |
| `Markdown` | 3.7 | Markdown processing used internally by Crawl4AI |
| `ollama` | 0.4.7 | Python client for the Ollama REST API |

### Docker images

| Image | Version | Role |
|---|---|---|
| `python` | 3.11-slim | Base image for the app container |
| `ollama/ollama` | latest | Ollama LLM runtime + model storage |
| `searxng/searxng` | latest | Self-hosted privacy-respecting meta search |

### System dependencies (installed in Dockerfile)

Playwright/Chromium system libraries — required by Crawl4AI for headless browser rendering of JavaScript-heavy pages.

---

## ✅ Prerequisites

| Requirement | Notes |
|---|---|
| **Docker Desktop** | ≥ 4.x, with at least **8 GB RAM** allocated |
| **Disk space** | ~6 GB (llama3.1:8b model: ~4.7 GB + images) |
| **Internet access** | Required on first run to pull model weights and Docker images |

---

## 🚀 Quick Start

```sh
# 1. Clone the repo
git clone <repo-url>
cd llm-app-with-web-search-demo

# 2. Start the full stack
#    First run downloads llama3.1:8b (~4.7 GB) — grab a coffee ☕
make docker-up

# 3. Follow startup logs (watch model-init finish)
make docker-logs

# 4. Open the app
open http://localhost:8501
```

### Useful commands

```sh
make docker-up     # Build and start all services (detached)
make docker-down   # Stop and remove containers
make docker-logs   # Follow logs from all services
make run           # Run Streamlit locally (requires activated venv)
make setup         # Create venv and install dependencies
make help          # List all available commands
```

---

## ⚖️ Pros & Cons

### ✅ Pros

| Advantage | Detail |
|---|---|
| **100% private** | LLM runs locally — no query, no context, no answer ever leaves your machine |
| **No API costs** | Ollama is free; no per-token billing regardless of usage volume |
| **No rate limits** | SearXNG is self-hosted; Ollama has no request quotas |
| **Source transparency** | Every answer includes `📚 Sources` with the exact URLs used |
| **No hallucination on facts** | System prompt instructs the model to cite sources and not fabricate |
| **Resilient search** | SearXNG queries 5 engines simultaneously; one failing doesn't break results |
| **Offline after setup** | Once models are pulled, the LLM works without internet |
| **Fully open source** | Streamlit, Ollama, SearXNG, Crawl4AI — all MIT/Apache licensed |

### ❌ Cons

| Limitation | Detail |
|---|---|
| **LLM quality ceiling** | `llama3.1:8b` is good but not GPT-4/Gemini-class. Complex reasoning degrades on very hard questions |
| **Inference speed** | CPU inference is slow — 5-30s per response depending on hardware. Needs NVIDIA GPU for real-time feel |
| **High first-run cost** | ~4.7 GB model download + image layers — not suitable for low-bandwidth environments |
| **Memory pressure** | Requires 8+ GB RAM allocated to Docker. May cause slowdowns on constrained machines |
| **Crawl reliability** | JavaScript-heavy / bot-protected pages may return empty content. Niche/French-language pages can score low on BM25 |
| **Context window limits** | Context is capped at 6000 chars — very long pages lose information. llama3.1:8b has 128k context but inference time grows |
| **SearXNG engine drift** | Search engines change HTML structure frequently — individual SearXNG engines occasionally break (Google engine was disabled for this reason) |
| **No conversation memory** | Each query is stateless — follow-up questions have no history of prior answers |

---

## 🧠 Design Decisions

### Why SearXNG instead of DuckDuckGo directly?
Docker/server IP addresses are aggressively rate-limited (HTTP 202) by DuckDuckGo's API. SearXNG runs with its own outbound IP and distributes requests across multiple engines, effectively bypassing this.

### Why remove ChromaDB from the web search flow?
ChromaDB was used to embed crawled content and query it semantically. For **ephemeral** web content (crawled per query, discarded after), this adds latency and complexity with no benefit. `build_context_from_crawl()` uses simple keyword overlap scoring instead — faster, fewer failure points, and embeds source URLs directly in the context string for citation.

### Why BM25 + raw markdown fallback?
BM25 is fast and cheap but keyword-dependent. For French-language or niche regional pages (e.g. Cameroonian fintech events), English keywords score near zero and BM25 returns empty. The raw markdown fallback ensures we always have *something* to send to the LLM rather than silently returning no context.

### Why `text_mode=False` in the crawler?
Many African/regional websites are JavaScript-rendered (React, Vue). `text_mode=True` blocks JS execution and returns empty content. `text_mode=False` allows Chromium to fully render the page before extraction.

---

## 🔀 Branches

| Branch | LLM Backend | Notes |
|---|---|---|
| `feature/local-llm` | Ollama (local) | This branch — fully self-hosted, private, no API keys |
| `main` | NVIDIA NIM (cloud) | Cloud inference — faster, larger models, requires API key |

---

## 📁 Project Structure

```
.
├── app.py                    # Main application — full pipeline
├── Dockerfile                # Streamlit app image
├── docker-compose.yml        # 4-service orchestration
├── Makefile                  # Dev shortcuts (setup, run, docker-up…)
├── entrypoint-ollama.sh      # (Legacy) Ollama startup script
├── searxng/
│   └── settings.yml          # SearXNG engine config
└── requirements/
    ├── requirements.txt      # Runtime dependencies
    └── requirements-dev.txt  # Linting (ruff)
```
