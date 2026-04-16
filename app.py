"""
app.py — Streamlit UI client.

Responsible only for rendering. All business logic lives in core/.
This file has zero knowledge of api.py — both clients are fully independent.
"""

import asyncio
import json

import streamlit as st

from core.config import NVIDIA_API_KEY, NVIDIA_MODEL
from core.crawler import build_context_from_crawl, crawl_webpages
from core.llm import call_llm, extract_events, is_event_query
from core.search import enrich_query, get_web_urls


# ── Streamlit-specific rendering ───────────────────────────────────────────────

def render_events(events_data: dict) -> None:
    """Renders extracted events as Streamlit cards with a JSON download button.

    This is the only function in this file that contains display logic specific
    to the event pipeline — everything else delegates to core/.

    Args:
        events_data (dict): Parsed event payload with an "events" key.
    """
    events = events_data.get("events", [])
    error = events_data.get("error")

    if error:
        st.error(f"⚠️ Extraction error: {error}")

    if not events:
        st.info("No events with confirmed dates were found in the search results.")
        return

    st.success(f"Found **{len(events)}** event(s)")

    for ev in events:
        title       = ev.get("title", "Untitled Event")
        starts      = ev.get("starts_at_raw", "Date unknown")
        ends        = ev.get("ends_at_raw")
        location    = ev.get("location_raw") or ev.get("city") or "Location unknown"
        description = ev.get("description", "")
        url         = ev.get("url", "")
        tags        = ev.get("tags", [])
        is_online   = ev.get("is_online", False)
        confidence  = ev.get("confidence", 0)

        with st.container(border=True):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"### {title}")
                date_str = f"📅 {starts}"
                if ends:
                    date_str += f" → {ends}"
                st.markdown(date_str)
                st.markdown(f"📍 {'🌐 Online' if is_online else location}")
            with col2:
                st.metric("Confidence", f"{confidence:.0%}")

            if description:
                st.markdown(description)
            if tags:
                st.markdown(" ".join(f"`{t}`" for t in tags))
            if url:
                st.markdown(f"[🔗 Event page]({url})")

    # Raw JSON block — for downstream consumption
    with st.expander("⬇️ Raw JSON (for downstream use)"):
        json_str = json.dumps(events_data, indent=2, ensure_ascii=False)
        st.code(json_str, language="json")
        st.download_button(
            label="Download events.json",
            data=json_str,
            file_name="events.json",
            mime="application/json",
        )


# ── Main Streamlit entry point ─────────────────────────────────────────────────

async def run() -> None:
    st.set_page_config(page_title="LLM with Web Search")

    # Sidebar — model info
    with st.sidebar:
        st.markdown("### ⚙️ Configuration")
        st.markdown(f"**Model:** `{NVIDIA_MODEL}`")
        st.markdown("**Provider:** NVIDIA NIM")
        if not NVIDIA_API_KEY:
            st.error("⚠️ NVIDIA_API_KEY not set")
        else:
            st.success("✅ API key configured")

    st.header("🔍 LLM Web Search")
    prompt = st.text_area(
        label="Put your query here",
        placeholder="Add your query...",
        label_visibility="hidden",
    )
    is_web_search = st.toggle("Enable web search", value=False, key="enable_web_search")
    go = st.button("⚡️ Go")

    if prompt and go:
        if is_web_search:
            enriched_query = enrich_query(prompt)
            if enriched_query != prompt:
                print(f"Query enriched: '{prompt}' → '{enriched_query}'")

            try:
                web_urls, snippet_context = get_web_urls(search_term=enriched_query)
            except ValueError as exc:
                st.warning(str(exc))
                st.stop()
            except RuntimeError as exc:
                st.error(str(exc))
                st.stop()

            with st.spinner("🔍 Crawling web pages..."):
                crawl_results = await crawl_webpages(urls=web_urls, prompt=prompt)

            context, sources = build_context_from_crawl(
                results=crawl_results,
                prompt=prompt,
                snippet_context=snippet_context,
            )
            print(f"Context assembled from {len(sources)} crawled sources")

            if is_event_query(prompt):
                # ── Event mode: structured JSON extraction ─────────────────
                with st.spinner("📅 Extracting events..."):
                    events_data = extract_events(context=context, prompt=prompt)
                render_events(events_data)
            else:
                # ── Standard mode: streaming natural-language answer ────────
                st.write_stream(call_llm(context=context, prompt=prompt, with_context=True))

            # Sources expander — shown in both modes
            if sources:
                with st.expander("📚 Sources"):
                    for src in sources:
                        st.markdown(f"- [{src}]({src})")
        else:
            st.write_stream(call_llm(prompt=prompt, with_context=False))


if __name__ == "__main__":
    asyncio.run(run())
