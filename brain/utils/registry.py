"""Registry utilities for the Darwin-God-MCP organism.

Provides bootstrap (init_registry), schema-validated reads (read_registry),
and atomic writes (write_registry) for memory/dna/registry.json.
"""
import json
import os
from pathlib import Path
from typing import Optional

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

    Raises:
        SchemaError: if any required field is missing or has an invalid type.
    """
    path = Path(registry_path) if registry_path is not None else REGISTRY_PATH
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
    """Atomically write *data* to registry.json (write to .tmp then os.replace)."""
    path = Path(registry_path) if registry_path is not None else REGISTRY_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
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
            **({k: v for k, v in existing.items() if k not in
                ("path", "entry_point", "runtime", "dependencies", "evolved_at", "status")}),
        }

    write_registry(registry, registry_path)
    return registry
