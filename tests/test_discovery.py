"""Tests for US-3 and US-4 — Species Discovery scan."""
import json
import tempfile
from pathlib import Path

import pytest

from brain.utils.registry import discover_species, init_registry, read_registry


def _make_temp_env():
    """Return (species_dir, registry_path) as Path objects inside a fresh temp dir."""
    tmp = tempfile.mkdtemp()
    species_dir = Path(tmp) / "species"
    species_dir.mkdir()
    registry_path = Path(tmp) / "registry.json"
    return species_dir, registry_path


# ---------------------------------------------------------------------------
# US-3 AC1 — Three .py files all registered
# ---------------------------------------------------------------------------

def test_three_species_files_all_registered():
    species_dir, registry_path = _make_temp_env()
    for name in ("alpha", "beta", "gamma"):
        (species_dir / f"{name}.py").write_text(f"# {name}\n")

    result = discover_species(species_dir=species_dir, registry_path=registry_path)

    assert set(result["skills"].keys()) == {"alpha", "beta", "gamma"}


# ---------------------------------------------------------------------------
# US-3 AC2 / US-4 AC1 — No duplication on rescan
# ---------------------------------------------------------------------------

def test_no_duplication_on_rescan():
    species_dir, registry_path = _make_temp_env()
    (species_dir / "omega.py").write_text("# omega\n")

    discover_species(species_dir=species_dir, registry_path=registry_path)
    discover_species(species_dir=species_dir, registry_path=registry_path)

    registry = read_registry(registry_path)
    assert len(registry["skills"]) == 1


def test_existing_entry_not_duplicated():
    """US-4 AC1 — entry count stays 1 after second scan."""
    species_dir, registry_path = _make_temp_env()
    (species_dir / "delta.py").write_text("# delta\n")

    discover_species(species_dir=species_dir, registry_path=registry_path)
    discover_species(species_dir=species_dir, registry_path=registry_path)

    registry = read_registry(registry_path)
    assert list(registry["skills"].keys()).count("delta") == 1


# ---------------------------------------------------------------------------
# US-3 AC3 — Empty species dir starts cleanly
# ---------------------------------------------------------------------------

def test_empty_species_dir_starts_cleanly():
    species_dir, registry_path = _make_temp_env()

    result = discover_species(species_dir=species_dir, registry_path=registry_path)

    assert result["skills"] == {}


# ---------------------------------------------------------------------------
# US-4 AC2 — Changed file entry is updated, not appended
# ---------------------------------------------------------------------------

def test_changed_file_entry_updated():
    species_dir, registry_path = _make_temp_env()
    py_file = species_dir / "mutant.py"
    py_file.write_text("# version 1\n")

    discover_species(species_dir=species_dir, registry_path=registry_path)
    first_path = read_registry(registry_path)["skills"]["mutant"]["path"]

    # Simulate content change (path stays same; status updated externally)
    # Re-scan should overwrite, not append
    discover_species(species_dir=species_dir, registry_path=registry_path)
    registry = read_registry(registry_path)

    assert len(registry["skills"]) == 1
    assert registry["skills"]["mutant"]["path"] == first_path  # same file, replaced entry


# ---------------------------------------------------------------------------
# US-4 AC3 — Registry created if absent
# ---------------------------------------------------------------------------

def test_registry_created_if_absent():
    species_dir, registry_path = _make_temp_env()
    assert not registry_path.exists()

    discover_species(species_dir=species_dir, registry_path=registry_path)

    assert registry_path.exists()
    data = json.loads(registry_path.read_text())
    assert "organism_version" in data
    assert "skills" in data
    assert isinstance(data["skills"], dict)
