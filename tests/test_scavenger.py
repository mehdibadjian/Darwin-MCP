"""Tests for brain.engine.scavenger — ENH-US3."""
import base64
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from brain.engine.scavenger import Scavenger, RateLimitError, ScavengerError

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_SAMPLE_README = """\
# MCP Servers

## Reference Servers

| Server | Repository | Description |
|--------|-----------|-------------|
| [filesystem](https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem) | https://github.com/modelcontextprotocol/servers | Filesystem access |
| [weather](https://github.com/example/mcp-weather) | https://github.com/example/mcp-weather | Weather data |
| [github](https://github.com/example/mcp-github) | https://github.com/example/mcp-github | GitHub integration |
"""

_SAMPLE_SERVER_README = "# Weather MCP Server\n\nProvides real-time weather data.\n"


def _github_api_response(content: str) -> dict:
    """Build a fake GitHub API JSON response for a README."""
    encoded = base64.b64encode(content.encode()).decode()
    # GitHub wraps in chunks of 60 chars
    chunked = "\n".join(encoded[i : i + 60] for i in range(0, len(encoded), 60))
    return {
        "name": "README.md",
        "path": "README.md",
        "content": chunked + "\n",
        "encoding": "base64",
    }


def _ok(text: str) -> dict:
    return {"status": "ok", "text": text}


def _err(msg: str) -> dict:
    return {"status": "error", "error": msg}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_fetch_registry_returns_server_list():
    """AC1: fetch_registry() returns list of dicts with required keys."""
    api_json = json.dumps(_github_api_response(_SAMPLE_README))

    with patch("brain.engine.scavenger.fetch_url", return_value=_ok(api_json)) as mock_fetch:
        scavenger = Scavenger(github_token="fake-token")
        result = scavenger.fetch_registry()

    assert isinstance(result, list)
    assert len(result) >= 1
    for entry in result:
        assert "name" in entry
        assert "repo_url" in entry
        assert "readme_excerpt" in entry
        assert entry["repo_url"].startswith("https://github.com/")
    mock_fetch.assert_called_once()


def test_fetch_registry_rate_limit_raises_error():
    """AC3: 403 error raises RateLimitError."""
    with patch("brain.engine.scavenger.fetch_url", return_value=_err("HTTP 403: Forbidden")):
        scavenger = Scavenger()
        with pytest.raises(RateLimitError):
            scavenger.fetch_registry()


def test_fetch_registry_rate_limit_429_raises_error():
    """AC3: 429 error raises RateLimitError."""
    with patch("brain.engine.scavenger.fetch_url", return_value=_err("HTTP 429: Too Many Requests")):
        scavenger = Scavenger()
        with pytest.raises(RateLimitError):
            scavenger.fetch_registry()


def test_fetch_registry_rate_limit_in_body_raises_error():
    """AC3: JSON body with rate limit message raises RateLimitError."""
    body = json.dumps({"message": "API rate limit exceeded for ...", "documentation_url": "..."})
    with patch("brain.engine.scavenger.fetch_url", return_value=_ok(body)):
        scavenger = Scavenger()
        with pytest.raises(RateLimitError):
            scavenger.fetch_registry()


def test_fetch_server_readme_caches_to_temp_dir(tmp_path):
    """AC2: fetch_server_readme() caches to cache_dir/<repo_name>.md."""
    with patch(
        "brain.engine.scavenger.fetch_url",
        return_value=_ok(_SAMPLE_SERVER_README),
    ):
        scavenger = Scavenger(cache_dir=tmp_path)
        text = scavenger.fetch_server_readme("https://github.com/example/mcp-weather")

    assert text == _SAMPLE_SERVER_README
    cached = tmp_path / "mcp-weather.md"
    assert cached.exists()
    assert cached.read_text() == _SAMPLE_SERVER_README


def test_fetch_server_readme_rate_limit_raises_error():
    """AC3: rate limit on readme fetch raises RateLimitError."""
    with patch("brain.engine.scavenger.fetch_url", return_value=_err("HTTP 403: Forbidden")):
        scavenger = Scavenger()
        with pytest.raises(RateLimitError):
            scavenger.fetch_server_readme("https://github.com/example/mcp-server")


def test_list_servers_returns_name_repo_url_excerpt():
    """list_servers() wraps fetch_registry() and returns consistent shape."""
    api_json = json.dumps(_github_api_response(_SAMPLE_README))

    with patch("brain.engine.scavenger.fetch_url", return_value=_ok(api_json)):
        scavenger = Scavenger()
        servers = scavenger.list_servers()

    assert isinstance(servers, list)
    assert all({"name", "repo_url", "readme_excerpt"}.issubset(s.keys()) for s in servers)


def test_scavenger_gracefully_handles_network_error():
    """Generic network errors raise ScavengerError (not crash)."""
    with patch(
        "brain.utils.web_fetch.fetch_url",
        return_value=_err("Connection refused"),
    ):
        scavenger = Scavenger()
        with pytest.raises(ScavengerError):
            scavenger.fetch_registry()


def test_scavenger_uses_github_token_env(monkeypatch):
    """github_token is read from MCP_GITHUB_TOKEN env var."""
    monkeypatch.setenv("MCP_GITHUB_TOKEN", "env-token-abc")
    scavenger = Scavenger()
    assert scavenger.github_token == "env-token-abc"


def test_fetch_server_readme_invalid_repo_url():
    """Invalid repo URL raises ScavengerError."""
    scavenger = Scavenger()
    with pytest.raises(ScavengerError):
        scavenger.fetch_server_readme("https://not-github.com/foo/bar")


def test_fetch_registry_missing_content_field():
    """API response without 'content' raises ScavengerError."""
    body = json.dumps({"name": "README.md"})  # no 'content' key
    with patch("brain.engine.scavenger.fetch_url", return_value=_ok(body)):
        scavenger = Scavenger()
        with pytest.raises(ScavengerError):
            scavenger.fetch_registry()
