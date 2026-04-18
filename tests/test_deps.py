"""Tests for US-22 (dependency tracking) and US-23 (env rebuild)."""
import logging
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from brain.engine.deps import update_requirements, rebuild_env


# ---------------------------------------------------------------------------
# US-22: update_requirements
# ---------------------------------------------------------------------------

def test_new_dep_appended_to_requirements():
    """AC1: new dep is appended to requirements.txt."""
    with tempfile.TemporaryDirectory() as tmpdir:
        req_path = Path(tmpdir) / "requirements.txt"
        added = update_requirements(["pypdf2"], requirements_path=req_path)
        assert added == ["pypdf2"]
        assert "pypdf2" in req_path.read_text()


def test_duplicate_dep_not_written():
    """AC2: calling twice with same dep results in only one line."""
    with tempfile.TemporaryDirectory() as tmpdir:
        req_path = Path(tmpdir) / "requirements.txt"
        update_requirements(["pypdf2"], requirements_path=req_path)
        added = update_requirements(["pypdf2"], requirements_path=req_path)
        assert added == []
        lines = [l for l in req_path.read_text().splitlines() if l.strip()]
        assert lines.count("pypdf2") == 1


def test_requirements_file_created_if_absent():
    """AC3: file is created when it does not exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        req_path = Path(tmpdir) / "subdir" / "requirements.txt"
        assert not req_path.exists()
        update_requirements(["pypdf2"], requirements_path=req_path)
        assert req_path.exists()
        assert "pypdf2" in req_path.read_text()


def test_multiple_new_deps_all_added():
    """All new deps are written when multiple are provided."""
    with tempfile.TemporaryDirectory() as tmpdir:
        req_path = Path(tmpdir) / "requirements.txt"
        added = update_requirements(["pypdf2", "requests"], requirements_path=req_path)
        assert set(added) == {"pypdf2", "requests"}
        content = req_path.read_text()
        assert "pypdf2" in content
        assert "requests" in content


# ---------------------------------------------------------------------------
# US-23: rebuild integration in request_evolution
# ---------------------------------------------------------------------------

def _make_temp_registry(tmpdir):
    """Helper: return paths for a fresh registry + requirements file."""
    from brain.utils.registry import init_registry
    reg_path = Path(tmpdir) / "registry.json"
    req_path = Path(tmpdir) / "requirements.txt"
    species_dir = Path(tmpdir) / "species"
    init_registry(reg_path)
    return reg_path, req_path, species_dir


def test_rebuild_triggered_when_new_deps_added():
    """AC1: rebuild_env is called when new deps were added."""
    with tempfile.TemporaryDirectory() as tmpdir:
        reg_path, req_path, species_dir = _make_temp_registry(tmpdir)
        with patch("brain.engine.mutator.rebuild_env", return_value=(True, "")) as mock_rebuild, \
             patch("brain.engine.mutator._run_tests", return_value=(True, "")):
            from brain.engine.mutator import request_evolution
            result = request_evolution(
                name="my_skill",
                code="def my_skill(): pass",
                tests="",
                requirements=["pypdf2"],
                species_dir=species_dir,
                registry_path=reg_path,
                requirements_path=req_path,
            )
            assert result.success
            mock_rebuild.assert_called_once()


def test_rebuild_not_triggered_when_no_new_deps():
    """AC3: rebuild_env is NOT called when all deps already present."""
    with tempfile.TemporaryDirectory() as tmpdir:
        reg_path, req_path, species_dir = _make_temp_registry(tmpdir)
        req_path.write_text("pypdf2\n")
        with patch("brain.engine.mutator.rebuild_env", return_value=(True, "")) as mock_rebuild, \
             patch("brain.engine.mutator._run_tests", return_value=(True, "")):
            from brain.engine.mutator import request_evolution
            result = request_evolution(
                name="my_skill",
                code="def my_skill(): pass",
                tests="",
                requirements=["pypdf2"],
                species_dir=species_dir,
                registry_path=reg_path,
                requirements_path=req_path,
            )
            assert result.success
            mock_rebuild.assert_not_called()


def test_rebuild_failure_flags_skill_in_registry():
    """AC2: when rebuild fails, skill status set to 'rebuild_failed'."""
    with tempfile.TemporaryDirectory() as tmpdir:
        reg_path, req_path, species_dir = _make_temp_registry(tmpdir)
        with patch("brain.engine.mutator.rebuild_env", return_value=(False, "pip error")), \
             patch("brain.engine.mutator._run_tests", return_value=(True, "")):
            from brain.engine.mutator import request_evolution
            from brain.utils.registry import read_registry
            result = request_evolution(
                name="my_skill",
                code="def my_skill(): pass",
                tests="",
                requirements=["pypdf2"],
                species_dir=species_dir,
                registry_path=reg_path,
                requirements_path=req_path,
            )
            # Mutation itself succeeds; rebuild failure is non-fatal
            assert result.success
            registry = read_registry(reg_path)
            assert registry["skills"]["my_skill"]["status"] == "rebuild_failed"
            assert "rebuild_error" in registry["skills"]["my_skill"]


def test_rebuild_failure_logged():
    """Rebuild failure is logged as an error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        reg_path, req_path, species_dir = _make_temp_registry(tmpdir)
        with patch("brain.engine.mutator.rebuild_env", return_value=(False, "pip error")), \
             patch("brain.engine.mutator._run_tests", return_value=(True, "")), \
             patch("brain.engine.mutator.logging") as mock_log:
            from brain.engine.mutator import request_evolution
            request_evolution(
                name="my_skill",
                code="def my_skill(): pass",
                tests="",
                requirements=["new_dep"],
                species_dir=species_dir,
                registry_path=reg_path,
                requirements_path=req_path,
            )
            mock_log.error.assert_called_once()
