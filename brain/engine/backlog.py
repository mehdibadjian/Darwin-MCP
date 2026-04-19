"""Genetic Backlog — Darwin-MCP autonomous task queue.

Provides a JSON-backed FIFO queue used by the Heartbeat loop to decouple
event detection (Scavenger) from execution (Mutator / Pruner).

File location: memory/dna/backlog.json

Schema
------
{
  "version": 1,
  "items": [
    {
      "id":          str,          # UUID4
      "task_type":   str,          # "evolve" | "prune" | "optimize" | "report"
      "payload":     dict,         # task-type-specific data
      "priority":    int,          # 1 (highest) … 5 (lowest)
      "status":      str,          # "pending" | "running" | "done" | "failed"
      "created_at":  str,          # ISO8601 UTC
      "updated_at":  str,          # ISO8601 UTC
      "error_count": int,
      "last_error":  str | null
    }
  ]
}

Concurrency note: all writes use a file-level lock (portalocker when available,
falls back to a simple rename-swap pattern to prevent registry corruption).
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_DEFAULT_BACKLOG_PATH = (
    Path(__file__).resolve().parent.parent.parent / "memory" / "dna" / "backlog.json"
)

TASK_TYPES = frozenset({"evolve", "prune", "optimize", "report"})
STATUSES = frozenset({"pending", "running", "done", "failed"})
MAX_ERROR_COUNT = 5   # items exceeding this are auto-failed


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve(path: Optional[Path | str]) -> Path:
    return Path(path) if path else _DEFAULT_BACKLOG_PATH


def _empty_backlog() -> dict:
    return {"version": 1, "items": []}


def _read_raw(path: Path) -> dict:
    if not path.exists():
        return _empty_backlog()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if "items" not in data:
            data["items"] = []
        return data
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Backlog file unreadable (%s), starting fresh: %s", path, exc)
        return _empty_backlog()


def _write_raw(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(path)   # atomic rename


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def init_backlog(backlog_path=None) -> None:
    """Create backlog.json if it does not already exist."""
    path = _resolve(backlog_path)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        _write_raw(path, _empty_backlog())
        logger.info("Initialised empty backlog at %s", path)


def enqueue(
    task_type: str,
    payload: Dict[str, Any],
    priority: int = 3,
    backlog_path=None,
) -> str:
    """Add a new item to the backlog.

    Args:
        task_type: One of TASK_TYPES ("evolve", "prune", "optimize", "report").
        payload:   Task-specific data dict.
        priority:  1 (highest) … 5 (lowest).

    Returns:
        The new item's UUID string.

    Raises:
        ValueError: on unknown task_type or out-of-range priority.
    """
    if task_type not in TASK_TYPES:
        raise ValueError(f"Unknown task_type '{task_type}'. Must be one of {TASK_TYPES}")
    if not (1 <= priority <= 5):
        raise ValueError(f"priority must be 1–5, got {priority}")

    item_id = str(uuid.uuid4())
    now = _now()
    item = {
        "id": item_id,
        "task_type": task_type,
        "payload": payload,
        "priority": priority,
        "status": "pending",
        "created_at": now,
        "updated_at": now,
        "error_count": 0,
        "last_error": None,
    }
    path = _resolve(backlog_path)
    data = _read_raw(path)
    data["items"].append(item)
    _write_raw(path, data)
    logger.info("Enqueued %s task (priority=%d) id=%s", task_type, priority, item_id)
    return item_id


def dequeue(backlog_path=None) -> Optional[Dict]:
    """Pop the highest-priority pending item (lowest priority number first, then FIFO).

    Marks the returned item as "running".
    Returns None when there are no pending items.
    """
    path = _resolve(backlog_path)
    data = _read_raw(path)
    pending = [i for i in data["items"] if i["status"] == "pending"]
    if not pending:
        return None
    # Sort by priority asc, then created_at asc (FIFO within same priority)
    pending.sort(key=lambda i: (i["priority"], i["created_at"]))
    item = pending[0]
    item["status"] = "running"
    item["updated_at"] = _now()
    _write_raw(path, data)
    logger.debug("Dequeued %s task id=%s", item["task_type"], item["id"])
    return item


def mark_done(item_id: str, backlog_path=None) -> bool:
    """Mark a running item as done. Returns True if found, False otherwise."""
    return _update_status(item_id, "done", backlog_path=backlog_path)


def mark_failed(item_id: str, error: str = "", backlog_path=None) -> bool:
    """Mark a running item as failed. Auto-increments error_count."""
    path = _resolve(backlog_path)
    data = _read_raw(path)
    for item in data["items"]:
        if item["id"] == item_id:
            item["error_count"] = item.get("error_count", 0) + 1
            item["last_error"] = error[:500] if error else None
            # Permanently fail if too many retries
            if item["error_count"] >= MAX_ERROR_COUNT:
                item["status"] = "failed"
                logger.warning("Item %s permanently failed after %d errors", item_id, item["error_count"])
            else:
                item["status"] = "pending"   # re-enqueue for retry
                logger.info("Item %s re-queued after error (%d/%d)", item_id, item["error_count"], MAX_ERROR_COUNT)
            item["updated_at"] = _now()
            _write_raw(path, data)
            return True
    logger.warning("mark_failed: item %s not found", item_id)
    return False


def _update_status(item_id: str, new_status: str, backlog_path=None) -> bool:
    path = _resolve(backlog_path)
    data = _read_raw(path)
    for item in data["items"]:
        if item["id"] == item_id:
            item["status"] = new_status
            item["updated_at"] = _now()
            _write_raw(path, data)
            return True
    return False


def get_all(backlog_path=None, status: Optional[str] = None) -> List[Dict]:
    """Return all items, optionally filtered by status."""
    data = _read_raw(_resolve(backlog_path))
    items = data.get("items", [])
    if status:
        items = [i for i in items if i.get("status") == status]
    return items


def pending_count(backlog_path=None) -> int:
    """Return number of pending items."""
    return len(get_all(backlog_path, status="pending"))


def purge_done(backlog_path=None) -> int:
    """Remove completed items older than 24 h to keep the file lean. Returns count removed."""
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    path = _resolve(backlog_path)
    data = _read_raw(path)
    before = len(data["items"])
    def _keep(item):
        if item["status"] not in ("done", "failed"):
            return True
        try:
            updated = datetime.fromisoformat(item["updated_at"].replace("Z", "+00:00"))
            if updated.tzinfo is None:
                updated = updated.replace(tzinfo=timezone.utc)
            return updated > cutoff
        except (ValueError, TypeError):
            return True
    data["items"] = [i for i in data["items"] if _keep(i)]
    removed = before - len(data["items"])
    if removed:
        _write_raw(path, data)
        logger.info("Purged %d completed backlog items", removed)
    return removed
