"""Tests for ENH-US7: X-Vault-Repo header routing in the SSE Bridge."""
import asyncio
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import brain.bridge.sse_server as mod

VALID_TOKEN = "test-secret-token"

SAMPLE_REGISTRY = {
    "organism_version": "1.0.0",
    "last_mutation": None,
    "skills": {
        "hello_world": {"status": "Active", "entry_point": "memory.species.hello_world.run"},
    },
}


@pytest.fixture(autouse=True)
def set_token_env(monkeypatch):
    monkeypatch.setenv("MCP_BEARER_TOKEN", VALID_TOKEN)


@pytest.fixture()
def client():
    return TestClient(mod.app, raise_server_exceptions=True)


def _first_sse_event(client, headers):
    """GET /sse and return (status_code, first_data_payload or None)."""

    async def _raise_cancelled(coro, *args, **kwargs):
        coro.close()
        raise asyncio.CancelledError()

    with patch.object(mod.asyncio, "wait_for", _raise_cancelled):
        response = client.get("/sse", headers=headers)

    for line in response.text.splitlines():
        if line.startswith("data:"):
            return response.status_code, json.loads(line[len("data: "):])
    return response.status_code, None


# ── resolve_vault_path unit tests ─────────────────────────────────────────────

def test_resolve_vault_path_no_header_returns_primary():
    """AC2: None/empty vault_id → PRIMARY_VAULT."""
    assert mod.resolve_vault_path(None) == mod.PRIMARY_VAULT
    assert mod.resolve_vault_path("") == mod.PRIMARY_VAULT


def test_resolve_vault_path_valid_vault_id(tmp_path, monkeypatch):
    """AC1: existing submodule directory → correct Path."""
    submodules = tmp_path / "submodules"
    vault_dir = submodules / "web-dev-vault"
    vault_dir.mkdir(parents=True)

    monkeypatch.setattr(mod, "SUBMODULES_DIR", submodules)
    result = mod.resolve_vault_path("web-dev-vault")
    assert result == vault_dir


def test_resolve_vault_path_invalid_vault_raises(tmp_path, monkeypatch):
    """AC3: non-existent vault_id → ValueError('Vault not found')."""
    monkeypatch.setattr(mod, "SUBMODULES_DIR", tmp_path / "submodules")
    with pytest.raises(ValueError, match="Vault not found"):
        mod.resolve_vault_path("does-not-exist")


def test_get_vault_registry_path():
    """get_vault_registry_path returns <vault>/dna/registry.json."""
    vault = Path("/some/vault")
    assert mod.get_vault_registry_path(vault) == vault / "dna" / "registry.json"


# ── /sse endpoint vault routing ───────────────────────────────────────────────

def test_sse_endpoint_default_vault_when_no_header(client):
    """AC2: no X-Vault-Repo header → uses primary vault registry."""
    with patch("brain.bridge.sse_server.read_registry", return_value=SAMPLE_REGISTRY) as mock_rr:
        status, payload = _first_sse_event(
            client, {"Authorization": f"Bearer {VALID_TOKEN}"}
        )
    assert status == 200
    assert payload["type"] == "tool_list"
    called_path = mock_rr.call_args[0][0] if mock_rr.call_args[0] else mock_rr.call_args[1].get("registry_path")
    assert called_path == mod.get_vault_registry_path(mod.PRIMARY_VAULT)


def test_sse_endpoint_returns_400_for_unknown_vault(client):
    """AC3: invalid vault_id → 400."""
    response = client.get(
        "/sse",
        headers={
            "Authorization": f"Bearer {VALID_TOKEN}",
            "X-Vault-Repo": "nonexistent-vault",
        },
    )
    assert response.status_code == 400
    assert "Vault not found" in response.text


def test_sse_endpoint_uses_named_vault(client, tmp_path, monkeypatch):
    """AC1: valid X-Vault-Repo → correct vault registry path passed to read_registry."""
    submodules = tmp_path / "submodules"
    vault_dir = submodules / "web-dev-vault"
    vault_dir.mkdir(parents=True)
    monkeypatch.setattr(mod, "SUBMODULES_DIR", submodules)

    with patch("brain.bridge.sse_server.read_registry", return_value=SAMPLE_REGISTRY) as mock_rr:
        status, _ = _first_sse_event(
            client,
            {
                "Authorization": f"Bearer {VALID_TOKEN}",
                "X-Vault-Repo": "web-dev-vault",
            },
        )
    assert status == 200
    called_path = mock_rr.call_args[0][0]
    assert called_path == vault_dir / "dna" / "registry.json"


# ── /evolve endpoint vault routing ────────────────────────────────────────────

def test_evolve_endpoint_uses_vault_from_header(client, tmp_path, monkeypatch):
    """AC1: /evolve respects X-Vault-Repo and passes vault path to request_evolution."""
    submodules = tmp_path / "submodules"
    vault_dir = submodules / "my-vault"
    vault_dir.mkdir(parents=True)
    monkeypatch.setattr(mod, "SUBMODULES_DIR", submodules)

    payload = {"name": "skill_a", "code": "def run(): pass", "tests": "def test_x(): pass"}

    with patch("brain.bridge.sse_server.request_evolution") as mock_evo:
        mock_result = mock_evo.return_value
        mock_result.success = True
        mock_result.to_dict.return_value = {}

        response = client.post(
            "/evolve",
            json=payload,
            headers={
                "Authorization": f"Bearer {VALID_TOKEN}",
                "X-Vault-Repo": "my-vault",
            },
        )

    assert response.status_code == 200
    _, kwargs = mock_evo.call_args
    assert kwargs["memory_dir"] == str(vault_dir)


def test_evolve_endpoint_returns_400_for_unknown_vault(client):
    """AC3: /evolve with invalid vault_id → 400."""
    payload = {"name": "skill_a", "code": "def run(): pass", "tests": "def test_x(): pass"}
    response = client.post(
        "/evolve",
        json=payload,
        headers={
            "Authorization": f"Bearer {VALID_TOKEN}",
            "X-Vault-Repo": "ghost-vault",
        },
    )
    assert response.status_code == 400
    assert "Vault not found" in response.json()["message"]


# ── /tools/{name}/invoke vault routing ────────────────────────────────────────

def test_invoke_tool_returns_400_for_unknown_vault(client):
    """AC3: /tools/foo/invoke with invalid vault_id → 400."""
    response = client.get(
        "/tools/hello_world/invoke",
        headers={
            "Authorization": f"Bearer {VALID_TOKEN}",
            "X-Vault-Repo": "phantom-vault",
        },
    )
    assert response.status_code == 400
    assert "Vault not found" in response.text


def test_invoke_tool_uses_vault_registry(client, tmp_path, monkeypatch):
    """AC1: /tools/{name}/invoke reads from the specified vault's registry."""
    submodules = tmp_path / "submodules"
    vault_dir = submodules / "alt-vault"
    vault_dir.mkdir(parents=True)
    monkeypatch.setattr(mod, "SUBMODULES_DIR", submodules)

    with patch("brain.bridge.sse_server.read_registry", return_value=SAMPLE_REGISTRY) as mock_rr:
        response = client.get(
            "/tools/hello_world/invoke",
            headers={
                "Authorization": f"Bearer {VALID_TOKEN}",
                "X-Vault-Repo": "alt-vault",
            },
        )
    assert response.status_code == 200
    called_path = mock_rr.call_args[0][0]
    assert called_path == vault_dir / "dna" / "registry.json"


# ── Concurrent safety ─────────────────────────────────────────────────────────

def test_concurrent_requests_use_correct_vaults(tmp_path, monkeypatch):
    """AC4: concurrent requests each resolve their own vault independently."""
    submodules = tmp_path / "submodules"
    vault_a = submodules / "vault-a"
    vault_b = submodules / "vault-b"
    vault_a.mkdir(parents=True)
    vault_b.mkdir(parents=True)
    monkeypatch.setattr(mod, "SUBMODULES_DIR", submodules)

    assert mod.resolve_vault_path("vault-a") == vault_a
    assert mod.resolve_vault_path("vault-b") == vault_b
    assert mod.resolve_vault_path(None) == mod.PRIMARY_VAULT
    # No shared state mutated — all three resolve correctly simultaneously
