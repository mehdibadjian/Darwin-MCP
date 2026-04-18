"""Scavenger Engine for Darwin-MCP.

Fetches and parses the official MCP Server Registry from GitHub,
enabling discovery of available open-source MCP servers.
"""
import base64
import datetime
import json
import logging
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from brain.utils.web_fetch import fetch_url
from brain.utils.registry import read_registry, write_registry, init_registry

logger = logging.getLogger(__name__)

_DEFAULT_CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "memory" / "temp"
_GITHUB_API_BASE = "https://api.github.com"
_RAW_CONTENT_BASE = "https://raw.githubusercontent.com"


class ScavengerError(Exception):
    pass


class RateLimitError(ScavengerError):
    pass


class Scavenger:
    REGISTRY_URL = "https://api.github.com/repos/modelcontextprotocol/servers/contents/README.md"

    def __init__(self, cache_dir=None, github_token=None):
        self.cache_dir = Path(cache_dir) if cache_dir else _DEFAULT_CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.github_token = github_token or os.environ.get("MCP_GITHUB_TOKEN")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _headers(self) -> dict:
        headers = {"Accept": "application/vnd.github.v3+json"}
        if self.github_token:
            headers["Authorization"] = f"Bearer {self.github_token}"
        return headers

    def _fetch(self, url: str) -> str:
        """Fetch *url* and return raw text; raise appropriate errors."""
        result = fetch_url(url)
        if result["status"] == "error":
            error_msg = result.get("error", "unknown error")
            # Detect rate-limit signals in the error message
            if "403" in error_msg or "429" in error_msg or "rate limit" in error_msg.lower():
                raise RateLimitError(f"GitHub rate limit exceeded: {error_msg}")
            raise ScavengerError(f"Network error fetching {url}: {error_msg}")
        text = result.get("text", "")
        # Detect rate-limit signals in the response body
        if "rate limit" in text.lower() and ("exceeded" in text.lower() or "api rate" in text.lower()):
            raise RateLimitError("GitHub rate limit exceeded")
        return text

    def _fetch_json(self, url: str) -> Union[Dict, List]:
        """Fetch *url* expecting JSON; returns parsed object."""
        result = fetch_url(url)
        if result["status"] == "error":
            error_msg = result.get("error", "unknown error")
            if "403" in error_msg or "429" in error_msg or "rate limit" in error_msg.lower():
                raise RateLimitError(f"GitHub rate limit exceeded: {error_msg}")
            raise ScavengerError(f"Network error fetching {url}: {error_msg}")
        text = result.get("text", "")
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # web_fetch strips HTML — try to detect rate-limit in stripped text
            if "rate limit" in text.lower():
                raise RateLimitError("GitHub rate limit exceeded")
            raise ScavengerError(f"Invalid JSON response from {url}")
        # GitHub API embeds rate-limit errors as JSON {"message": "API rate limit exceeded..."}
        if isinstance(data, dict):
            message = data.get("message", "")
            if "rate limit" in message.lower():
                raise RateLimitError(f"GitHub rate limit exceeded: {message}")
        return data

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch_registry(self) -> List[Dict]:
        """Fetch and parse the official MCP server list from GitHub.

        Returns list of {"name": str, "repo_url": str, "readme_excerpt": str}.
        Raises RateLimitError on 403/429 or rate-limit response.
        """
        data = self._fetch_json(self.REGISTRY_URL)
        if not isinstance(data, dict) or "content" not in data:
            raise ScavengerError("Unexpected GitHub API response: missing 'content' field")

        # GitHub returns base64-encoded file content
        raw_b64 = data["content"].replace("\n", "")
        try:
            readme_text = base64.b64decode(raw_b64).decode("utf-8", errors="replace")
        except Exception as exc:
            raise ScavengerError(f"Failed to decode README content: {exc}") from exc

        servers = _parse_server_list(readme_text)
        logger.info("Scavenger fetched %d servers from registry", len(servers))
        return servers

    def fetch_server_readme(self, repo_url: str) -> str:
        """Fetch README for a specific MCP server repo and cache it.

        Args:
            repo_url: GitHub repository URL, e.g. https://github.com/owner/repo

        Returns the README text.
        Caches to {cache_dir}/{repo_name}.md.
        Raises RateLimitError on rate limit.
        """
        owner, repo = _parse_github_repo(repo_url)
        raw_url = f"{_RAW_CONTENT_BASE}/{owner}/{repo}/main/README.md"

        readme_text = self._fetch(raw_url)

        cache_path = self.cache_dir / f"{repo}.md"
        try:
            cache_path.write_text(readme_text, encoding="utf-8")
            logger.debug("Cached README for %s to %s", repo, cache_path)
        except OSError as exc:
            logger.warning("Could not cache README for %s: %s", repo, exc)

        return readme_text

    def list_servers(self) -> List[Dict]:
        """Return all servers with name, repo_url, readme_excerpt."""
        return self.fetch_registry()

    def generate_wrapper(self, name: str, repo_url: str, readme_text: str) -> str:
        """Generate a Python wrapper species string for an external MCP server.

        Returns Python source code as a string.
        The wrapper includes: docstring with provenance, run(input_data) function,
        logging, error handling, and a comment noting external API translation.
        """
        generated_at = datetime.datetime.utcnow().isoformat()
        code = f'''\
"""
External MCP wrapper: {name}
Source: {repo_url}
Generated: {generated_at}
generated_at: {generated_at}
"""
import logging

logger = logging.getLogger(__name__)

# External API: {repo_url}


def run(input_data: dict) -> dict:
    """Invoke the external MCP server tool and map response to internal format.

    Translates input_data to the {name} external API and maps the response
    back to the Darwin-MCP internal species format.
    """
    try:
        logger.info("Invoking external wrapper '{name}' with input: %s", input_data)
        # TODO: replace with actual HTTP call to {repo_url}
        result = {{
            "status": "ok",
            "source": "external",
            "species": "{name}",
            "repo_url": "{repo_url}",
            "output": input_data,
        }}
        logger.debug("External wrapper '{name}' response: %s", result)
        return result
    except Exception as exc:
        logger.error("External wrapper '{name}' failed: %s", exc)
        return {{"status": "error", "error": str(exc)}}
'''
        return code

    def commit_wrapper(
        self,
        name: str,
        repo_url: str,
        wrapper_code: str,
        species_dir=None,
        registry_path=None,
    ) -> dict:
        """Write wrapper_code to species_dir/{name}.py and register in registry.

        Adds to registry with:
          source="external"
          repo_url=repo_url
          generated_at=ISO8601 timestamp
          status="active"

        Returns updated registry entry dict.
        """
        if species_dir is None:
            species_dir = Path(__file__).resolve().parent.parent.parent / "memory" / "species"
        species_dir = Path(species_dir)
        species_dir.mkdir(parents=True, exist_ok=True)

        species_file = species_dir / f"{name}.py"
        species_file.write_text(wrapper_code, encoding="utf-8")
        logger.info("Wrote wrapper species '%s' to %s", name, species_file)

        registry_path = Path(registry_path) if registry_path is not None else None
        init_registry(registry_path)
        registry = read_registry(registry_path)

        generated_at = datetime.datetime.utcnow().isoformat()
        existing = registry["skills"].get(name, {})
        registry["skills"][name] = {
            "path": str(species_file),
            "entry_point": name,
            "runtime": existing.get("runtime", "python3"),
            "dependencies": existing.get("dependencies", []),
            "evolved_at": existing.get("evolved_at"),
            "status": "active",
            "source": "external",
            "repo_url": repo_url,
            "generated_at": generated_at,
            "last_used_at": existing.get("last_used_at"),
            "total_calls": existing.get("total_calls", 0),
            "success_count": existing.get("success_count", 0),
            "failure_count": existing.get("failure_count", 0),
        }
        write_registry(registry, registry_path)
        logger.info("Registered external wrapper '%s' in registry", name)
        return registry["skills"][name]


# ------------------------------------------------------------------
# Parsing helpers
# ------------------------------------------------------------------

def _parse_github_repo(repo_url: str) -> Tuple[str, str]:
    """Extract (owner, repo) from a GitHub URL."""
    match = re.search(r"github\.com/([^/]+)/([^/\s#?]+)", repo_url)
    if not match:
        raise ScavengerError(f"Cannot parse GitHub repo from URL: {repo_url}")
    owner = match.group(1)
    repo = match.group(2).rstrip(".git")
    return owner, repo


def _parse_server_list(readme: str) -> List[Dict]:
    """Extract MCP server entries from the registry README.

    Looks for markdown table rows and markdown links that reference GitHub repos.
    Returns list of {"name": str, "repo_url": str, "readme_excerpt": str}.
    """
    servers: List[Dict] = []
    seen_urls: set = set()

    # Strategy 1: markdown table rows  |  [name](url)  |  description  |
    table_row = re.compile(
        r"\|\s*\[([^\]]+)\]\((https://github\.com/[^\)]+)\)\s*\|([^\|]*)\|"
    )
    for m in table_row.finditer(readme):
        name = m.group(1).strip()
        url = m.group(2).strip().rstrip("/")
        excerpt = m.group(3).strip()[:200]
        if url not in seen_urls:
            seen_urls.add(url)
            servers.append({"name": name, "repo_url": url, "readme_excerpt": excerpt})

    # Strategy 2: plain markdown links  [name](https://github.com/...)
    if not servers:
        md_link = re.compile(r"\[([^\]]+)\]\((https://github\.com/[^\)]+)\)")
        for m in md_link.finditer(readme):
            name = m.group(1).strip()
            url = m.group(2).strip().rstrip("/")
            # Skip obvious non-server links (badges, org links, etc.)
            parts = url.rstrip("/").split("/")
            if len(parts) < 5:  # needs at least github.com/owner/repo
                continue
            if url not in seen_urls:
                seen_urls.add(url)
                # Grab the surrounding line as excerpt
                line_start = readme.rfind("\n", 0, m.start()) + 1
                line_end = readme.find("\n", m.end())
                excerpt = readme[line_start:line_end if line_end != -1 else None].strip()[:200]
                servers.append({"name": name, "repo_url": url, "readme_excerpt": excerpt})

    return servers
