"""Tests for brain/engine/mutator.py — US-6, US-7, US-12, US-19, US-20."""
import os
import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch

import pytest

from brain.engine.mutator import (
    request_evolution,
    validate_payload,
    ValidationError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tmp_dirs():
    """Return (species_dir, registry_path) as temp paths."""
    base = tempfile.mkdtemp()
    species_dir = Path(base) / "species"
    species_dir.mkdir()
    registry_path = Path(base) / "registry.json"
    return species_dir, registry_path, base


# ---------------------------------------------------------------------------
# US-6: request_evolution API
# ---------------------------------------------------------------------------

def test_valid_payload_returns_success():
    """US-6 AC1: valid payload → pipeline executes and returns success."""
    sd, rp, base = _tmp_dirs()
    try:
        result = request_evolution("myskill", "def run(): pass", "def test_run(): pass", [], species_dir=sd, registry_path=rp)
        assert result.success is True
    finally:
        shutil.rmtree(base)


def test_all_required_fields_used():
    """US-6 AC2: all four required fields are consumed; no defaults assumed."""
    sd, rp, base = _tmp_dirs()
    try:
        result = request_evolution(
            name="alpha",
            code="def run(): return 42",
            tests="from alpha import run\ndef test_alpha(): assert run() == 42",
            requirements=["requests"],
            species_dir=sd,
            registry_path=rp,
        )
        assert result.success is True
        registry = json.loads(rp.read_text())
        entry = registry["skills"]["alpha"]
        assert entry["dependencies"] == ["requests"]
        assert entry["parent_request"]["name"] == "alpha"
    finally:
        shutil.rmtree(base)


def test_success_returns_skill_name_and_version():
    """US-6 AC3: confirmation message contains skill name and version."""
    sd, rp, base = _tmp_dirs()
    try:
        result = request_evolution("beta", "x = 1", "", [], species_dir=sd, registry_path=rp)
        assert result.success is True
        assert result.skill_name == "beta"
        assert result.version is not None
        assert "beta" in result.message
        assert str(result.version) in result.message
    finally:
        shutil.rmtree(base)


# ---------------------------------------------------------------------------
# US-7: Input validation
# ---------------------------------------------------------------------------

def test_missing_name_raises_error():
    """US-7 AC1: missing name returns error 'name is required'."""
    sd, rp, base = _tmp_dirs()
    try:
        result = request_evolution("", "code", "tests", [], species_dir=sd, registry_path=rp)
        assert result.success is False
        assert "name is required" in result.error
    finally:
        shutil.rmtree(base)


def test_empty_code_rejected_before_write():
    """US-7 AC2: empty code string → error returned, no file written."""
    sd, rp, base = _tmp_dirs()
    try:
        result = request_evolution("myskill", "   ", "tests", [], species_dir=sd, registry_path=rp)
        assert result.success is False
        assert not (sd / "myskill.py").exists()
    finally:
        shutil.rmtree(base)


def test_requirements_not_list_rejected():
    """US-7 AC3: requirements not a list → type-validation error."""
    sd, rp, base = _tmp_dirs()
    try:
        result = request_evolution("myskill", "code", "tests", "requests", species_dir=sd, registry_path=rp)
        assert result.success is False
        assert "requirements" in result.error
    finally:
        shutil.rmtree(base)


# ---------------------------------------------------------------------------
# US-12: Species file promotion
# ---------------------------------------------------------------------------

def test_species_file_written_on_success():
    """US-12 AC1: exact code written to species/{name}.py on success."""
    sd, rp, base = _tmp_dirs()
    code = "def run():\n    return 'hello'\n"
    try:
        result = request_evolution("gamma", code, "", [], species_dir=sd, registry_path=rp)
        assert result.success is True
        species_file = sd / "gamma.py"
        assert species_file.exists()
        assert species_file.read_text(encoding="utf-8") == code
    finally:
        shutil.rmtree(base)


def test_no_file_written_on_test_failure():
    """US-12 AC2: no file written when tests_passed is False (mock the path)."""
    sd, rp, base = _tmp_dirs()
    try:
        # Patch the tests_passed logic inside request_evolution by patching
        # the internal constant used as placeholder
        with patch("brain.engine.mutator._run_tests", return_value=(False, "mocked failure")):
            result = request_evolution("delta", "def run(): pass", "tests", [], species_dir=sd, registry_path=rp)
        assert result.success is False
        assert not (sd / "delta.py").exists()
    finally:
        shutil.rmtree(base)


def test_existing_species_file_overwritten():
    """US-12 AC3: re-evolving overwrites the existing species file."""
    sd, rp, base = _tmp_dirs()
    try:
        request_evolution("epsilon", "v1 = True", "", [], species_dir=sd, registry_path=rp)
        request_evolution("epsilon", "v2 = True", "", [], species_dir=sd, registry_path=rp)
        content = (sd / "epsilon.py").read_text(encoding="utf-8")
        assert "v2 = True" in content
        assert "v1 = True" not in content
    finally:
        shutil.rmtree(base)


# ---------------------------------------------------------------------------
# US-19: Registry entry on successful mutation
# ---------------------------------------------------------------------------

def test_registry_entry_has_all_required_fields():
    """US-19 AC1: entry contains path, entry_point, runtime, dependencies, evolved_at, parent_request."""
    sd, rp, base = _tmp_dirs()
    required = {"path", "entry_point", "runtime", "dependencies", "evolved_at", "parent_request"}
    try:
        request_evolution("zeta", "z = 1", "", ["numpy"], species_dir=sd, registry_path=rp)
        registry = json.loads(rp.read_text())
        entry = registry["skills"]["zeta"]
        assert required.issubset(entry.keys())
    finally:
        shutil.rmtree(base)


def test_registry_entry_fields_non_null():
    """US-19 AC2: all required entry fields are non-null."""
    sd, rp, base = _tmp_dirs()
    required = ["path", "entry_point", "runtime", "dependencies", "evolved_at", "parent_request"]
    try:
        request_evolution("eta", "e = 1", "", [], species_dir=sd, registry_path=rp)
        registry = json.loads(rp.read_text())
        entry = registry["skills"]["eta"]
        for field in required:
            assert entry[field] is not None, f"Field '{field}' is None"
    finally:
        shutil.rmtree(base)


def test_re_evolution_replaces_not_duplicates():
    """US-19 AC3: evolving the same skill twice yields exactly one registry entry."""
    sd, rp, base = _tmp_dirs()
    try:
        request_evolution("theta", "t = 1", "", [], species_dir=sd, registry_path=rp)
        request_evolution("theta", "t = 2", "", [], species_dir=sd, registry_path=rp)
        registry = json.loads(rp.read_text())
        assert list(registry["skills"].keys()).count("theta") == 1
    finally:
        shutil.rmtree(base)


# ---------------------------------------------------------------------------
# US-20: Atomic registry writes
# ---------------------------------------------------------------------------

def test_registry_write_uses_atomic_pattern():
    """US-20 AC2: write_registry source uses os.replace (inspect source)."""
    import inspect
    from brain.utils import registry as reg_module
    source = inspect.getsource(reg_module.write_registry)
    assert "os.replace(" in source


def test_atomic_write_no_tmp_file_left():
    """US-20: after a successful write, no .tmp file remains next to registry."""
    sd, rp, base = _tmp_dirs()
    try:
        request_evolution("iota", "i = 1", "", [], species_dir=sd, registry_path=rp)
        tmp = rp.with_suffix(".json.tmp")
        assert not tmp.exists(), f"Temp file still present: {tmp}"
    finally:
        shutil.rmtree(base)
