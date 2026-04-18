"""Tests for US-28 (watchdog file watcher) and US-29 (MCP list_changed notification)."""
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, call
import pytest

import brain.watcher.hot_reload as hr


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clear_callbacks():
    hr._active_sse_callbacks.clear()
    with hr._notification_lock:
        hr._notification_queue.clear()


# ---------------------------------------------------------------------------
# US-28 — SpeciesEventHandler
# ---------------------------------------------------------------------------

class TestSpeciesEventHandler:
    def setup_method(self):
        _clear_callbacks()

    def _make_event(self, path, is_directory=False):
        ev = MagicMock()
        ev.src_path = path
        ev.is_directory = is_directory
        return ev

    @patch("brain.watcher.hot_reload._emit_list_changed")
    @patch("brain.utils.registry.discover_species")
    def test_new_py_file_triggers_registration(self, mock_discover, mock_emit, tmp_path):
        handler = hr.SpeciesEventHandler(
            species_dir=str(tmp_path), registry_path=str(tmp_path / "registry.json")
        )
        with patch("brain.watcher.hot_reload._emit_list_changed", mock_emit):
            with patch("brain.utils.registry.discover_species", mock_discover):
                with patch("brain.watcher.hot_reload.__import__", create=True):
                    # Patch the import inside _handle
                    with patch("brain.watcher.hot_reload.SpeciesEventHandler._handle") as mock_handle:
                        mock_handle.side_effect = lambda p: hr.SpeciesEventHandler._handle(handler, p)
                        pass

        # Direct test: patch discover_species via module
        with patch("brain.watcher.hot_reload._emit_list_changed") as mock_emit2:
            import brain.utils.registry as reg_mod
            with patch.object(reg_mod, "discover_species") as mock_disc2:
                handler2 = hr.SpeciesEventHandler(
                    species_dir=str(tmp_path),
                    registry_path=str(tmp_path / "registry.json"),
                )
                handler2.on_created(self._make_event(str(tmp_path / "foo.py")))
                mock_disc2.assert_called_once()
                mock_emit2.assert_called_once()

    @patch("brain.watcher.hot_reload._emit_list_changed")
    def test_modified_py_file_updates_registry(self, mock_emit, tmp_path):
        import brain.utils.registry as reg_mod
        with patch.object(reg_mod, "discover_species") as mock_disc:
            handler = hr.SpeciesEventHandler(
                species_dir=str(tmp_path),
                registry_path=str(tmp_path / "registry.json"),
            )
            handler.on_modified(self._make_event(str(tmp_path / "bar.py")))
            mock_disc.assert_called_once()
            mock_emit.assert_called_once()

    def test_non_py_file_ignored(self, tmp_path):
        import brain.utils.registry as reg_mod
        with patch.object(reg_mod, "discover_species") as mock_disc:
            handler = hr.SpeciesEventHandler(species_dir=str(tmp_path))
            handler.on_created(self._make_event(str(tmp_path / "readme.txt")))
            mock_disc.assert_not_called()

    def test_directory_event_ignored(self, tmp_path):
        import brain.utils.registry as reg_mod
        with patch.object(reg_mod, "discover_species") as mock_disc:
            handler = hr.SpeciesEventHandler(species_dir=str(tmp_path))
            handler.on_created(self._make_event(str(tmp_path / "subdir"), is_directory=True))
            mock_disc.assert_not_called()


# ---------------------------------------------------------------------------
# US-29 — list_changed notifications
# ---------------------------------------------------------------------------

class TestListChangedNotifications:
    def setup_method(self):
        _clear_callbacks()

    def test_list_changed_emitted_on_registration(self, tmp_path):
        """_emit_list_changed is invoked after a .py file event."""
        import brain.utils.registry as reg_mod
        with patch.object(reg_mod, "discover_species"):
            handler = hr.SpeciesEventHandler(species_dir=str(tmp_path))
            cb = MagicMock()
            hr.register_sse_callback(cb)
            ev = MagicMock()
            ev.src_path = str(tmp_path / "skill.py")
            ev.is_directory = False
            handler.on_created(ev)
            cb.assert_called_once_with({"type": "list_changed"})

    def test_notification_queued_when_no_sse_connection(self):
        """With no active callbacks, notification lands in the queue."""
        hr._emit_list_changed()
        with hr._notification_lock:
            assert hr._notification_queue == [{"type": "list_changed"}]

    def test_notification_sent_to_active_callback(self):
        """With an active callback, it is called directly and queue stays empty."""
        cb = MagicMock()
        hr.register_sse_callback(cb)
        hr._emit_list_changed()
        cb.assert_called_once_with({"type": "list_changed"})
        with hr._notification_lock:
            assert hr._notification_queue == []

    def test_queued_notifications_flushed_on_connect(self):
        """flush_queued_notifications sends queued items and clears the queue."""
        with hr._notification_lock:
            hr._notification_queue.append({"type": "list_changed"})
        cb = MagicMock()
        hr.flush_queued_notifications(cb)
        cb.assert_called_once_with({"type": "list_changed"})
        with hr._notification_lock:
            assert hr._notification_queue == []

    def test_register_and_unregister_sse_callback(self):
        cb = MagicMock()
        hr.register_sse_callback(cb)
        assert cb in hr._active_sse_callbacks
        hr.unregister_sse_callback(cb)
        assert cb not in hr._active_sse_callbacks


# ---------------------------------------------------------------------------
# US-28 AC-3 — watcher restarts on failure
# ---------------------------------------------------------------------------

class TestWatcherRestart:
    def setup_method(self):
        _clear_callbacks()

    def test_watcher_restarts_on_failure(self, tmp_path):
        """If observer.join() raises, the watcher loop restarts."""
        call_count = {"n": 0}
        restart_event = threading.Event()

        with patch("brain.watcher.hot_reload.Observer") as MockObserver:
            instance = MockObserver.return_value

            def fake_join():
                call_count["n"] += 1
                if call_count["n"] == 1:
                    raise RuntimeError("simulated failure")
                restart_event.set()
                # Block until test finishes to avoid busy-loop
                time.sleep(5)

            instance.join.side_effect = fake_join

            hr.start_watcher(species_dir=str(tmp_path), restart_on_failure=True)
            assert restart_event.wait(timeout=5), "Watcher did not restart within 5s"
            assert call_count["n"] >= 2

    def test_watcher_error_is_logged(self, tmp_path):
        """When observer.join() raises, logger.error is called."""
        done = threading.Event()

        with patch("brain.watcher.hot_reload.Observer") as MockObserver:
            instance = MockObserver.return_value

            def fake_join():
                done.set()
                raise RuntimeError("boom")

            instance.join.side_effect = fake_join

            with patch("brain.watcher.hot_reload.logger") as mock_logger:
                hr.start_watcher(species_dir=str(tmp_path), restart_on_failure=False)
                done.wait(timeout=5)
                time.sleep(0.2)  # let logger call happen
                mock_logger.error.assert_called()

    def test_no_restart_when_disabled(self, tmp_path):
        """When restart_on_failure=False, loop exits after first failure."""
        call_count = {"n": 0}
        done = threading.Event()

        with patch("brain.watcher.hot_reload.Observer") as MockObserver:
            instance = MockObserver.return_value

            def fake_join():
                call_count["n"] += 1
                done.set()
                raise RuntimeError("stop")

            instance.join.side_effect = fake_join

            hr.start_watcher(species_dir=str(tmp_path), restart_on_failure=False)
            done.wait(timeout=5)
            time.sleep(0.3)
            assert call_count["n"] == 1
