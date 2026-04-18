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


# ---------------------------------------------------------------------------
# ENH-US5: Senescence Fields
# ---------------------------------------------------------------------------

class TestSenescenceFields:
    def _base_registry(self, skills=None):
        return {
            "organism_version": "1.0.0",
            "last_mutation": None,
            "skills": skills or {},
        }

    def test_upgrade_senescence_fields_adds_defaults(self, tmp_path):
        """AC-1: All skills get senescence defaults after upgrade."""
        from brain.utils.registry import upgrade_senescence_fields, write_registry
        reg_path = tmp_path / "registry.json"
        registry = self._base_registry({
            "skill_a": {"path": "/a.py", "status": "active"},
            "skill_b": {"path": "/b.py", "status": "active"},
        })
        write_registry(registry, registry_path=reg_path)
        updated = upgrade_senescence_fields(registry, registry_path=reg_path)
        for name in ("skill_a", "skill_b"):
            skill = updated["skills"][name]
            assert skill["total_calls"] == 0
            assert skill["success_count"] == 0
            assert skill["failure_count"] == 0
            assert skill["last_used_at"] is not None  # defaulted to upgrade timestamp

    def test_upgrade_senescence_fields_does_not_overwrite_existing(self, tmp_path):
        """Existing senescence values are preserved on upgrade."""
        from brain.utils.registry import upgrade_senescence_fields, write_registry
        reg_path = tmp_path / "registry.json"
        registry = self._base_registry({
            "skill_x": {
                "path": "/x.py",
                "last_used_at": "2024-01-01T00:00:00Z",
                "total_calls": 5,
                "success_count": 4,
                "failure_count": 1,
            },
        })
        write_registry(registry, registry_path=reg_path)
        updated = upgrade_senescence_fields(registry, registry_path=reg_path)
        skill = updated["skills"]["skill_x"]
        assert skill["last_used_at"] == "2024-01-01T00:00:00Z"
        assert skill["total_calls"] == 5

    def test_record_invocation_success_increments_counts(self, tmp_path):
        """AC-2: Successful invocation increments success_count and total_calls."""
        from brain.utils.registry import record_invocation, write_registry
        reg_path = tmp_path / "registry.json"
        registry = self._base_registry({
            "my_skill": {"path": "/s.py", "total_calls": 2, "success_count": 2, "failure_count": 0},
        })
        write_registry(registry, registry_path=reg_path)
        updated = record_invocation("my_skill", success=True, registry_path=reg_path)
        skill = updated["skills"]["my_skill"]
        assert skill["total_calls"] == 3
        assert skill["success_count"] == 3
        assert skill["failure_count"] == 0
        assert skill["last_used_at"] is not None

    def test_record_invocation_failure_increments_failure_count(self, tmp_path):
        """AC-2: Failed invocation increments failure_count and total_calls."""
        from brain.utils.registry import record_invocation, write_registry
        reg_path = tmp_path / "registry.json"
        registry = self._base_registry({
            "my_skill": {"path": "/s.py", "total_calls": 1, "success_count": 1, "failure_count": 0},
        })
        write_registry(registry, registry_path=reg_path)
        updated = record_invocation("my_skill", success=False, registry_path=reg_path)
        skill = updated["skills"]["my_skill"]
        assert skill["total_calls"] == 2
        assert skill["success_count"] == 1
        assert skill["failure_count"] == 1

    def test_record_invocation_unknown_skill_returns_unchanged(self, tmp_path):
        """record_invocation on missing skill returns registry unchanged."""
        from brain.utils.registry import record_invocation, write_registry
        reg_path = tmp_path / "registry.json"
        registry = self._base_registry({})
        write_registry(registry, registry_path=reg_path)
        updated = record_invocation("ghost_skill", success=True, registry_path=reg_path)
        assert "ghost_skill" not in updated["skills"]

    def test_compute_success_rate_calculation(self):
        """AC-3: 7 successes, 3 failures → success_rate = 0.7."""
        from brain.utils.registry import compute_success_rate
        skill = {"total_calls": 10, "success_count": 7, "failure_count": 3}
        assert compute_success_rate(skill) == pytest.approx(0.7)

    def test_compute_success_rate_no_calls_returns_one(self):
        """AC-3: No calls yet → success_rate = 1.0 (benefit of the doubt)."""
        from brain.utils.registry import compute_success_rate
        skill = {"total_calls": 0, "success_count": 0, "failure_count": 0}
        assert compute_success_rate(skill) == 1.0

    def test_compute_success_rate_all_success(self):
        from brain.utils.registry import compute_success_rate
        skill = {"total_calls": 5, "success_count": 5, "failure_count": 0}
        assert compute_success_rate(skill) == 1.0

    def test_discover_species_preserves_senescence_fields(self, tmp_path):
        """Existing senescence data survives a discover_species run."""
        from brain.utils.registry import discover_species, write_registry
        species_dir = tmp_path / "species"
        species_dir.mkdir()
        (species_dir / "my_tool.py").write_text("def my_tool(): pass")

        reg_path = tmp_path / "registry.json"
        registry = {
            "organism_version": "1.0.0",
            "last_mutation": None,
            "skills": {
                "my_tool": {
                    "path": str(species_dir / "my_tool.py"),
                    "entry_point": "my_tool",
                    "runtime": "python3",
                    "dependencies": [],
                    "evolved_at": None,
                    "status": "active",
                    "last_used_at": "2024-06-01T12:00:00Z",
                    "total_calls": 42,
                    "success_count": 40,
                    "failure_count": 2,
                }
            },
        }
        write_registry(registry, registry_path=reg_path)
        updated = discover_species(species_dir=species_dir, registry_path=reg_path)
        skill = updated["skills"]["my_tool"]
        assert skill["last_used_at"] == "2024-06-01T12:00:00Z"
        assert skill["total_calls"] == 42
        assert skill["success_count"] == 40
        assert skill["failure_count"] == 2

