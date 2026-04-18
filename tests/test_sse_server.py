"""Tests for brain/bridge/sse_server.py — US-1, US-2, US-5, US-21, US-32."""
import json
import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

# ── helpers ───────────────────────────────────────────────────────────────────

VALID_TOKEN = "test-secret-token"

SAMPLE_REGISTRY = {
    "organism_version": "1.0.0",
    "last_mutation": None,
    "skills": {
        "hello_world": {
            "status": "Active",
            "entry_point": "memory.species.hello_world.run",
            "description": "Says hello",
        },
        "bad_skill": {
            "status": "Toxic",
            "entry_point": "memory.species.bad_skill.run",
            "description": "Should be excluded",
        },
        "another_skill": {
            "status": "Active",
            "entry_point": "memory.species.another_skill.run",
            "description": "Another active skill",
        },
    },
}


@pytest.fixture(autouse=True)
def set_token_env(monkeypatch):
    monkeypatch.setenv("MCP_BEARER_TOKEN", VALID_TOKEN)


def _get_client():
    """Return a TestClient for the SSE app (no reload)."""
    import brain.bridge.sse_server as mod
    return TestClient(mod.app, raise_server_exceptions=True)


def _reload_client():
    """Reload the module (picks up env changes) and return a fresh TestClient."""
    import importlib
    import brain.bridge.sse_server as mod
    importlib.reload(mod)
    return TestClient(mod.app, raise_server_exceptions=True)


def _first_sse_event(client, headers):
    """GET /sse and return (status_code, first_data_payload).

    Patches asyncio.wait_for in sse_server to raise CancelledError immediately.
    The generator catches CancelledError and exits cleanly after the tool_list
    event, so client.get() returns without hanging.
    """
    import asyncio as _asyncio
    import brain.bridge.sse_server as _mod

    async def _raise_cancelled(coro, *args, **kwargs):
        coro.close()  # prevent "coroutine was never awaited" ResourceWarning
        raise _asyncio.CancelledError()

    with patch.object(_mod.asyncio, "wait_for", _raise_cancelled):
        response = client.get("/sse", headers=headers)

    for line in response.text.splitlines():
        if line.startswith("data:"):
            return response.status_code, json.loads(line[len("data: "):])
    return response.status_code, None


def _sse_status(client, headers):
    """Return only the HTTP status code for a (typically rejected) SSE request.

    For 401 cases the generator never runs, so no patch is needed; we patch
    anyway to keep the helper symmetric and safe for any future code path.
    """
    import asyncio as _asyncio
    import brain.bridge.sse_server as _mod

    async def _raise_cancelled(coro, *args, **kwargs):
        coro.close()  # prevent "coroutine was never awaited" ResourceWarning
        raise _asyncio.CancelledError()

    with patch.object(_mod.asyncio, "wait_for", _raise_cancelled):
        response = client.get("/sse", headers=headers)
    return response.status_code


# ── US-1: Bearer Token Authentication ─────────────────────────────────────────

def test_valid_token_accepted():
    """US-1 AC1: valid Bearer token → 200."""
    client = _get_client()
    with patch("brain.bridge.sse_server.read_registry", return_value=SAMPLE_REGISTRY):
        status, _ = _first_sse_event(client, {"Authorization": f"Bearer {VALID_TOKEN}"})
    assert status == 200


def test_invalid_token_rejected():
    """US-1 AC2: wrong token → 401."""
    client = _get_client()
    status = _sse_status(client, {"Authorization": "Bearer wrong-token"})
    assert status == 401


def test_missing_auth_header_rejected():
    """US-1 AC3: no Authorization header → 401."""
    client = _get_client()
    status = _sse_status(client, {})
    assert status == 401


# ── US-2: Constant-Time Token Comparison ──────────────────────────────────────

def test_token_uses_hmac_compare_digest():
    """US-2 AC1: verify_token uses hmac.compare_digest."""
    import inspect
    import brain.bridge.sse_server as mod
    source = inspect.getsource(mod.verify_token)
    assert "hmac.compare_digest" in source


def test_token_from_env_var(monkeypatch):
    """US-2 AC3: token is read from MCP_BEARER_TOKEN, not hardcoded."""
    monkeypatch.setenv("MCP_BEARER_TOKEN", "env-driven-token")
    import brain.bridge.sse_server as mod
    # verify_token reads os.environ at call time
    assert mod.verify_token("Bearer env-driven-token") is True
    assert mod.verify_token("Bearer test-secret-token") is False


def test_invalid_token_any_length(monkeypatch):
    """US-2 AC2: comparison does not short-circuit on length difference."""
    import brain.bridge.sse_server as mod
    assert mod.verify_token("Bearer x") is False
    assert mod.verify_token("Bearer " + "a" * 100) is False
    assert mod.verify_token("Bearer ") is False


# ── US-5: Tool List Serving over SSE ──────────────────────────────────────────

def test_tool_list_contains_all_registry_skills():
    """US-5 AC1: all non-Toxic registry entries appear in the SSE response."""
    client = _get_client()
    with patch("brain.bridge.sse_server.read_registry", return_value=SAMPLE_REGISTRY):
        status, payload = _first_sse_event(client, {"Authorization": f"Bearer {VALID_TOKEN}"})
    assert status == 200
    assert payload["type"] == "tool_list"
    assert "hello_world" in payload["tools"]
    assert "another_skill" in payload["tools"]


def test_toxic_skill_excluded():
    """US-5 AC2: skill with status=Toxic is excluded from tool list."""
    client = _get_client()
    with patch("brain.bridge.sse_server.read_registry", return_value=SAMPLE_REGISTRY):
        _, payload = _first_sse_event(client, {"Authorization": f"Bearer {VALID_TOKEN}"})
    assert "bad_skill" not in payload["tools"]


def test_tool_list_delivered_quickly():
    """US-5 AC3: tool list delivered within 2 seconds of connection."""
    import time
    client = _get_client()
    with patch("brain.bridge.sse_server.read_registry", return_value=SAMPLE_REGISTRY):
        start = time.monotonic()
        status, payload = _first_sse_event(client, {"Authorization": f"Bearer {VALID_TOKEN}"})
        elapsed = time.monotonic() - start
    assert status == 200
    assert elapsed < 2.0


# ── US-21: SSE Bridge loads tools exclusively from registry.json ──────────────

def test_only_registry_skills_served():
    """US-21 AC1: filesystem-only species not in registry are absent from list."""
    client = _get_client()
    with patch("brain.bridge.sse_server.read_registry", return_value=SAMPLE_REGISTRY):
        _, payload = _first_sse_event(client, {"Authorization": f"Bearer {VALID_TOKEN}"})
    assert set(payload["tools"].keys()) == {"hello_world", "another_skill"}


def test_registry_is_sole_state_source():
    """US-21 AC2: bridge does not call os.scandir / os.listdir on species dir."""
    client = _get_client()
    with patch("brain.bridge.sse_server.read_registry", return_value=SAMPLE_REGISTRY), \
         patch("os.scandir") as mock_scan, \
         patch("os.listdir") as mock_list:
        _first_sse_event(client, {"Authorization": f"Bearer {VALID_TOKEN}"})
    mock_scan.assert_not_called()
    mock_list.assert_not_called()


def test_entry_point_from_registry():
    """US-21 AC3: entry_point field from registry is preserved in tool list."""
    client = _get_client()
    with patch("brain.bridge.sse_server.read_registry", return_value=SAMPLE_REGISTRY):
        _, payload = _first_sse_event(client, {"Authorization": f"Bearer {VALID_TOKEN}"})
    assert payload["tools"]["hello_world"]["entry_point"] == "memory.species.hello_world.run"


# ── US-32: All operational state derived from registry.json on startup ─────────

def test_stale_sandbox_cleanup_on_startup():
    """US-32 AC3: /tmp/mutation_* dirs are cleaned on startup."""
    import brain.bridge.sse_server as mod
    import importlib

    # Create fake stale sandbox dirs in /tmp
    stale1 = Path("/tmp/mutation_abc123")
    stale2 = Path("/tmp/mutation_xyz789")
    stale1.mkdir(exist_ok=True)
    stale2.mkdir(exist_ok=True)

    try:
        mod.cleanup_stale_sandboxes()
        assert not stale1.exists(), "stale1 should be removed"
        assert not stale2.exists(), "stale2 should be removed"
    finally:
        # cleanup in case of test failure
        shutil.rmtree(stale1, ignore_errors=True)
        shutil.rmtree(stale2, ignore_errors=True)


def test_registry_state_survives_restart(tmp_path):
    """US-32 AC1+AC2: registry.json is sole persistent state; re-reading it restores tools."""
    from brain.utils.registry import init_registry, read_registry, write_registry

    reg_path = tmp_path / "registry.json"
    init_registry(registry_path=reg_path)
    data = read_registry(registry_path=reg_path)
    data["skills"]["persistent_skill"] = {
        "status": "Active",
        "entry_point": "memory.species.persistent_skill.run",
        "description": "Survives restart",
    }
    write_registry(data, registry_path=reg_path)

    # Simulate restart: re-read from disk (no in-memory state)
    restored = read_registry(registry_path=reg_path)
    assert "persistent_skill" in restored["skills"]
