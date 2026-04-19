"""Mutation engine for Darwin-MCP — Sprint 2/3.

Orchestrates: input validation → pytest sandbox tests → species file
promotion → atomic registry update → dependency tracking + env rebuild.
"""
import logging
import sys
import datetime
from pathlib import Path

from brain.utils.registry import read_registry, write_registry, init_registry, record_invocation, REGISTRY_PATH
from brain.engine.deps import update_requirements, rebuild_env

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


def _run_tests(python_bin, test_code, code, name, work_dir=None):
    """Run tests in sandbox using pytest_runner. Returns (passed: bool, error: str)."""
    from brain.engine.pytest_runner import run_pytest
    result = run_pytest(python_bin, test_code, code, name, work_dir)
    if result.passed:
        return True, ""
    return False, result.format_error()


def _get_version(registry, name):
    """Return next version number for a skill."""
    if name in registry.get("skills", {}):
        return registry["skills"][name].get("version", 0) + 1
    return 1


def request_evolution(name, code, tests, requirements, species_dir=None, registry_path=None, python_bin=None, requirements_path=None, recursion_depth=0, git_commit=False, memory_dir=None):
    """Orchestrate the mutation pipeline.

    Returns MutationResult.
    """
    from brain.engine.guard import check_recursion_depth, RecursionLimitError
    try:
        check_recursion_depth(recursion_depth, name)
    except RecursionLimitError as e:
        return MutationResult(
            success=False,
            error=f"Circuit breaker triggered: recursion depth {e.depth} for skill '{e.skill_name}'",
        )

    if python_bin is None:
        python_bin = sys.executable
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

    # Step 3: Run tests in sandbox
    tests_passed, pytest_error = _run_tests(python_bin, tests, code, name)
    if not tests_passed:
        return MutationResult(success=False, error=pytest_error)

    # Step 4: Write species file (only on test pass)
    species_file.write_text(code, encoding="utf-8")

    # Step 5: Atomically update registry
    init_registry(registry_path)
    old_registry = read_registry(registry_path)
    registry = {**old_registry, "skills": dict(old_registry.get("skills", {}))}
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

    # Step 6: Dependency tracking + env rebuild (US-22, US-23)
    added_deps = update_requirements(requirements, requirements_path=requirements_path)
    if added_deps:
        success, err = rebuild_env(requirements_path=requirements_path)
        if not success:
            registry = read_registry(registry_path)
            if name in registry["skills"]:
                registry["skills"][name]["status"] = "rebuild_failed"
                registry["skills"][name]["rebuild_error"] = err
                write_registry(registry, registry_path)
            logging.error(f"Rebuild failed for {name}: {err}")

    # Step 7: Git commit + push (US-13–US-16)
    # Registry is written before git add so the commit bundles both the species
    # file and the updated registry.json atomically. On unrecoverable push
    # failure, the registry is reverted to its pre-mutation snapshot to avoid
    # creating a Ghost Skill (US-H3).
    if git_commit:
        from brain.utils.git_manager import commit_and_push, PushRejectedError, RebaseError
        try:
            commit_and_push(name, version, memory_dir=memory_dir)
        except (PushRejectedError, RebaseError) as e:
            logging.warning(f"git push failed for {name} v{version}, reverting registry: {e}")
            try:
                write_registry(old_registry, registry_path)
            except Exception as revert_err:
                logging.error(f"registry revert also failed for {name}: {revert_err}")
            return MutationResult(
                success=False,
                error=f"Git push failed and registry was reverted: {e}",
            )
        except Exception as e:
            logging.warning(f"git push failed for {name} v{version}: {e}")

    # Step 8: Record invocation stats (ENH-US5) — only when memory_dir is set
    if memory_dir is not None:
        try:
            record_invocation(name, success=True, registry_path=registry_path)
        except Exception as e:
            logging.warning(f"record_invocation failed for {name}: {e}")

    return MutationResult(
        success=True,
        skill_name=name,
        version=version,
        message=f"Skill '{name}' evolved successfully at version {version}",
    )
