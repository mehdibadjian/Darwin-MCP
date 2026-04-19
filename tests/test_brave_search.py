"""Tests for memory.species.brave_search."""
import pytest
from unittest.mock import patch, MagicMock
import json


def test_brave_search_no_api_key():
    from memory.species.brave_search import brave_search
    result = brave_search("test query", api_key="")
    assert result["status"] == "error"
    assert "BRAVE_API_KEY" in result["error"]


def test_brave_search_returns_results():
    from memory.species.brave_search import brave_search

    mock_response_data = {
        "web": {
            "results": [
                {"title": "Result 1", "url": "https://example.com", "description": "Snippet 1"},
                {"title": "Result 2", "url": "https://other.com", "description": "Snippet 2"},
            ]
        }
    }

    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(mock_response_data).encode()
    mock_resp.info.return_value = MagicMock(**{"get.return_value": None})
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_resp):
        result = brave_search("test query", api_key="test-key")

    assert result["status"] == "ok"
    assert len(result["results"]) == 2
    assert result["results"][0]["title"] == "Result 1"
    assert result["results"][0]["url"] == "https://example.com"


def test_brave_search_http_error():
    from memory.species.brave_search import brave_search
    import urllib.error

    with patch("urllib.request.urlopen", side_effect=urllib.error.HTTPError(
        url="", code=403, msg="Forbidden", hdrs=None, fp=None
    )):
        result = brave_search("query", api_key="bad-key")

    assert result["status"] == "error"
    assert "403" in result["error"]


def test_brave_search_caps_count():
    """Count should be capped at 20."""
    from memory.species.brave_search import brave_search

    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        raise Exception("stop")

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        brave_search("q", count=999, api_key="k")

    assert "count=20" in captured.get("url", "")
