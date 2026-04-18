"""Web fetch utility for the Darwin-God-MCP brain.

Fetches a URL and returns plain text, stripping HTML tags.
Also provides search_web() using DuckDuckGo HTML (no API key required).
Used by skills that need live documentation at runtime and by the /search endpoint.
"""
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional

_USER_AGENT = "Mozilla/5.0 (compatible; DarwinMCP/1.0; +https://github.com/darwin-god-mcp)"
_DEFAULT_TIMEOUT = 10
_DDG_URL = "https://html.duckduckgo.com/html/"


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


def search_web(query: str, max_results: int = 5, timeout: int = _DEFAULT_TIMEOUT) -> list:
    """Search the web via DuckDuckGo HTML (no API key required).

    Returns a list of {"title": str, "url": str, "snippet": str} dicts.
    """
    try:
        data = urllib.parse.urlencode({"q": query, "kl": "us-en"}).encode()
        req = urllib.request.Request(
            _DDG_URL,
            data=data,
            headers={
                "User-Agent": _USER_AGENT,
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        return [{"title": "search error", "url": "", "snippet": str(e)}]

    results = []
    # Extract result blocks: each result has a link + snippet in DDG HTML
    blocks = re.findall(
        r'class="result__title".*?<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>.*?'
        r'class="result__snippet"[^>]*>(.*?)</div>',
        html,
        re.DOTALL,
    )
    for url, title, snippet in blocks[:max_results]:
        # DDG wraps URLs in redirects — extract the actual URL
        real_url = url
        uddg_match = re.search(r"uddg=([^&]+)", url)
        if uddg_match:
            real_url = urllib.parse.unquote(uddg_match.group(1))
        results.append({
            "title": _strip_html(title).strip(),
            "url": real_url,
            "snippet": _strip_html(snippet).strip()[:300],
        })

    return results


def _strip_html(html: str) -> str:
    """Remove HTML tags, collapse whitespace, decode common entities."""
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<[^>]+>", " ", html)
    for entity, char in [("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
                          ("&quot;", '"'), ("&#39;", "'"), ("&nbsp;", " ")]:
        html = html.replace(entity, char)
    html = re.sub(r"\s+", " ", html).strip()
    return html
