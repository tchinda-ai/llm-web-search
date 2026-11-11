"""
core/search.py — web search via SearXNG.

No UI framework imports. Errors are raised as standard Python exceptions
so each client (Streamlit, Flask, CLI…) can handle them appropriately.
"""

import json
import random
import socket
import time
import urllib.parse
import urllib.request
from datetime import datetime
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

from .config import SEARXNG_URL


def enrich_query(prompt: str) -> str:
    """Appends the current year to time-sensitive queries only if a year isn't already present.

    Ensures search engines return fresh results rather than old pages when
    the user asks about events, news, top lists, etc.
    """
    import re
    # If the query already has a target year (e.g. 2024, 2025, 2026, 2027), do not append another year!
    if re.search(r'\b202[4-9]\b', prompt):
        return prompt

    year = datetime.now().year
    time_keywords = [
        "latest", "upcoming", "current", "top", "best", "new",
        "events", "news", "recently", "this year",
    ]
    if any(kw in prompt.lower() for kw in time_keywords):
        return f"{prompt} {year}"
    return prompt


def sanitize_url(raw_url: str, discard_domains: list[str]) -> str | None:
    """Sanitizes raw search URLs, unwrapping Google redirects and dropping spam/malformed URLs."""
    if not raw_url or not isinstance(raw_url, str):
        return None
    raw_url = raw_url.strip()
    if not (raw_url.startswith("http://") or raw_url.startswith("https://")):
        return None

    try:
        parsed = urlparse(raw_url)
        netloc = parsed.netloc.lower()

        # Reject malformed hostnames (e.g., http:///url, http://url/, or no TLD)
        if not netloc or netloc in ("url", "localhost") or "." not in netloc:
            return None

        # Unwrap Google search redirect wrappers (e.g. google.com/url?q=https://real-target.com)
        if "google." in netloc and parsed.path.startswith("/url"):
            qs = urllib.parse.parse_qs(parsed.query)
            target = qs.get("q", qs.get("url", []))
            if target and target[0].startswith(("http://", "https://")):
                return sanitize_url(target[0], discard_domains)
            return None

        if any(d in netloc for d in discard_domains):
            return None

        return raw_url
    except Exception:
        return None


def check_robots_txt(urls: list[str]) -> list[str]:
    """Filters URLs that disallow crawling according to their robots.txt."""
    allowed: list[str] = []
    default_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(3.0)  # fast 3s timeout to prevent hanging on robots.txt
    try:
        for url in urls:
            try:
                robots_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}/robots.txt"
                rp = RobotFileParser(robots_url)
                rp.read()
                if rp.can_fetch("*", url):
                    allowed.append(url)
            except Exception:
                allowed.append(url)
    finally:
        socket.setdefaulttimeout(default_timeout)
    return allowed


def get_web_urls(search_term: str, num_results: int = 15) -> tuple[list[str], str]:
    """Searches SearXNG and returns crawlable URLs plus a snippet context string."""
    discard_domains = [
        "youtube.com", "britannica.com", "vimeo.com",
        "support.google.com",
        # Consistently irrelevant to African event queries (movie and dictionary spam)
        "rottentomatoes.com", "moviefone.com", "imdb.com", "fandango.com",
        "sensacine.com", "warnerbros.com",
        "merriam-webster.com", "dictionary.com", "cambridge.org", "wiktionary.org", "wikipedia.org",
        "theupcoming.co.uk", "upcoming.org", "whats-on.co.uk",
        # Consistently timing out on Crawl4AI / geo-blocked
        "allconferencealert.net", "conferencelists.com",
        "yesinvestafrica.com",
    ]

    try:
        params = urllib.parse.urlencode({
            "q": search_term,
            "format": "json",
            "language": "all",
            "engines": "google,brave,bing,duckduckgo,google news",
        })
        req_url = f"{SEARXNG_URL}/search?{params}"
        print(f"Querying SearXNG: {req_url}")

        # Throttling Safety: Jitter between sequential searches
        time.sleep(random.uniform(2.5, 5.0))

        req = urllib.request.Request(req_url, headers={"User-Agent": "llm-web-search/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())

        valid_results = []
        for r in data.get("results", []):
            clean_url = sanitize_url(r.get("url", ""), discard_domains)
            if clean_url:
                r_copy = dict(r)
                r_copy["url"] = clean_url
                valid_results.append(r_copy)

        raw_results = valid_results[:num_results]

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


def get_web_urls_multi(queries: list[str], max_results_per_query: int = 8) -> tuple[list[str], str]:
    """Executes multiple queries against SearXNG and aggregates the results.
    
    Args:
        queries (list[str]): The list of enriched queries to search.
        max_results_per_query (int): Max URLs to extract per query.
        
    Returns:
        tuple[list[str], str]: Deduplicated list of URLs and aggregated snippet context.
    """
    all_urls = []
    seen_urls = set()
    all_snippets = []
    
    for query in queries:
        try:
            urls, snippet = get_web_urls(search_term=query, num_results=max_results_per_query)
            for url in urls:
                if url not in seen_urls:
                    seen_urls.add(url)
                    all_urls.append(url)
            if snippet:
                all_snippets.append(f"--- Results for: {query} ---\n{snippet}")
        except ValueError:
            print(f"SearXNG returned no results for query variant: {query}")
            continue
        except Exception as exc:
            print(f"Error fetching variant '{query}': {exc}")
            continue

    if not all_urls:
        raise ValueError("SearXNG returned no results for any of the queries.")

    return all_urls, "\n\n".join(all_snippets)
