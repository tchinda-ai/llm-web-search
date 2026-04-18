# Graph Report - .  (2026-04-18)

## Corpus Check
- Corpus is ~5,172 words - fits in a single context window. You may not need a graph.

## Summary
- 55 nodes · 71 edges · 8 communities detected
- Extraction: 72% EXTRACTED · 28% INFERRED · 0% AMBIGUOUS · INFERRED: 20 edges (avg confidence: 0.82)
- Token cost: 1,200 input · 800 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Flask REST API Service|Flask REST API Service]]
- [[_COMMUNITY_Search Engine Client|Search Engine Client]]
- [[_COMMUNITY_NVIDIA NIM LLM Client|NVIDIA NIM LLM Client]]
- [[_COMMUNITY_Web Crawler Engine|Web Crawler Engine]]
- [[_COMMUNITY_Project Architecture & Design Intent|Project Architecture & Design Intent]]
- [[_COMMUNITY_Streamlit Frontend Application|Streamlit Frontend Application]]
- [[_COMMUNITY_Cloud API Integration Rationale|Cloud API Integration Rationale]]
- [[_COMMUNITY_Core Module Initialization|Core Module Initialization]]

## God Nodes (most connected - your core abstractions)
1. `run()` - 10 edges
2. `_run_pipeline()` - 9 edges
3. `ask()` - 6 edges
4. `is_event_query()` - 5 edges
5. `call_llm()` - 5 edges
6. `extract_events()` - 5 edges
7. `get_web_urls()` - 5 edges
8. `Web Search & Context Pipeline` - 5 edges
9. `ask_stream()` - 4 edges
10. `_nvidia_client()` - 4 edges

## Surprising Connections (you probably didn't know these)
- `Streamlit UI Orchestrator` --implements--> `Web Search & Context Pipeline`  [INFERRED]
  app.py → README.md
- `Flask REST API Client` --implements--> `Web Search & Context Pipeline`  [INFERRED]
  api.py → README.md
- `Structured Event Extraction` --conceptually_related_to--> `Research Assistant Architecture`  [INFERRED]
  core/llm.py → README.md
- `Rationale: SearXNG Rate-Limit Bypass` --rationale_for--> `Web Search & Context Pipeline`  [EXTRACTED]
  core/search.py → README.md
- `Rationale: JavaScript-Heavy Rendering` --rationale_for--> `Web Search & Context Pipeline`  [EXTRACTED]
  core/crawler.py → README.md

## Hyperedges (group relationships)
- **Core Orchestration Flow** — app_streamlit_orchestrator, api_flask_rest_api, readme_web_search_pipeline [INFERRED 0.90]

## Communities

### Community 0 - "Flask REST API Service"
Cohesion: 0.21
Nodes (11): ask(), ask_stream(), health(), api.py — Flask REST API client.  Exposes the same business logic as app.py (Stre, Streaming ask endpoint — returns a Server-Sent Events (SSE) stream.      Only av, Runs the full web search → crawl → context pipeline.      Shared by /ask and /as, Health check — returns service status and configuration summary.      Response 2, Synchronous ask endpoint — returns a complete JSON response.      The response s (+3 more)

### Community 1 - "Search Engine Client"
Cohesion: 0.22
Nodes (8): core/config.py — centralised environment variable resolution.  Imported by every, check_robots_txt(), enrich_query(), get_web_urls(), core/search.py — web search via SearXNG.  No UI framework imports. Errors are ra, Appends the current year to time-sensitive queries.      Ensures search engines, Filters URLs that disallow crawling according to their robots.txt.      Args:, Searches SearXNG and returns crawlable URLs plus a snippet context string.

### Community 2 - "NVIDIA NIM LLM Client"
Cohesion: 0.24
Nodes (8): call_llm(), extract_events(), _nvidia_client(), core/llm.py — LLM interaction via NVIDIA NIM (OpenAI-compatible API).  No UI fra, Returns an OpenAI client pointed at the NVIDIA NIM endpoint., Streams an LLM answer via NVIDIA NIM.      Args:         prompt (str): The user, Extracts structured event data from context using the event system prompt., core/prompts.py — LLM system prompts.  Kept in their own module so both the stan

### Community 3 - "Web Crawler Engine"
Cohesion: 0.25
Nodes (7): build_context_from_crawl(), crawl_webpages(), normalize_url(), core/crawler.py — async web crawling and context assembly.  No UI framework impo, Assembles a ranked context string directly from crawl results.      Scores each, Normalises a URL into a safe string (used as a document identifier).      Args:, Asynchronously crawls multiple pages and extracts relevant content.      Uses BM

### Community 4 - "Project Architecture & Design Intent"
Cohesion: 0.33
Nodes (7): Flask REST API Client, Streamlit UI Orchestrator, Rationale: JavaScript-Heavy Rendering, Structured Event Extraction, Research Assistant Architecture, Web Search & Context Pipeline, Rationale: SearXNG Rate-Limit Bypass

### Community 5 - "Streamlit Frontend Application"
Cohesion: 0.5
Nodes (4): app.py — Streamlit UI client.  Responsible only for rendering. All business logi, Renders extracted events as Streamlit cards with a JSON download button.      Th, render_events(), run()

### Community 6 - "Cloud API Integration Rationale"
Cohesion: 1.0
Nodes (2): Rationale: OpenAI Client Compatibility, NVIDIA NIM Cloud API Integration

### Community 7 - "Core Module Initialization"
Cohesion: 1.0
Nodes (0): 

## Knowledge Gaps
- **27 isolated node(s):** `api.py — Flask REST API client.  Exposes the same business logic as app.py (Stre`, `Runs the full web search → crawl → context pipeline.      Shared by /ask and /as`, `Health check — returns service status and configuration summary.      Response 2`, `Synchronous ask endpoint — returns a complete JSON response.      The response s`, `Streaming ask endpoint — returns a Server-Sent Events (SSE) stream.      Only av` (+22 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Cloud API Integration Rationale`** (2 nodes): `Rationale: OpenAI Client Compatibility`, `NVIDIA NIM Cloud API Integration`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Core Module Initialization`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `run()` connect `Streamlit Frontend Application` to `Flask REST API Service`, `Search Engine Client`, `NVIDIA NIM LLM Client`, `Web Crawler Engine`?**
  _High betweenness centrality (0.270) - this node is a cross-community bridge._
- **Why does `_run_pipeline()` connect `Flask REST API Service` to `Search Engine Client`, `Web Crawler Engine`, `Streamlit Frontend Application`?**
  _High betweenness centrality (0.171) - this node is a cross-community bridge._
- **Why does `get_web_urls()` connect `Search Engine Client` to `Flask REST API Service`, `Streamlit Frontend Application`?**
  _High betweenness centrality (0.098) - this node is a cross-community bridge._
- **Are the 8 inferred relationships involving `run()` (e.g. with `_run_pipeline()` and `enrich_query()`) actually correct?**
  _`run()` has 8 INFERRED edges - model-reasoned connections that need verification._
- **Are the 5 inferred relationships involving `_run_pipeline()` (e.g. with `enrich_query()` and `get_web_urls()`) actually correct?**
  _`_run_pipeline()` has 5 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `ask()` (e.g. with `is_event_query()` and `extract_events()`) actually correct?**
  _`ask()` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `is_event_query()` (e.g. with `ask()` and `ask_stream()`) actually correct?**
  _`is_event_query()` has 3 INFERRED edges - model-reasoned connections that need verification._