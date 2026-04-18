"""Darwinian Pruning — Skill Senescence & Garbage Collection (ENH-US6)."""
import logging
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from brain.utils.registry import read_registry, write_registry, compute_success_rate

logger = logging.getLogger(__name__)

SENESCENCE_SUCCESS_RATE_THRESHOLD = 0.5   # below this → archive
SENESCENCE_UNUSED_DAYS = 30               # unused longer than this → archive
ARCHIVE_DIR_NAME = "archive"


class PrunerResult:
    def __init__(self):
        self.archived: list = []
        self.kept: list = []
        self.dry_run: bool = False
        self.errors: list = []


def evaluate_skill(skill: dict, now: Optional[datetime] = None) -> tuple:
    """Return (should_archive: bool, reason: str) for a skill entry.

    Checks (in order):
    1. status="Toxic" → always archive
    2. success_rate < SENESCENCE_SUCCESS_RATE_THRESHOLD (only if there are calls)
    3. last_used_at older than SENESCENCE_UNUSED_DAYS days
    4. No data yet (last_used_at=None, total_calls=0) → keep
    """
    if skill.get("status") == "Toxic":
        return True, "toxic status"

    # Benefit of the doubt — no usage data yet
    if skill.get("total_calls", 0) == 0 and skill.get("last_used_at") is None:
        return False, "no data yet"

    rate = compute_success_rate(skill)
    if rate < SENESCENCE_SUCCESS_RATE_THRESHOLD:
        return True, f"success_rate {rate:.2f} below threshold {SENESCENCE_SUCCESS_RATE_THRESHOLD}"

    last_used = skill.get("last_used_at")
    if last_used is not None:
        if now is None:
            now = datetime.now(timezone.utc)
        try:
            last_dt = datetime.fromisoformat(last_used.replace("Z", "+00:00"))
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
            age_days = (now - last_dt).days
            if age_days > SENESCENCE_UNUSED_DAYS:
                return True, f"unused for {age_days} days (threshold {SENESCENCE_UNUSED_DAYS})"
        except (ValueError, TypeError):
            pass

    return False, "healthy"


def run_pruner(
    registry_path=None,
    species_dir=None,
    archive_dir=None,
    dry_run: bool = False,
    now: Optional[datetime] = None,
) -> PrunerResult:
    """Evaluate all skills against senescence policy and archive qualifying ones.

    In dry_run mode: log decisions but do not move files or update registry.
    In normal mode: move species .py file to archive_dir, update registry status to "archived".
    After pruning: write updated registry atomically.
    Returns PrunerResult with archived/kept lists.
    """
    result = PrunerResult()
    result.dry_run = dry_run

    if now is None:
        now = datetime.now(timezone.utc)

    # Resolve paths
    base = Path(__file__).resolve().parent.parent.parent / "memory"
    if registry_path is None:
        registry_path = base / "dna" / "registry.json"
    registry_path = Path(registry_path)

    if species_dir is None:
        species_dir = base / "species"
    species_dir = Path(species_dir)

    if archive_dir is None:
        archive_dir = base / ARCHIVE_DIR_NAME
    archive_dir = Path(archive_dir)

    registry = read_registry(registry_path)
    skills = registry.get("skills", {})
    registry_dirty = False

    for name, skill in skills.items():
        status = skill.get("status", "active")
        if status not in ("active",):
            # Skip already-archived, Toxic-already-handled, etc.
            # Note: Toxic is caught by evaluate_skill but only active skills are pruned here
            continue

        should_archive, reason = evaluate_skill(skill, now=now)

        if should_archive:
            logger.info("[PRUNE] Archiving %s: %s", name, reason)
            if not dry_run:
                archive_dir.mkdir(parents=True, exist_ok=True)
                src = species_dir / f"{name}.py"
                timestamp = now.strftime("%Y%m%dT%H%M%S")
                dst = archive_dir / f"{name}_{timestamp}.py"
                if src.exists():
                    shutil.copy2(str(src), str(dst))
                    src.unlink()
                skill["status"] = "archived"
                registry_dirty = True
            result.archived.append(name)
        else:
            logger.debug("[PRUNE] Keeping %s: %s", name, reason)
            result.kept.append(name)

    if registry_dirty and not dry_run:
        write_registry(registry, registry_path)

    return result
