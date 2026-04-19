"""US-28 / US-29 — Watchdog file watcher with MCP list_changed notifications."""
import logging
import threading
import time
from pathlib import Path

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Official MCP notification constant (jsonrpc-compatible)
# ---------------------------------------------------------------------------

MCP_LIST_CHANGED: dict = {
    "method": "notifications/tools/list_changed",
    "params": {},
}

# ---------------------------------------------------------------------------
# SSE callback registry and notification queue (thread-safe)
# ---------------------------------------------------------------------------

_notification_queue: list = []
_notification_lock = threading.Lock()
_active_sse_callbacks: list = []


def register_sse_callback(callback) -> None:
    """Register an async callable invoked on list_changed."""
    _active_sse_callbacks.append(callback)


def unregister_sse_callback(callback) -> None:
    """Remove an SSE callback when the connection closes."""
    if callback in _active_sse_callbacks:
        _active_sse_callbacks.remove(callback)


def _emit_list_changed() -> None:
    """Push list_changed to all active SSE connections; queue if none exist.

    Emits the official MCP notification format so that IDEs (Cursor, Claude
    Desktop) automatically refresh their tool list without a reconnect.
    """
    notification = MCP_LIST_CHANGED
    if _active_sse_callbacks:
        for cb in list(_active_sse_callbacks):
            try:
                cb(notification)
            except Exception as exc:
                logger.warning(f"SSE callback error: {exc}")
    else:
        with _notification_lock:
            _notification_queue.append(notification)


def flush_queued_notifications(callback) -> None:
    """Send any queued notifications to *callback* on new SSE connection."""
    with _notification_lock:
        for notif in _notification_queue:
            try:
                callback(notif)
            except Exception:
                pass
        _notification_queue.clear()


# ---------------------------------------------------------------------------
# Watchdog event handler
# ---------------------------------------------------------------------------

class SpeciesEventHandler(FileSystemEventHandler):
    def __init__(self, species_dir=None, registry_path=None):
        super().__init__()
        self.species_dir = species_dir
        self.registry_path = registry_path

    def _handle(self, path: str) -> None:
        if not path.endswith(".py"):
            return
        try:
            from brain.utils.registry import discover_species
            discover_species(
                species_dir=self.species_dir,
                registry_path=self.registry_path,
            )
            _emit_list_changed()
            logger.info(f"Re-registered species after change: {path}")
        except Exception as exc:
            logger.error(f"Failed to re-register species: {exc}")

    def on_created(self, event) -> None:
        if not event.is_directory:
            self._handle(event.src_path)

    def on_modified(self, event) -> None:
        if not event.is_directory:
            self._handle(event.src_path)


# ---------------------------------------------------------------------------
# Watcher start — daemon thread with optional auto-restart
# ---------------------------------------------------------------------------

def start_watcher(
    species_dir=None,
    registry_path=None,
    restart_on_failure: bool = True,
):
    """Start the watchdog Observer in a daemon thread.

    Automatically restarts on failure when *restart_on_failure* is True.
    Returns the daemon thread.
    """
    if species_dir is None:
        species_dir = (
            Path(__file__).resolve().parent.parent.parent / "memory" / "species"
        )
    species_dir = Path(species_dir)
    species_dir.mkdir(parents=True, exist_ok=True)

    def _run() -> None:
        while True:
            try:
                handler = SpeciesEventHandler(
                    species_dir=str(species_dir),
                    registry_path=registry_path,
                )
                observer = Observer()
                observer.schedule(handler, str(species_dir), recursive=False)
                observer.start()
                logger.info(f"Watchdog started on {species_dir}")
                observer.join()
            except Exception as exc:
                logger.error(f"Watchdog error: {exc}. Restarting in 1s...")
                if not restart_on_failure:
                    break
                time.sleep(1)

    t = threading.Thread(target=_run, daemon=True, name="species-watcher")
    t.start()
    return t
