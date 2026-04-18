"""Tests for ENH-US10: get_droplet_vitals native MCP tool."""
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

# Set token before importing app
os.environ.setdefault("MCP_BEARER_TOKEN", "test-token")

from fastapi.testclient import TestClient

from brain.bridge.sse_server import app

client = TestClient(app, raise_server_exceptions=False)
HEADERS = {"Authorization": "Bearer test-token"}


@pytest.fixture(autouse=True, scope="module")
def trigger_startup():
    """Ensure builtin tools are registered before registry tests run."""
    from brain.bridge.sse_server import _register_builtin_tools
    _register_builtin_tools()

# ---------------------------------------------------------------------------
# Registry registration tests
# ---------------------------------------------------------------------------

def test_get_droplet_vitals_registered_in_registry():
    """After startup, registry contains 'get_droplet_vitals'."""
    from brain.utils.registry import read_registry
    registry = read_registry()
    assert "get_droplet_vitals" in registry["skills"], (
        "get_droplet_vitals must be registered in the registry at startup"
    )


def test_get_droplet_vitals_registry_entry_has_expected_fields():
    """Registry entry for get_droplet_vitals has required metadata fields."""
    from brain.utils.registry import read_registry
    registry = read_registry()
    entry = registry["skills"]["get_droplet_vitals"]
    assert entry.get("status") == "active"
    assert entry.get("runtime") == "builtin"
    assert "description" in entry


# ---------------------------------------------------------------------------
# Invocation endpoint tests
# ---------------------------------------------------------------------------

def test_invoke_get_droplet_vitals_returns_200():
    """GET /tools/get_droplet_vitals/invoke returns 200."""
    resp = client.get("/tools/get_droplet_vitals/invoke", headers=HEADERS)
    assert resp.status_code == 200


def test_invoke_vitals_response_has_required_keys():
    """Response JSON contains all required top-level keys."""
    resp = client.get("/tools/get_droplet_vitals/invoke", headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    for key in ("cpu_percent", "memory", "disk", "process", "collected_at", "evolution_log_tail"):
        assert key in data, f"Missing key: {key}"


def test_invoke_vitals_memory_subkeys():
    """memory dict contains used, total, percent."""
    resp = client.get("/tools/get_droplet_vitals/invoke", headers=HEADERS)
    data = resp.json()
    mem = data.get("memory", {})
    for key in ("used", "total", "percent"):
        assert key in mem, f"memory missing key: {key}"


def test_invoke_vitals_disk_is_list_with_entries():
    """disk value is a list of partition dicts with used/total/percent."""
    resp = client.get("/tools/get_droplet_vitals/invoke", headers=HEADERS)
    data = resp.json()
    disk = data.get("disk", [])
    assert isinstance(disk, list)
    assert len(disk) >= 1
    for entry in disk:
        for key in ("used", "total", "percent"):
            assert key in entry, f"disk entry missing key: {key}"


def test_invoke_vitals_evolution_log_tail_is_list():
    """evolution_log_tail value is a list."""
    resp = client.get("/tools/get_droplet_vitals/invoke", headers=HEADERS)
    data = resp.json()
    assert isinstance(data.get("evolution_log_tail"), list)


def test_invoke_vitals_json_well_formed():
    """Response content-type is application/json and parses without error."""
    resp = client.get("/tools/get_droplet_vitals/invoke", headers=HEADERS)
    assert "application/json" in resp.headers.get("content-type", "")
    data = resp.json()
    assert isinstance(data, dict)


def test_invoke_vitals_requires_auth():
    """Unauthenticated request returns 401."""
    resp = client.get("/tools/get_droplet_vitals/invoke")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# get_evolution_log_tail helper tests
# ---------------------------------------------------------------------------

def test_get_evolution_log_tail_missing_file():
    """Returns [] when the log file does not exist."""
    from brain.engine.vitals import get_evolution_log_tail
    result = get_evolution_log_tail(log_path="/nonexistent/path/evolution.log")
    assert result == []


def test_get_evolution_log_tail_returns_last_n_lines(tmp_path):
    """File with 15 lines → returns last 10."""
    from brain.engine.vitals import get_evolution_log_tail
    log_file = tmp_path / "evolution.log"
    lines = [f"line {i}" for i in range(1, 16)]
    log_file.write_text("\n".join(lines) + "\n")
    result = get_evolution_log_tail(log_path=str(log_file), n=10)
    assert len(result) == 10
    assert result[0] == "line 6"
    assert result[-1] == "line 15"


def test_get_evolution_log_tail_fewer_than_n_lines(tmp_path):
    """File with 5 lines, n=10 → returns all 5 (no padding)."""
    from brain.engine.vitals import get_evolution_log_tail
    log_file = tmp_path / "evolution.log"
    lines = [f"line {i}" for i in range(1, 6)]
    log_file.write_text("\n".join(lines) + "\n")
    result = get_evolution_log_tail(log_path=str(log_file), n=10)
    assert len(result) == 5
    assert result[0] == "line 1"
    assert result[-1] == "line 5"


def test_get_evolution_log_tail_default_n(tmp_path):
    """Default n=10; file with exactly 10 lines returns all 10."""
    from brain.engine.vitals import get_evolution_log_tail
    log_file = tmp_path / "evolution.log"
    lines = [f"entry {i}" for i in range(1, 11)]
    log_file.write_text("\n".join(lines) + "\n")
    result = get_evolution_log_tail(log_path=str(log_file))
    assert len(result) == 10
