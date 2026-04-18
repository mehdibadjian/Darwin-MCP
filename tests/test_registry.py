"""Tests for US-17 (Registry Initialization) and US-18 (Schema Validation)."""
import json
import os
import pytest
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data))


# ---------------------------------------------------------------------------
# US-17: Registry Initialization and Bootstrap
# ---------------------------------------------------------------------------

class TestRegistryInit:
    def test_creates_registry_when_absent(self, tmp_path):
        """AC-1: creates registry.json with correct schema when file is absent."""
        from brain.utils.registry import init_registry, REGISTRY_SCHEMA
        reg_path = tmp_path / "registry.json"
        assert not reg_path.exists()
        init_registry(registry_path=reg_path)
        assert reg_path.exists()
        data = json.loads(reg_path.read_text())
        assert "organism_version" in data
        assert "last_mutation" in data
        assert "skills" in data
        assert isinstance(data["skills"], dict)

    def test_does_not_overwrite_existing_registry(self, tmp_path):
        """AC-2: does not overwrite an existing valid registry.json."""
        from brain.utils.registry import init_registry
        reg_path = tmp_path / "registry.json"
        original = {
            "organism_version": "9.9.9",
            "last_mutation": "2099-01-01",
            "skills": {"existing_skill": {}},
        }
        _write(reg_path, original)
        init_registry(registry_path=reg_path)
        data = json.loads(reg_path.read_text())
        assert data["organism_version"] == "9.9.9"
        assert "existing_skill" in data["skills"]

    def test_registry_path_uses_pathlib_no_hardcoded_absolute(self):
        """AC-3: REGISTRY_PATH is a pathlib.Path and constructed relative to __file__."""
        from brain.utils import registry as reg_module
        import inspect

        assert isinstance(reg_module.REGISTRY_PATH, Path)

        source = inspect.getsource(reg_module)
        # Must not contain hardcoded /Users or /home absolute paths
        assert "/Users/" not in source.replace("# ", "")
        assert "/home/" not in source.replace("# ", "")


# ---------------------------------------------------------------------------
# US-18: Registry Schema Validation on Every Read
# ---------------------------------------------------------------------------

class TestRegistrySchemaValidation:
    def test_missing_skills_key_raises_schema_error(self, tmp_path):
        """AC-1: missing 'skills' key raises SchemaError before tool loading."""
        from brain.utils.registry import read_registry, SchemaError
        reg_path = tmp_path / "registry.json"
        _write(reg_path, {"organism_version": "1.0.0", "last_mutation": None})
        with pytest.raises(SchemaError, match="skills"):
            read_registry(registry_path=reg_path)

    def test_skills_not_dict_raises_schema_error(self, tmp_path):
        """AC-2: skills present but not a dict raises SchemaError."""
        from brain.utils.registry import read_registry, SchemaError
        reg_path = tmp_path / "registry.json"
        _write(reg_path, {"organism_version": "1.0.0", "last_mutation": None, "skills": "bad"})
        with pytest.raises(SchemaError, match="skills"):
            read_registry(registry_path=reg_path)

    def test_missing_organism_version_raises_schema_error(self, tmp_path):
        """AC-2: missing 'organism_version' raises SchemaError."""
        from brain.utils.registry import read_registry, SchemaError
        reg_path = tmp_path / "registry.json"
        _write(reg_path, {"last_mutation": None, "skills": {}})
        with pytest.raises(SchemaError, match="organism_version"):
            read_registry(registry_path=reg_path)

    def test_valid_registry_loads_normally(self, tmp_path):
        """AC-3: valid registry is read without errors."""
        from brain.utils.registry import read_registry
        reg_path = tmp_path / "registry.json"
        payload = {"organism_version": "1.0.0", "last_mutation": None, "skills": {"s1": {}}}
        _write(reg_path, payload)
        data = read_registry(registry_path=reg_path)
        assert data["skills"] == {"s1": {}}

    def test_schema_error_message_identifies_field(self, tmp_path):
        """AC-2: the error message clearly names the missing/invalid field."""
        from brain.utils.registry import read_registry, SchemaError
        reg_path = tmp_path / "registry.json"
        _write(reg_path, {"organism_version": "1.0.0", "skills": {}})  # missing last_mutation
        with pytest.raises(SchemaError, match="last_mutation"):
            read_registry(registry_path=reg_path)


# ---------------------------------------------------------------------------
# write_registry (atomic write)
# ---------------------------------------------------------------------------

class TestWriteRegistry:
    def test_atomic_write_creates_file(self, tmp_path):
        from brain.utils.registry import write_registry
        reg_path = tmp_path / "registry.json"
        data = {"organism_version": "1.0.0", "last_mutation": None, "skills": {}}
        write_registry(data, registry_path=reg_path)
        assert reg_path.exists()
        assert json.loads(reg_path.read_text()) == data

    def test_no_tmp_file_left_behind(self, tmp_path):
        from brain.utils.registry import write_registry
        reg_path = tmp_path / "registry.json"
        data = {"organism_version": "1.0.0", "last_mutation": None, "skills": {}}
        write_registry(data, registry_path=reg_path)
        assert not (tmp_path / "registry.json.tmp").exists()
