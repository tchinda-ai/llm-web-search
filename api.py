"""
api.py — Flask REST API client.

Exposes the same business logic as app.py (Streamlit) through HTTP endpoints.
This file has zero knowledge of app.py — both clients are fully independent.
Both import from core/, but never from each other.

Endpoints
─────────
GET  /health          Health check + config status
POST /ask             Synchronous answer (standard or event mode)
POST /ask/stream      Streaming answer via Server-Sent Events (standard mode only)

Usage
─────
    python api.py                    # development server on :5000
    gunicorn api:flask_app -w 2      # production
"""

import asyncio
import json
from typing import Generator

from flask import Flask, Response, jsonify, request, stream_with_context

from core.config import NVIDIA_API_KEY, NVIDIA_MODEL, SEARXNG_URL
from core.crawler import build_context_from_crawl, crawl_webpages
from core.llm import call_llm, extract_events, is_event_query
from core.search import enrich_query, get_web_urls

flask_app = Flask(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _run_pipeline(prompt: str) -> tuple[str, list[str]]:
    """Runs the full web search → crawl → context pipeline.

    Shared by /ask and /ask/stream. Returns assembled context and source URLs.

    Args:
        prompt (str): The user query (not yet enriched).

    Returns:
        tuple[str, list[str]]: (context_string, source_urls)

    Raises:
        ValueError: No results from SearXNG.
        RuntimeError: SearXNG network/timeout error.
    """
    enriched = enrich_query(prompt)
    urls, snippet_context = get_web_urls(search_term=enriched)  # may raise
    crawl_results = asyncio.run(crawl_webpages(urls=urls, prompt=prompt))
    context, sources = build_context_from_crawl(
        results=crawl_results,
        prompt=prompt,
        snippet_context=snippet_context,
    )
    return context, sources


# ── Routes ─────────────────────────────────────────────────────────────────────

@flask_app.get("/health")
def health():
    """Health check — returns service status and configuration summary.

    Response 200:
        {
            "status": "ok",
            "model": "meta/llama-3.3-70b-instruct",
            "searxng_url": "http://searxng:8080",
            "api_key_configured": true
        }
    """
    return jsonify({
        "status": "ok",
        "model": NVIDIA_MODEL,
        "searxng_url": SEARXNG_URL,
        "api_key_configured": bool(NVIDIA_API_KEY),
    })


@flask_app.post("/ask")
def ask():
    """Synchronous ask endpoint — returns a complete JSON response.

    The response shape depends on whether the query is event-related:

    Standard query response:
        {
            "type": "answer",
            "answer": "...",
            "sources": ["https://..."]
        }

    Event query response:
        {
            "type": "events",
            "events": [ { ...GeminiEventRaw schema... } ],
            "sources": ["https://..."]
        }

    Request body (JSON):
        {
            "prompt":     "top fintech companies in Cameron",  -- required
            "web_search": true                                  -- optional, default false
        }

    Error responses:
        400  prompt missing or empty
        503  NVIDIA_API_KEY not configured
        404  SearXNG returned no results
        502  SearXNG network/timeout error
    """
    body = request.get_json(force=True, silent=True) or {}
    prompt: str = body.get("prompt", "").strip()
    web_search: bool = body.get("web_search", False)

    if not prompt:
        return jsonify({"error": "prompt is required"}), 400

    if not NVIDIA_API_KEY:
        return jsonify({"error": "NVIDIA_API_KEY is not configured on the server"}), 503

    sources: list[str] = []
    context: str | None = None

    if web_search:
        try:
            context, sources = _run_pipeline(prompt)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 404
        except RuntimeError as exc:
            return jsonify({"error": str(exc)}), 502

        if is_event_query(prompt):
            events_data = extract_events(context=context, prompt=prompt)
            return jsonify({
                "type": "events",
                "events": events_data.get("events", []),
                "sources": sources,
                **({"error": events_data["error"]} if "error" in events_data else {}),
            })

        # Standard query — collect streaming generator into a single string
        answer = "".join(call_llm(context=context, prompt=prompt, with_context=True))
        return jsonify({"type": "answer", "answer": answer, "sources": sources})

    # No web search — plain LLM call
    answer = "".join(call_llm(prompt=prompt, with_context=False))
    return jsonify({"type": "answer", "answer": answer, "sources": []})


@flask_app.post("/ask/stream")
def ask_stream():
    """Streaming ask endpoint — returns a Server-Sent Events (SSE) stream.

    Only available for standard (non-event) queries. Event queries require
    the complete JSON response — use POST /ask for those.

    The stream emits lines in SSE format:
        data: <token>\\n\\n

    A final sentinel event signals completion:
        event: done
        data: {"sources": [...]}\\n\\n

    Request body (JSON):
        {
            "prompt":     "...",   -- required
            "web_search": true     -- optional, default false
        }

    Error responses (non-SSE, returned before stream starts):
        400  prompt missing or empty
        503  NVIDIA_API_KEY not configured
        404  SearXNG returned no results
        502  SearXNG network/timeout error
        422  Event query detected — use POST /ask instead
    """
    body = request.get_json(force=True, silent=True) or {}
    prompt: str = body.get("prompt", "").strip()
    web_search: bool = body.get("web_search", False)

    if not prompt:
        return jsonify({"error": "prompt is required"}), 400

    if not NVIDIA_API_KEY:
        return jsonify({"error": "NVIDIA_API_KEY is not configured on the server"}), 503

    sources: list[str] = []
    context: str | None = None

    if web_search:
        if is_event_query(prompt):
            return jsonify({
                "error": "Event queries return structured JSON — use POST /ask instead."
            }), 422

        try:
            context, sources = _run_pipeline(prompt)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 404
        except RuntimeError as exc:
            return jsonify({"error": str(exc)}), 502

    def _sse_generator() -> Generator[str, None, None]:
        token_stream = (
            call_llm(context=context, prompt=prompt, with_context=bool(context))
        )
        for token in token_stream:
            # SSE format: each message is "data: <payload>\n\n"
            yield f"data: {json.dumps(token)}\n\n"

        # Sentinel event carrying metadata
        yield f"event: done\ndata: {json.dumps({'sources': sources})}\n\n"

    return Response(
        stream_with_context(_sse_generator()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # disable nginx buffering
        },
    )


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    flask_app.run(host="0.0.0.0", port=5005, debug=False)
