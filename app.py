"""
LLM App with Web Search
"""

import asyncio
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

# NVIDIA NIM API configuration (OpenAI-compatible endpoint)
NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY", "")
NVIDIA_MODEL = os.environ.get("NVIDIA_MODEL", "meta/llama-3.3-70b-instruct")
# Self-hosted SearXNG instance (avoids DDG rate limits from Docker IPs)
SEARXNG_URL = os.environ.get("SEARXNG_URL", "http://localhost:8080")

from openai import OpenAI
import streamlit as st
from crawl4ai import AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerRunConfig
from crawl4ai.content_filter_strategy import BM25ContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from crawl4ai.models import CrawlResult

system_prompt = """
You are a research assistant with real-time web search access. You receive web search results as context.

Your task:
1. Synthesize the provided context to answer the question accurately and completely.
2. Supplement with your own knowledge where the context has gaps, but clearly prefer the context for current facts.
3. Always cite your sources using [Source: URL] inline when a specific fact comes from the context.
4. If the context contains no relevant information at all, say so briefly, then answer from your knowledge with a disclaimer that the information may not be current.
5. Structure your response clearly: use headings, bullet points, and tables where appropriate.
6. For time-sensitive queries (events, prices, news), note that your context reflects the web results at query time.

Context will be passed as "Context:" (text chunks with [Source: URL] labels)
Question will be passed as "Question:"

Do NOT fabricate specific facts (names, dates, amounts, company names) that are not in the context or your verified training data.
"""


def call_llm(prompt: str, with_context: bool = True, context: str | None = None):
    """Calls the NVIDIA NIM cloud LLM via OpenAI-compatible API.

    The model and API key are configured via environment variables:
        NVIDIA_API_KEY  — your NVIDIA NIM API key
        NVIDIA_MODEL    — model identifier (default: meta/llama-3.3-70b-instruct)

    Args:
        prompt (str): The user prompt/question to send to the LLM
        with_context (bool, optional): Whether to include system context. Defaults to True.
        context (str | None, optional): Additional context to provide to the LLM. Defaults to None.

    Yields:
        str: Generated text chunks from the LLM response stream
    """
    if not NVIDIA_API_KEY:
        yield "❌ NVIDIA_API_KEY is not set. Add it to your .env file."
        return

    if with_context:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {prompt}"},
        ]
    else:
        messages = [{"role": "user", "content": prompt}]

    client = OpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=NVIDIA_API_KEY,
    )

    response = client.chat.completions.create(
        model=NVIDIA_MODEL,
        messages=messages,
        temperature=0.2,
        top_p=0.7,
        max_tokens=1024,
        stream=True,
    )

    for chunk in response:
        if chunk.choices and chunk.choices[0].delta.content is not None:
            yield chunk.choices[0].delta.content


def enrich_query(prompt: str) -> str:
    """Adds temporal context to time-sensitive search queries.

    Appends the current year when the query looks time-sensitive (events, news,
    top lists, etc.) so search engines return fresh results rather than old pages.

    Args:
        prompt (str): The original user query.

    Returns:
        str: The enriched query.
    """
    year = datetime.now().year
    time_keywords = [
        "latest", "upcoming", "current", "top", "best", "new",
        "events", "news", "recently", "this year", "2024", "2025", "2026",
    ]
    if any(kw in prompt.lower() for kw in time_keywords):
        return f"{prompt} {year}"
    return prompt


def normalize_url(url: str) -> str:
    """Normalizes a URL into a safe string for use as a ChromaDB document ID.

    Args:
        url (str): The URL to normalize.

    Returns:
        str: Normalized URL with special characters replaced by underscores.

    Example:
        >>> normalize_url("https://www.example.com/path")
        "example_com_path"
    """
    return (
        url.replace("https://", "")
        .replace("http://", "")
        .replace("www.", "")
        .replace("/", "_")
        .replace("-", "_")
        .replace(".", "_")
    )


def build_context_from_crawl(
    results: list[CrawlResult],
    prompt: str,
    snippet_context: str = "",
    max_chars: int = 6000,
) -> tuple[str, list[str]]:
    """Assembles ranked context directly from crawl results — no vector DB needed.

    Scores each paragraph by keyword overlap with the query, then concatenates
    the top chunks up to max_chars. Source URLs are embedded in the context
    string so the LLM can cite them inline.

    Args:
        results (list[CrawlResult]): Crawled page results.
        prompt (str): The original user query (used for keyword ranking).
        snippet_context (str): Pre-formatted SearXNG snippet context to prepend.
        max_chars (int): Maximum total characters to include in context.

    Returns:
        tuple[str, list[str]]: (context_string, list_of_source_urls)
    """
    query_words = set(prompt.lower().split())
    scored_chunks: list[tuple[int, str, str]] = []

    for result in results:
        if not result.markdown_v2:
            continue

        # Prefer BM25-filtered content; fall back to raw markdown when the
        # filter strips everything (common for French-language/niche pages).
        text = result.markdown_v2.fit_markdown
        if not text or not text.strip():
            text = result.markdown_v2.raw_markdown
            if not text or not text.strip():
                print(f"No content extracted from {result.url}")
                continue

        paragraphs = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 80]
        for para in paragraphs:
            words = set(para.lower().split())
            overlap = len(words & query_words)
            scored_chunks.append((overlap, para, result.url))

    # Sort by relevance, highest keyword overlap first
    scored_chunks.sort(key=lambda x: x[0], reverse=True)

    context_parts: list[str] = []
    sources: list[str] = []
    total_chars = 0

    # Prepend SearXNG snippets as a lightweight fast-context layer
    if snippet_context:
        context_parts.append(f"## Search Result Summaries\n{snippet_context}")
        total_chars += len(snippet_context)

    context_parts.append("## Crawled Page Content")
    for _score, chunk, url in scored_chunks:
        if total_chars + len(chunk) > max_chars:
            break
        context_parts.append(f"[Source: {url}]\n{chunk}")
        if url not in sources:
            sources.append(url)
        total_chars += len(chunk)

    return "\n\n---\n\n".join(context_parts), sources


async def crawl_webpages(urls: list[str], prompt: str) -> list[CrawlResult]:
    """Asynchronously crawls multiple webpages and extracts relevant content.

    Args:
        urls (list[str]): List of URLs to crawl.
        prompt (str): Query text used for BM25 content filtering.

    Returns:
        list[CrawlResult]: Crawl results with extracted markdown content.

    Note:
        - BM25 threshold is kept low (0.5) for niche/non-English pages.
        - text_mode=False allows JavaScript to execute, which is critical for
          JS-rendered regional/African sites.
        - <a> tags are kept (unlike original) so event titles/links are retained.
    """
    bm25_filter = BM25ContentFilter(user_query=prompt, bm25_threshold=0.5)
    md_generator = DefaultMarkdownGenerator(content_filter=bm25_filter)

    crawler_config = CrawlerRunConfig(
        markdown_generator=md_generator,
        # Keep <a> tags — event pages link from their titles/dates
        excluded_tags=["nav", "footer", "header", "form", "img"],
        only_text=True,
        exclude_social_media_links=True,
        keep_data_attributes=False,
        cache_mode=CacheMode.BYPASS,
        remove_overlay_elements=True,
        word_count_threshold=30,  # skip very short blocks (ads, nav breadcrumbs)
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
        page_timeout=30000,  # 30s (up from 20s) for JS-heavy regional sites
    )
    # text_mode=False allows JavaScript to execute — critical for JS-rendered sites
    browser_config = BrowserConfig(headless=True, text_mode=False, light_mode=True)

    async with AsyncWebCrawler(config=browser_config) as crawler:
        results = await crawler.arun_many(urls, config=crawler_config)
        print(f"Crawled {len(results)} pages")
        return results


def check_robots_txt(urls: list[str]) -> list[str]:
    """Checks robots.txt files to determine which URLs are allowed to be crawled.

    Args:
        urls (list[str]): List of URLs to check against their robots.txt files.

    Returns:
        list[str]: List of URLs that are allowed to be crawled. If robots.txt
            is missing or there's an error, the URL is assumed to be allowed.
    """
    allowed_urls = []
    for url in urls:
        try:
            robots_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}/robots.txt"
            rp = RobotFileParser(robots_url)
            rp.read()
            if rp.can_fetch("*", url):
                allowed_urls.append(url)
        except Exception:
            # If robots.txt is missing or there's any error, assume URL is allowed
            allowed_urls.append(url)
    return allowed_urls


def get_web_urls(search_term: str, num_results: int = 10) -> tuple[list[str], str]:
    """Performs a web search via SearXNG and returns URLs plus snippet context.

    Queries the self-hosted SearXNG JSON API which aggregates results from
    multiple engines (Google, Bing, Brave, DDG), bypassing direct rate-limit
    issues from Docker IPs.

    Args:
        search_term (str): The (possibly enriched) search query.
        num_results (int, optional): Maximum number of results to return. Defaults to 10.

    Returns:
        tuple[list[str], str]:
            - List of crawlable URLs (robots.txt filtered)
            - snippet_context: pre-formatted string of titles+summaries from
              SearXNG — used as a fast lightweight context layer without crawling.
    """
    discard_domains = ["youtube.com", "britannica.com", "vimeo.com"]

    try:
        params = urllib.parse.urlencode({
            "q": search_term,
            "format": "json",
            "language": "en-US",
            "engines": "google,bing,brave,duckduckgo",
        })
        url = f"{SEARXNG_URL}/search?{params}"
        print(f"Querying SearXNG: {url}")

        req = urllib.request.Request(url, headers={"User-Agent": "llm-web-search/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())

        raw_results = [
            r for r in data.get("results", [])
            if not any(d in r.get("url", "") for d in discard_domains)
        ][:num_results]

        if not raw_results:
            st.warning("SearXNG returned no results. Try a different query.")
            st.stop()

        urls = [r["url"] for r in raw_results]
        print(f"Found {len(urls)} URLs from SearXNG")

        # Build snippet context from titles + summaries (fast, no crawling needed).
        # This gives the LLM a quick overview even if some pages fail to crawl.
        snippet_parts = [
            f"[Source: {r['url']}]\n**{r.get('title', '')}**\n{r.get('content', '')}"
            for r in raw_results
            if r.get("content")
        ]
        snippet_context = "\n\n".join(snippet_parts)

        return check_robots_txt(urls), snippet_context

    except Exception as e:
        error_msg = ("❌ Failed to fetch results from the web", str(e))
        print(error_msg)
        st.write(error_msg)
        st.stop()


async def run():
    st.set_page_config(page_title="LLM with Web Search")

    # Sidebar — model info and config
    with st.sidebar:
        st.markdown("### ⚙️ Configuration")
        st.markdown(f"**Model:** `{NVIDIA_MODEL}`")
        st.markdown(f"**Provider:** NVIDIA NIM")
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
            # Enrich query with temporal context for time-sensitive questions
            enriched_query = enrich_query(prompt)
            if enriched_query != prompt:
                print(f"Query enriched: '{prompt}' → '{enriched_query}'")

            web_urls, snippet_context = get_web_urls(search_term=enriched_query)
            if not web_urls:
                st.write("No results found.")
                st.stop()

            with st.spinner("🔍 Crawling web pages..."):
                crawl_results = await crawl_webpages(urls=web_urls, prompt=prompt)

            context, sources = build_context_from_crawl(
                results=crawl_results,
                prompt=prompt,
                snippet_context=snippet_context,
            )

            print(f"Context assembled from {len(sources)} crawled sources")

            llm_response = call_llm(context=context, prompt=prompt, with_context=True)
            st.write_stream(llm_response)

            # Show sources at the bottom
            if sources:
                with st.expander("📚 Sources"):
                    for src in sources:
                        st.markdown(f"- [{src}]({src})")
        else:
            llm_response = call_llm(prompt=prompt, with_context=False)
            st.write_stream(llm_response)


if __name__ == "__main__":
    asyncio.run(run())
