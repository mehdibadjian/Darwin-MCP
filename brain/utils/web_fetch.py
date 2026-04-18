"""Web fetch utility for the Darwin-God-MCP brain.

Fetches a URL and returns plain text, stripping HTML tags.
Used by skills that need live documentation at runtime and by the /search endpoint.
"""
import re
import urllib.error
import urllib.request
from typing import Optional

_USER_AGENT = "Mozilla/5.0 (compatible; DarwinMCP/1.0; +https://github.com/darwin-god-mcp)"
_DEFAULT_TIMEOUT = 10


def fetch_url(url: str, timeout: int = _DEFAULT_TIMEOUT) -> dict:
    """Fetch *url* and return plain text content stripped of HTML.

    Returns:
        {"url": str, "text": str, "status": "ok"} on success
        {"url": str, "error": str, "status": "error"} on failure
    """
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        text = _strip_html(raw)
        return {"url": url, "text": text[:8000], "status": "ok"}
    except urllib.error.HTTPError as e:
        return {"url": url, "error": f"HTTP {e.code}: {e.reason}", "status": "error"}
    except Exception as e:
        return {"url": url, "error": str(e), "status": "error"}


def fetch_urls(urls: list, timeout: int = _DEFAULT_TIMEOUT) -> list:
    """Fetch multiple URLs sequentially. Returns list of fetch_url results."""
    return [fetch_url(url, timeout=timeout) for url in urls]


def _strip_html(html: str) -> str:
    """Remove HTML tags, collapse whitespace, decode common entities."""
    # Remove script/style blocks entirely
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # Remove all remaining tags
    html = re.sub(r"<[^>]+>", " ", html)
    # Decode common entities
    for entity, char in [("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
                          ("&quot;", '"'), ("&#39;", "'"), ("&nbsp;", " ")]:
        html = html.replace(entity, char)
    # Collapse whitespace
    html = re.sub(r"\s+", " ", html).strip()
    return html
