"""Registry utilities for the Darwin-MCP organism.

Provides bootstrap (init_registry), schema-validated reads (read_registry),
and atomic writes (write_registry) for memory/dna/registry.json.

All reads and writes are protected by an exclusive/shared fcntl file lock
(registry.json.lock) to serialise concurrent mutations without data loss.
"""
import contextlib
import datetime
import json
import os
from pathlib import Path
from typing import Optional

try:
    import fcntl as _fcntl
    _HAVE_FCNTL = True
except ImportError:  # Windows
    _HAVE_FCNTL = False

# ---------------------------------------------------------------------------
# Path resolution — no hardcoded absolute paths
# ---------------------------------------------------------------------------

REGISTRY_PATH: Path = (
    Path(__file__).resolve().parent.parent.parent / "memory" / "dna" / "registry.json"
)

REGISTRY_SCHEMA: dict = {
    "organism_version": "1.0.0",
    "last_mutation": None,
    "skills": {},
}

_REQUIRED_FIELDS = ("organism_version", "last_mutation", "skills")


# ---------------------------------------------------------------------------
# File locking — US-H1
# ---------------------------------------------------------------------------

@contextlib.contextmanager
def _registry_lock(path: Path, exclusive: bool = False):
    """Acquire a shared (read) or exclusive (write) flock on *path*.lock.

    Falls back to a no-op context manager on platforms that lack fcntl
    (e.g., Windows) so the code runs everywhere.
    """
    if not _HAVE_FCNTL:
        yield
        return

    lock_path = path.with_suffix(".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_flag = _fcntl.LOCK_EX if exclusive else _fcntl.LOCK_SH
    with open(lock_path, "w") as _lf:
        _fcntl.flock(_lf, lock_flag)
        try:
            yield
        finally:
            _fcntl.flock(_lf, _fcntl.LOCK_UN)


SENESCENCE_DEFAULTS: dict = {
    "last_used_at": None,
    "total_calls": 0,
    "success_count": 0,
    "failure_count": 0,
}


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------

class SchemaError(Exception):
    """Raised when registry.json does not conform to the expected schema."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def init_registry(registry_path: Optional[Path] = None) -> None:
    """Create registry.json with the canonical schema if it does not already exist."""
    path = Path(registry_path) if registry_path is not None else REGISTRY_PATH
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    write_registry(dict(REGISTRY_SCHEMA), registry_path=path)


def read_registry(registry_path: Optional[Path] = None) -> dict:
    """Read registry.json, validate its schema, and return parsed data.

    Acquires a shared file lock before reading so concurrent writes cannot
    produce a torn read.

    Raises:
        SchemaError: if any required field is missing or has an invalid type.
    """
    path = Path(registry_path) if registry_path is not None else REGISTRY_PATH
    with _registry_lock(path, exclusive=False):
        data = json.loads(path.read_text(encoding="utf-8"))

    for field in _REQUIRED_FIELDS:
        if field not in data:
            raise SchemaError(
                f"Registry schema error: required field '{field}' is missing."
            )

    if not isinstance(data["skills"], dict):
        raise SchemaError(
            f"Registry schema error: 'skills' must be a JSON object (dict), "
            f"got {type(data['skills']).__name__!r}."
        )

    return data


def write_registry(data: dict, registry_path: Optional[Path] = None) -> None:
    """Atomically write *data* to registry.json (write to .tmp then os.replace).

    Holds an exclusive file lock for the duration of the write so concurrent
    reads and writes are serialised without data loss.
    """
    path = Path(registry_path) if registry_path is not None else REGISTRY_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with _registry_lock(path, exclusive=True):
        tmp_path = path.with_suffix(".json.tmp")
        tmp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        os.replace(tmp_path, path)


def discover_species(
    species_dir: Optional[Path] = None,
    registry_path: Optional[Path] = None,
) -> dict:
    """Walk *species_dir* and upsert each .py file into registry.json.

    Idempotent: running twice produces the same result.
    Creates registry.json if absent.
    """
    if species_dir is None:
        species_dir = Path(__file__).resolve().parent.parent.parent / "memory" / "species"
    species_dir = Path(species_dir)

    init_registry(registry_path)
    registry = read_registry(registry_path)

    if not species_dir.exists():
        return registry

    for py_file in species_dir.glob("*.py"):
        name = py_file.stem
        existing = registry["skills"].get(name, {})
        registry["skills"][name] = {
            "path": str(py_file),
            "entry_point": name,
            "runtime": existing.get("runtime", "python3"),
            "dependencies": existing.get("dependencies", []),
            "evolved_at": existing.get("evolved_at"),
            "status": existing.get("status", "active"),
            "last_used_at": existing.get("last_used_at"),
            "total_calls": existing.get("total_calls", 0),
            "success_count": existing.get("success_count", 0),
            "failure_count": existing.get("failure_count", 0),
            **({k: v for k, v in existing.items() if k not in
                ("path", "entry_point", "runtime", "dependencies", "evolved_at", "status",
                 "last_used_at", "total_calls", "success_count", "failure_count")}),
        }

    write_registry(registry, registry_path)
    return registry


# ---------------------------------------------------------------------------
# Senescence tracking
# ---------------------------------------------------------------------------

def upgrade_senescence_fields(registry: dict, registry_path: Optional[Path] = None) -> dict:
    """Add missing senescence fields to all existing skills with defaults.

    last_used_at defaults to current UTC timestamp for existing skills.
    Writes updated registry atomically.
    Returns the updated registry.
    """
    now = datetime.datetime.utcnow().isoformat() + "Z"
    for skill in registry.get("skills", {}).values():
        if "last_used_at" not in skill:
            skill["last_used_at"] = now
        if "total_calls" not in skill:
            skill["total_calls"] = 0
        if "success_count" not in skill:
            skill["success_count"] = 0
        if "failure_count" not in skill:
            skill["failure_count"] = 0
    write_registry(registry, registry_path)
    return registry


def record_invocation(skill_name: str, success: bool, registry_path: Optional[Path] = None) -> dict:
    """Update last_used_at, total_calls, and success/failure counts for skill_name.

    Creates senescence fields if missing.
    Writes registry atomically.
    Returns updated registry.
    """
    path = Path(registry_path) if registry_path is not None else REGISTRY_PATH
    registry = read_registry(path)
    skill = registry["skills"].get(skill_name)
    if skill is None:
        return registry

    now = datetime.datetime.utcnow().isoformat() + "Z"
    skill["last_used_at"] = now
    skill["total_calls"] = skill.get("total_calls", 0) + 1
    if success:
        skill["success_count"] = skill.get("success_count", 0) + 1
    else:
        skill["failure_count"] = skill.get("failure_count", 0) + 1

    write_registry(registry, path)
    return registry


def compute_success_rate(skill: dict) -> float:
    """Compute success_rate = success_count / (success_count + failure_count).

    Returns 1.0 if total_calls == 0 (benefit of the doubt — no data yet).
    """
    total = skill.get("total_calls", 0)
    if total == 0:
        return 1.0
    success = skill.get("success_count", 0)
    failure = skill.get("failure_count", 0)
    denominator = success + failure
    if denominator == 0:
        return 1.0
    return success / denominator
