"""Webpage content extraction with trafilatura primary, httpx+bs4 fallback."""

from __future__ import annotations

import asyncio
import logging

from kresearch.providers.types import ToolDeclaration

log = logging.getLogger(__name__)

READ_WEBPAGE_DECLARATION = ToolDeclaration(
    name="read_webpage",
    description=(
        "Fetch and extract the main content from a webpage URL. Returns clean "
        "text, title, and URL. Use this to read full articles, research papers, "
        "documentation, or news stories. Prefer authoritative primary sources."
    ),
    parameters={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The full URL to fetch and extract content from.",
            },
        },
        "required": ["url"],
    },
)

MAX_CONTENT_LEN = 15_000


async def _extract_with_trafilatura(url: str) -> dict | None:
    def _extract():
        import trafilatura
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return None
        text = trafilatura.extract(
            downloaded, output_format="markdown",
            include_links=True, with_metadata=True,
        )
        metadata = trafilatura.extract_metadata(downloaded)
        title = metadata.title if metadata else ""
        if not text:
            return None
        return {"content": text, "title": title, "url": url}
    try:
        return await asyncio.to_thread(_extract)
    except Exception as e:
        log.debug("Trafilatura failed for %s: %s", url, e)
        return None


async def _extract_with_httpx(url: str) -> dict | None:
    try:
        import httpx
        from bs4 import BeautifulSoup
        async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")
            for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
                tag.decompose()
            title = soup.title.string if soup.title else ""
            content = soup.get_text(separator="\n", strip=True)
            if not content or len(content) < 50:
                return None
            return {"content": content, "title": title, "url": url}
    except Exception as e:
        log.debug("httpx fallback failed for %s: %s", url, e)
        return None


async def handle_read_webpage(args: dict, **_ctx) -> dict:
    url = args.get("url", "")
    if not url:
        return {"error": "No URL provided."}

    result = await _extract_with_trafilatura(url)
    if not result:
        result = await _extract_with_httpx(url)
    if not result:
        return {"error": f"Could not extract content from {url}. Try another source."}

    content = result["content"]
    if len(content) > MAX_CONTENT_LEN:
        result["content"] = content[:MAX_CONTENT_LEN] + "\n\n[Content truncated...]"
        result["truncated"] = True
    result["char_count"] = len(content)
    return result
