"""Mutation engine for Darwin-God-MCP — Sprint 2.

Orchestrates: input validation → (Sprint 3: sandbox tests) → species file
promotion → atomic registry update.
"""
import os
import datetime
from pathlib import Path

from brain.utils.registry import read_registry, write_registry, init_registry, REGISTRY_PATH

SPECIES_DIR = Path(__file__).resolve().parent.parent.parent / "memory" / "species"


class ValidationError(Exception):
    pass


class MutationResult:
    def __init__(self, success, skill_name=None, version=None, message=None, error=None):
        self.success = success
        self.skill_name = skill_name
        self.version = version
        self.message = message
        self.error = error

    def to_dict(self):
        return {
            "success": self.success,
            "skill_name": self.skill_name,
            "version": self.version,
            "message": self.message,
            "error": self.error,
        }


def validate_payload(name, code, tests, requirements):
    """Raise ValidationError with descriptive message if any field is invalid."""
    if not name or not isinstance(name, str):
        raise ValidationError("name is required")
    if not isinstance(code, str) or code.strip() == "":
        raise ValidationError("code must be a non-empty string")
    if not isinstance(requirements, list):
        raise ValidationError("requirements must be a list")


def _run_tests(name, code, tests):
    """Placeholder — Sprint 3 replaces this with sandbox execution."""
    return True


def _get_version(registry, name):
    """Return next version number for a skill."""
    if name in registry.get("skills", {}):
        return registry["skills"][name].get("version", 0) + 1
    return 1


def request_evolution(name, code, tests, requirements, species_dir=None, registry_path=None):
    """Orchestrate the mutation pipeline (Sprint 2: no sandbox yet).

    Returns MutationResult.
    """
    # Step 1: Validate inputs
    try:
        validate_payload(name, code, tests, requirements)
    except ValidationError as e:
        return MutationResult(success=False, error=str(e))

    # Step 2: Resolve paths
    if species_dir is None:
        species_dir = SPECIES_DIR
    species_dir = Path(species_dir)
    species_dir.mkdir(parents=True, exist_ok=True)
    species_file = species_dir / f"{name}.py"

    # Step 3: Run tests (Sprint 3 replaces _run_tests with sandbox)
    tests_passed = _run_tests(name, code, tests)
    if not tests_passed:
        return MutationResult(success=False, error="Tests failed")

    # Step 4: Write species file (only on test pass)
    species_file.write_text(code, encoding="utf-8")

    # Step 5: Atomically update registry
    init_registry(registry_path)
    registry = read_registry(registry_path)
    version = _get_version(registry, name)

    entry = {
        "path": str(species_file),
        "entry_point": name,
        "runtime": "python3",
        "dependencies": requirements,
        "evolved_at": datetime.datetime.utcnow().isoformat() + "Z",
        "parent_request": {"name": name, "requirements": requirements},
        "version": version,
        "status": "active",
    }
    registry["skills"][name] = entry
    registry["last_mutation"] = entry["evolved_at"]
    write_registry(registry, registry_path)

    return MutationResult(
        success=True,
        skill_name=name,
        version=version,
        message=f"Skill '{name}' evolved successfully at version {version}",
    )
