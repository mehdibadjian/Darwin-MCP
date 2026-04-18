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


# ---------------------------------------------------------------------------
# ENH-US4: generate_wrapper and commit_wrapper tests
# ---------------------------------------------------------------------------

_SAMPLE_REPO_URL = "https://github.com/example/mcp-weather"
_SAMPLE_README_TEXT = "# Weather MCP Server\n\nProvides real-time weather data.\n"


def test_generate_wrapper_returns_python_string():
    """AC1: generate_wrapper returns a string with run() and repo_url."""
    scavenger = Scavenger()
    wrapper = scavenger.generate_wrapper("weather", _SAMPLE_REPO_URL, _SAMPLE_README_TEXT)
    assert isinstance(wrapper, str)
    assert "def run(" in wrapper
    assert _SAMPLE_REPO_URL in wrapper
    assert "weather" in wrapper


def test_generate_wrapper_includes_provenance():
    """AC2: wrapper string contains repo_url and a generated_at timestamp."""
    scavenger = Scavenger()
    wrapper = scavenger.generate_wrapper("weather", _SAMPLE_REPO_URL, _SAMPLE_README_TEXT)
    assert _SAMPLE_REPO_URL in wrapper
    assert "generated_at" in wrapper or "Generated:" in wrapper


def test_generate_wrapper_includes_error_handling():
    """AC3: wrapper string contains try/except and logger usage."""
    scavenger = Scavenger()
    wrapper = scavenger.generate_wrapper("weather", _SAMPLE_REPO_URL, _SAMPLE_README_TEXT)
    assert "try" in wrapper or "except" in wrapper
    assert "logger" in wrapper


def test_commit_wrapper_writes_file(tmp_path):
    """AC1/2: commit_wrapper writes {name}.py into species_dir."""
    registry_file = tmp_path / "registry.json"
    from brain.utils.registry import write_registry
    write_registry({"organism_version": "1.0.0", "last_mutation": None, "skills": {}}, registry_path=registry_file)

    scavenger = Scavenger()
    wrapper_code = scavenger.generate_wrapper("weather", _SAMPLE_REPO_URL, _SAMPLE_README_TEXT)
    scavenger.commit_wrapper(
        "weather",
        _SAMPLE_REPO_URL,
        wrapper_code,
        species_dir=tmp_path,
        registry_path=registry_file,
    )
    assert (tmp_path / "weather.py").exists()
    assert "def run(" in (tmp_path / "weather.py").read_text()


def test_commit_wrapper_registers_with_external_source(tmp_path):
    """AC2: Registry entry has source='external' and repo_url set."""
    registry_file = tmp_path / "registry.json"
    from brain.utils.registry import write_registry, read_registry
    write_registry({"organism_version": "1.0.0", "last_mutation": None, "skills": {}}, registry_path=registry_file)

    scavenger = Scavenger()
    wrapper_code = scavenger.generate_wrapper("weather", _SAMPLE_REPO_URL, _SAMPLE_README_TEXT)
    scavenger.commit_wrapper(
        "weather",
        _SAMPLE_REPO_URL,
        wrapper_code,
        species_dir=tmp_path,
        registry_path=registry_file,
    )
    registry = read_registry(registry_file)
    entry = registry["skills"].get("weather")
    assert entry is not None
    assert entry.get("source") == "external"
    assert entry.get("repo_url") == _SAMPLE_REPO_URL


def test_commit_wrapper_provenance_metadata(tmp_path):
    """AC2: Registry entry has generated_at field (ISO8601)."""
    registry_file = tmp_path / "registry.json"
    from brain.utils.registry import write_registry, read_registry
    write_registry({"organism_version": "1.0.0", "last_mutation": None, "skills": {}}, registry_path=registry_file)

    scavenger = Scavenger()
    wrapper_code = scavenger.generate_wrapper("weather", _SAMPLE_REPO_URL, _SAMPLE_README_TEXT)
    scavenger.commit_wrapper(
        "weather",
        _SAMPLE_REPO_URL,
        wrapper_code,
        species_dir=tmp_path,
        registry_path=registry_file,
    )
    registry = read_registry(registry_file)
    entry = registry["skills"]["weather"]
    assert "generated_at" in entry
    assert isinstance(entry["generated_at"], str)
    assert len(entry["generated_at"]) > 10  # not empty, looks like ISO8601
