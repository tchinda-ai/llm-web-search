"""
core/crawler.py — async web crawling and context assembly.

No UI framework imports. The crawler uses headless Chromium via crawl4ai.
build_context_from_crawl() is synchronous and can be called from any context
(Streamlit, Flask, CLI, tests).
"""

from crawl4ai import AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerRunConfig
from crawl4ai.content_filter_strategy import BM25ContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from crawl4ai.models import CrawlResult


def normalize_url(url: str) -> str:
    """Normalises a URL into a safe string (used as a document identifier).

    Args:
        url (str): The URL to normalise.

    Returns:
        str: URL with scheme/www removed and /, -, . replaced by underscores.

    Example:
        >>> normalize_url("https://www.example.com/path-name")
        "example_com_path_name"
    """
    return (
        url.replace("https://", "")
        .replace("http://", "")
        .replace("www.", "")
        .replace("/", "_")
        .replace("-", "_")
        .replace(".", "_")
    )


async def crawl_webpages(urls: list[str], prompt: str) -> list[CrawlResult]:
    """Asynchronously crawls multiple pages and extracts relevant content.

    Uses BM25 content filtering to retain the most query-relevant paragraphs
    from each page and falls back to raw markdown if BM25 strips everything.

    Args:
        urls (list[str]): URLs to crawl.
        prompt (str): Query text used for BM25 relevance filtering.

    Returns:
        list[CrawlResult]: Crawl results carrying extracted markdown content.

    Notes:
        - BM25 threshold is 0.5 (permissive) to handle niche/French-language pages.
        - text_mode=False lets JavaScript execute — essential for JS-rendered sites.
        - <a> tags are kept so event page titles/links are not stripped.
    """
    bm25_filter = BM25ContentFilter(user_query=prompt, bm25_threshold=0.5)
    md_generator = DefaultMarkdownGenerator(content_filter=bm25_filter)

    crawler_config = CrawlerRunConfig(
        markdown_generator=md_generator,
        excluded_tags=["nav", "footer", "header", "form", "img"],  # keep <a>
        only_text=True,
        exclude_social_media_links=True,
        keep_data_attributes=False,
        cache_mode=CacheMode.BYPASS,
        remove_overlay_elements=True,
        word_count_threshold=30,
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36"
        ),
        page_timeout=30000,
    )
    browser_config = BrowserConfig(headless=True, text_mode=False, light_mode=True)

    async with AsyncWebCrawler(config=browser_config) as crawler:
        results = await crawler.arun_many(urls, config=crawler_config)
        print(f"Crawled {len(results)} pages")
        return results


def build_context_from_crawl(
    results: list[CrawlResult],
    prompt: str,
    snippet_context: str = "",
    max_chars: int = 6000,
) -> tuple[str, list[str]]:
    """Assembles a ranked context string directly from crawl results.

    Scores each paragraph by keyword overlap with the query, then concatenates
    the top chunks up to max_chars. Source URLs are embedded inline so the
    LLM can cite them without extra bookkeeping.

    Args:
        results (list[CrawlResult]): Output of crawl_webpages().
        prompt (str): Original user query (drives keyword scoring).
        snippet_context (str): Pre-formatted SearXNG snippet block to prepend.
        max_chars (int): Hard cap on total context length. Defaults to 6000.

    Returns:
        tuple[str, list[str]]:
            - context_string: ready to pass to the LLM
            - sources: deduplicated list of URLs whose content was included
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

    scored_chunks.sort(key=lambda x: x[0], reverse=True)

    context_parts: list[str] = []
    sources: list[str] = []
    total_chars = 0

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
