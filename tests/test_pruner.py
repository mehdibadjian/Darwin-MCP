"""Tests for brain/engine/pruner.py — ENH-US6: Skill Pruning Policy & Automation."""
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

from brain.engine.pruner import (
    evaluate_skill,
    run_pruner,
    PrunerResult,
    SENESCENCE_SUCCESS_RATE_THRESHOLD,
    SENESCENCE_UNUSED_DAYS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_skill(
    name="test_skill",
    status="active",
    success_count=0,
    failure_count=0,
    total_calls=0,
    last_used_at=None,
):
    return {
        "name": name,
        "status": status,
        "success_count": success_count,
        "failure_count": failure_count,
        "total_calls": total_calls,
        "last_used_at": last_used_at,
        "path": f"memory/species/{name}.py",
        "entry_point": name,
        "runtime": "python3",
        "dependencies": [],
    }


def _make_registry(skills: dict) -> dict:
    return {
        "organism_version": "1.0.0",
        "last_mutation": None,
        "skills": skills,
    }


def _days_ago_iso(days: int) -> str:
    dt = datetime.now(timezone.utc) - timedelta(days=days)
    return dt.isoformat()


def _setup_skill_fs(tmp_path: Path, name: str, registry: dict):
    """Write registry.json and an empty species .py file for *name*."""
    dna_dir = tmp_path / "dna"
    dna_dir.mkdir(parents=True)
    registry_path = dna_dir / "registry.json"
    registry_path.write_text(json.dumps(registry), encoding="utf-8")

    species_dir = tmp_path / "species"
    species_dir.mkdir(parents=True)
    (species_dir / f"{name}.py").write_text(f"# {name}\n", encoding="utf-8")

    archive_dir = tmp_path / "archive"
    archive_dir.mkdir(parents=True)

    return registry_path, species_dir, archive_dir


# ---------------------------------------------------------------------------
# evaluate_skill — unit tests
# ---------------------------------------------------------------------------

def test_evaluate_skill_low_success_rate():
    skill = _make_skill(success_count=3, failure_count=7, total_calls=10)
    should_archive, reason = evaluate_skill(skill)
    assert should_archive is True
    assert "success_rate" in reason.lower() or "rate" in reason.lower()


def test_evaluate_skill_good_success_rate():
    skill = _make_skill(success_count=8, failure_count=2, total_calls=10)
    should_archive, reason = evaluate_skill(skill)
    assert should_archive is False


def test_evaluate_skill_unused_31_days():
    skill = _make_skill(
        last_used_at=_days_ago_iso(31),
        total_calls=5,
        success_count=5,
        failure_count=0,
    )
    now = datetime.now(timezone.utc)
    should_archive, reason = evaluate_skill(skill, now=now)
    assert should_archive is True
    assert "unused" in reason.lower() or "days" in reason.lower() or "stale" in reason.lower()


def test_evaluate_skill_used_recently():
    skill = _make_skill(
        last_used_at=_days_ago_iso(5),
        total_calls=5,
        success_count=5,
        failure_count=0,
    )
    now = datetime.now(timezone.utc)
    should_archive, reason = evaluate_skill(skill, now=now)
    assert should_archive is False


def test_evaluate_skill_toxic_always_archived():
    skill = _make_skill(status="Toxic", success_count=10, failure_count=0, total_calls=10)
    should_archive, reason = evaluate_skill(skill)
    assert should_archive is True
    assert "toxic" in reason.lower()


def test_evaluate_skill_no_data_kept():
    skill = _make_skill(last_used_at=None, total_calls=0, success_count=0, failure_count=0)
    should_archive, reason = evaluate_skill(skill)
    assert should_archive is False


# ---------------------------------------------------------------------------
# run_pruner — integration tests
# ---------------------------------------------------------------------------

def test_run_pruner_archives_low_success_skill(tmp_path):
    name = "weak_skill"
    skill = _make_skill(
        name=name,
        success_count=2,
        failure_count=8,
        total_calls=10,
        last_used_at=_days_ago_iso(1),
    )
    registry = _make_registry({name: skill})
    registry_path, species_dir, archive_dir = _setup_skill_fs(tmp_path, name, registry)

    result = run_pruner(
        registry_path=registry_path,
        species_dir=species_dir,
        archive_dir=archive_dir,
    )

    assert name in result.archived
    assert name not in result.kept
    # Species file moved to archive
    assert not (species_dir / f"{name}.py").exists()
    archive_files = list(archive_dir.glob(f"{name}_*.py"))
    assert len(archive_files) == 1
    # Registry updated
    updated = json.loads(registry_path.read_text())
    assert updated["skills"][name]["status"] == "archived"


def test_run_pruner_archives_stale_skill(tmp_path):
    name = "stale_skill"
    skill = _make_skill(
        name=name,
        success_count=5,
        failure_count=0,
        total_calls=5,
        last_used_at=_days_ago_iso(31),
    )
    registry = _make_registry({name: skill})
    registry_path, species_dir, archive_dir = _setup_skill_fs(tmp_path, name, registry)

    result = run_pruner(
        registry_path=registry_path,
        species_dir=species_dir,
        archive_dir=archive_dir,
    )

    assert name in result.archived
    assert not (species_dir / f"{name}.py").exists()
    updated = json.loads(registry_path.read_text())
    assert updated["skills"][name]["status"] == "archived"


def test_run_pruner_dry_run_does_not_move_files(tmp_path):
    name = "dry_skill"
    skill = _make_skill(
        name=name,
        success_count=1,
        failure_count=9,
        total_calls=10,
        last_used_at=_days_ago_iso(1),
    )
    registry = _make_registry({name: skill})
    registry_path, species_dir, archive_dir = _setup_skill_fs(tmp_path, name, registry)

    original_registry = registry_path.read_text()
    result = run_pruner(
        registry_path=registry_path,
        species_dir=species_dir,
        archive_dir=archive_dir,
        dry_run=True,
    )

    assert result.dry_run is True
    # File NOT moved
    assert (species_dir / f"{name}.py").exists()
    # Registry NOT changed
    assert registry_path.read_text() == original_registry


def test_run_pruner_returns_result_with_lists(tmp_path):
    bad = "bad_skill"
    good = "good_skill"
    skills = {
        bad: _make_skill(
            name=bad,
            success_count=1,
            failure_count=9,
            total_calls=10,
            last_used_at=_days_ago_iso(1),
        ),
        good: _make_skill(
            name=good,
            success_count=9,
            failure_count=1,
            total_calls=10,
            last_used_at=_days_ago_iso(1),
        ),
    }
    registry = _make_registry(skills)
    dna_dir = tmp_path / "dna"
    dna_dir.mkdir()
    registry_path = dna_dir / "registry.json"
    registry_path.write_text(json.dumps(registry))
    species_dir = tmp_path / "species"
    species_dir.mkdir()
    (species_dir / f"{bad}.py").write_text("# bad\n")
    (species_dir / f"{good}.py").write_text("# good\n")
    archive_dir = tmp_path / "archive"
    archive_dir.mkdir()

    result = run_pruner(
        registry_path=registry_path,
        species_dir=species_dir,
        archive_dir=archive_dir,
    )

    assert bad in result.archived
    assert good in result.kept
    assert isinstance(result, PrunerResult)


def test_run_pruner_only_active_skills_archived(tmp_path):
    already = "already_archived"
    skill = _make_skill(
        name=already,
        status="archived",
        success_count=0,
        failure_count=10,
        total_calls=10,
        last_used_at=_days_ago_iso(60),
    )
    registry = _make_registry({already: skill})
    dna_dir = tmp_path / "dna"
    dna_dir.mkdir()
    registry_path = dna_dir / "registry.json"
    registry_path.write_text(json.dumps(registry))
    species_dir = tmp_path / "species"
    species_dir.mkdir()
    archive_dir = tmp_path / "archive"
    archive_dir.mkdir()

    result = run_pruner(
        registry_path=registry_path,
        species_dir=species_dir,
        archive_dir=archive_dir,
    )

    assert already not in result.archived
    assert already not in result.kept  # skipped entirely
