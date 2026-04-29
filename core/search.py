"""
core/search.py — web search via SearXNG.

No UI framework imports. Errors are raised as standard Python exceptions
so each client (Streamlit, Flask, CLI…) can handle them appropriately.
"""

import asyncio
import json
import random
import time
import urllib.parse
from datetime import datetime
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import aiohttp

from .config import SEARXNG_URL


def enrich_query(prompt: str) -> str:
    """Appends the current year to time-sensitive queries.

    Ensures search engines return fresh results rather than old pages when
    the user asks about events, news, top lists, etc.

    Args:
        prompt (str): The original user query.

    Returns:
        str: The enriched query (unchanged if no time-sensitive keyword found).
    """
    year = datetime.now().year
    time_keywords = [
        "latest", "upcoming", "current", "top", "best", "new",
        "events", "news", "recently", "this year", "2024", "2025", "2026",
    ]
    if any(kw in prompt.lower() for kw in time_keywords):
        return f"{prompt} {year}"
    return prompt


def _check_robots_txt_sync(urls: list[str]) -> list[str]:
    """Filters URLs that disallow crawling according to their robots.txt (Synchronous)."""
    allowed: list[str] = []
    for url in urls:
        try:
            robots_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}/robots.txt"
            rp = RobotFileParser(robots_url)
            rp.read()
            if rp.can_fetch("*", url):
                allowed.append(url)
        except Exception:
            allowed.append(url)
    return allowed


async def check_robots_txt(urls: list[str]) -> list[str]:
    """Asynchronous wrapper around robots.txt checker."""
    return await asyncio.to_thread(_check_robots_txt_sync, urls)


async def get_web_urls(search_term: str, session: aiohttp.ClientSession, num_results: int = 10) -> tuple[list[str], str]:
    """Searches SearXNG and returns crawlable URLs plus a snippet context string."""
    discard_domains = ["youtube.com", "britannica.com", "vimeo.com"]

    try:
        params = urllib.parse.urlencode({
            "q": search_term,
            "format": "json",
            "language": "en-US",
            "engines": "google,bing,brave,duckduckgo",
        })
        req_url = f"{SEARXNG_URL}/search?{params}"
        print(f"Querying SearXNG: {req_url}")

        # Throttling Safety: Random jitter (100ms - 1200ms)
        await asyncio.sleep(random.uniform(0.1, 1.2))

        async with session.get(req_url, headers={"User-Agent": "llm-web-search/1.0"}, timeout=15) as resp:
            resp.raise_for_status()
            data = await resp.json()

        raw_results = [
            r for r in data.get("results", [])
            if not any(d in r.get("url", "") for d in discard_domains)
        ][:num_results]

        if not raw_results:
            raise ValueError("SearXNG returned no results for this query. Try rephrasing.")

        urls = [r["url"] for r in raw_results]
        print(f"Found {len(urls)} URLs from SearXNG for query: {search_term}")

        snippet_parts = [
            f"[Source: {r['url']}]\n**{r.get('title', '')}**\n{r.get('content', '')}"
            for r in raw_results
            if r.get("content")
        ]
        snippet_context = "\n\n".join(snippet_parts)

        allowed_urls = await check_robots_txt(urls)
        return allowed_urls, snippet_context

    except ValueError:
        raise
    except Exception as exc:
        raise RuntimeError(f"Failed to fetch results from the web: {exc}") from exc


async def get_web_urls_multi(queries: list[str], max_results_per_query: int = 5) -> tuple[list[str], str]:
    """Executes multiple queries against SearXNG concurrently and aggregates the results."""
    all_urls = []
    seen_urls = set()
    all_snippets = []
    
    semaphore = asyncio.Semaphore(3)

    async def fetch(query: str, session: aiohttp.ClientSession):
        async with semaphore:
            try:
                urls, snippet = await get_web_urls(search_term=query, session=session, num_results=max_results_per_query)
                return query, urls, snippet
            except ValueError:
                print(f"SearXNG returned no results for query variant: {query}")
                return query, [], ""
            except Exception as exc:
                print(f"Error fetching variant '{query}': {exc}")
                return query, [], ""

    async with aiohttp.ClientSession() as session:
        tasks = [fetch(q, session) for q in queries]
        results = await asyncio.gather(*tasks)

    for query, urls, snippet in results:
        for url in urls:
            if url not in seen_urls:
                seen_urls.add(url)
                all_urls.append(url)
        if snippet:
            all_snippets.append(f"--- Results for: {query} ---\n{snippet}")

    if not all_urls:
        raise ValueError("SearXNG returned no results for any of the queries.")

    return all_urls, "\n\n".join(all_snippets)
