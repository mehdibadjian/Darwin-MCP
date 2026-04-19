"""Tests for brain/engine/backlog.py — Genetic Backlog queue."""
import json
from pathlib import Path

import pytest

from brain.engine.backlog import (
    MAX_ERROR_COUNT,
    enqueue,
    dequeue,
    mark_done,
    mark_failed,
    get_all,
    pending_count,
    purge_done,
    init_backlog,
    _empty_backlog,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def bp(tmp_path) -> Path:
    """Return a fresh backlog path inside tmp_path."""
    path = tmp_path / "dna" / "backlog.json"
    path.parent.mkdir(parents=True)
    return path


# ── init_backlog ──────────────────────────────────────────────────────────────

def test_init_backlog_creates_file(bp):
    init_backlog(bp)
    assert bp.exists()
    data = json.loads(bp.read_text())
    assert data["version"] == 1
    assert data["items"] == []


def test_init_backlog_idempotent(bp):
    init_backlog(bp)
    init_backlog(bp)   # must not overwrite
    assert json.loads(bp.read_text())["items"] == []


# ── enqueue ───────────────────────────────────────────────────────────────────

def test_enqueue_returns_id(bp):
    item_id = enqueue("report", {"line": "ERROR found"}, backlog_path=bp)
    assert isinstance(item_id, str) and len(item_id) == 36   # UUID4


def test_enqueue_persists(bp):
    enqueue("prune", {}, backlog_path=bp)
    items = get_all(backlog_path=bp)
    assert len(items) == 1
    assert items[0]["task_type"] == "prune"
    assert items[0]["status"] == "pending"


def test_enqueue_invalid_task_type_raises(bp):
    with pytest.raises(ValueError, match="Unknown task_type"):
        enqueue("fly_to_moon", {}, backlog_path=bp)


def test_enqueue_invalid_priority_raises(bp):
    with pytest.raises(ValueError, match="priority must be"):
        enqueue("report", {}, priority=0, backlog_path=bp)
    with pytest.raises(ValueError, match="priority must be"):
        enqueue("report", {}, priority=6, backlog_path=bp)


# ── dequeue ───────────────────────────────────────────────────────────────────

def test_dequeue_empty_returns_none(bp):
    assert dequeue(backlog_path=bp) is None


def test_dequeue_returns_highest_priority_first(bp):
    enqueue("report", {"n": "low"},  priority=4, backlog_path=bp)
    enqueue("prune",  {"n": "high"}, priority=1, backlog_path=bp)
    item = dequeue(backlog_path=bp)
    assert item["priority"] == 1
    assert item["task_type"] == "prune"


def test_dequeue_sets_status_running(bp):
    enqueue("report", {}, backlog_path=bp)
    item = dequeue(backlog_path=bp)
    assert item["status"] == "running"
    # Still shows as running in get_all
    all_items = get_all(backlog_path=bp)
    assert all_items[0]["status"] == "running"


def test_dequeue_fifo_within_same_priority(bp):
    id1 = enqueue("report", {"n": 1}, priority=3, backlog_path=bp)
    id2 = enqueue("report", {"n": 2}, priority=3, backlog_path=bp)
    first = dequeue(backlog_path=bp)
    assert first["id"] == id1


# ── mark_done ─────────────────────────────────────────────────────────────────

def test_mark_done(bp):
    enqueue("prune", {}, backlog_path=bp)
    item = dequeue(backlog_path=bp)
    assert mark_done(item["id"], backlog_path=bp) is True
    assert get_all(backlog_path=bp, status="done")[0]["id"] == item["id"]


def test_mark_done_unknown_id(bp):
    assert mark_done("nonexistent-id", backlog_path=bp) is False


# ── mark_failed ───────────────────────────────────────────────────────────────

def test_mark_failed_re_enqueues_below_max(bp):
    enqueue("prune", {}, backlog_path=bp)
    item = dequeue(backlog_path=bp)
    mark_failed(item["id"], error="oops", backlog_path=bp)
    all_items = get_all(backlog_path=bp)
    assert all_items[0]["status"] == "pending"   # re-enqueued
    assert all_items[0]["error_count"] == 1
    assert all_items[0]["last_error"] == "oops"


def test_mark_failed_permanently_fails_at_max(bp):
    item_id = enqueue("prune", {}, backlog_path=bp)
    for i in range(MAX_ERROR_COUNT):
        # dequeue → fail cycle
        dequeue(backlog_path=bp)
        mark_failed(item_id, error=f"err{i}", backlog_path=bp)
    all_items = get_all(backlog_path=bp)
    assert all_items[0]["status"] == "failed"


# ── pending_count ─────────────────────────────────────────────────────────────

def test_pending_count(bp):
    assert pending_count(backlog_path=bp) == 0
    enqueue("report", {}, backlog_path=bp)
    enqueue("report", {}, backlog_path=bp)
    assert pending_count(backlog_path=bp) == 2
    dequeue(backlog_path=bp)
    assert pending_count(backlog_path=bp) == 1   # one running, one pending


# ── purge_done ────────────────────────────────────────────────────────────────

def test_purge_done_removes_old_completed(bp):
    from datetime import datetime, timezone, timedelta
    item_id = enqueue("prune", {}, backlog_path=bp)
    dequeue(backlog_path=bp)
    mark_done(item_id, backlog_path=bp)

    # Backdate the completed item by 25 hours
    data = json.loads(bp.read_text())
    old_time = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
    data["items"][0]["updated_at"] = old_time
    bp.write_text(json.dumps(data))

    removed = purge_done(backlog_path=bp)
    assert removed == 1
    assert get_all(backlog_path=bp) == []


def test_purge_done_keeps_recent_completed(bp):
    item_id = enqueue("prune", {}, backlog_path=bp)
    dequeue(backlog_path=bp)
    mark_done(item_id, backlog_path=bp)
    removed = purge_done(backlog_path=bp)
    assert removed == 0
    assert len(get_all(backlog_path=bp)) == 1


def test_purge_done_never_removes_pending(bp):
    enqueue("report", {}, backlog_path=bp)
    removed = purge_done(backlog_path=bp)
    assert removed == 0
    assert pending_count(backlog_path=bp) == 1
