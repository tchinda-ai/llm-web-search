"""
core/search.py — web search via SearXNG.

No UI framework imports. Errors are raised as standard Python exceptions
so each client (Streamlit, Flask, CLI…) can handle them appropriately.
"""

import json
import random
import time
import urllib.parse
import urllib.request
from datetime import datetime
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

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


def check_robots_txt(urls: list[str]) -> list[str]:
    """Filters URLs that disallow crawling according to their robots.txt.

    Args:
        urls (list[str]): Candidate URLs.

    Returns:
        list[str]: Subset of URLs that are allowed to be crawled.
            If robots.txt is missing or unreadable, the URL is assumed allowed.
    """
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


def get_web_urls(search_term: str, num_results: int = 10) -> tuple[list[str], str]:
    """Searches SearXNG and returns crawlable URLs plus a snippet context string.

    The snippet context is a lightweight pre-formatted text block built from
    SearXNG result titles and summaries — it can be used directly as a fast
    context layer without needing to crawl any full pages.

    Args:
        search_term (str): The (possibly enriched) search query.
        num_results (int): Maximum number of results to return. Defaults to 10.

    Returns:
        tuple[list[str], str]:
            - List of robots.txt-allowed URLs
            - Pre-formatted snippet context string

    Raises:
        ValueError: If SearXNG returns no results for the query.
        RuntimeError: If the SearXNG request fails (network error, timeout, etc.)
    """
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

        # Throttling Safety: Random jitter (100ms - 1200ms) prevents "8-at-exact-same-millisecond"
        # bursts which usually trigger bot-detection/IP-suspensions upstream (e.g. Brave, Google)
        time.sleep(random.uniform(0.1, 1.2))

        req = urllib.request.Request(req_url, headers={"User-Agent": "llm-web-search/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())

        raw_results = [
            r for r in data.get("results", [])
            if not any(d in r.get("url", "") for d in discard_domains)
        ][:num_results]

        if not raw_results:
            raise ValueError("SearXNG returned no results for this query. Try rephrasing.")

        urls = [r["url"] for r in raw_results]
        print(f"Found {len(urls)} URLs from SearXNG")

        # Build snippet context: used as a fast first-pass context layer.
        snippet_parts = [
            f"[Source: {r['url']}]\n**{r.get('title', '')}**\n{r.get('content', '')}"
            for r in raw_results
            if r.get("content")
        ]
        snippet_context = "\n\n".join(snippet_parts)

        return check_robots_txt(urls), snippet_context

    except ValueError:
        raise
    except Exception as exc:
        raise RuntimeError(f"Failed to fetch results from the web: {exc}") from exc
