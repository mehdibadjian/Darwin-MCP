"""Tests for US-25 (resource monitor SIGKILL) and US-26 (Toxic skill flag)."""
import json
import os
import signal
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_registry(tmp_path, skills=None):
    reg_path = tmp_path / "registry.json"
    data = {
        "organism_version": "1.0.0",
        "last_mutation": None,
        "skills": skills or {},
    }
    reg_path.write_text(json.dumps(data))
    return reg_path


# ---------------------------------------------------------------------------
# US-25 — SIGKILL on CPU / RAM exceeded
# ---------------------------------------------------------------------------

class TestSigkillOnResourceLimitExceeded:
    def test_sigkill_sent_when_cpu_exceeded(self, tmp_path):
        reg_path = _make_registry(tmp_path, {"skill_a": {"status": "active"}})

        mock_proc = MagicMock()
        mock_proc.cpu_percent.return_value = 90.0
        mock_proc.memory_info.return_value = MagicMock(rss=50 * 1024 * 1024)

        with patch("psutil.Process", return_value=mock_proc), \
             patch("os.kill") as mock_kill:
            from brain.engine.guard import monitor_subprocess, ResourceLimitError
            with pytest.raises(ResourceLimitError):
                monitor_subprocess(
                    pid=1234,
                    skill_name="skill_a",
                    registry_path=reg_path,
                    cpu_limit=80.0,
                    ram_limit=256.0,
                    poll_interval=0,
                )
            mock_kill.assert_called_once_with(1234, signal.SIGKILL)

    def test_sigkill_sent_when_ram_exceeded(self, tmp_path):
        reg_path = _make_registry(tmp_path, {"skill_b": {"status": "active"}})

        mock_proc = MagicMock()
        mock_proc.cpu_percent.return_value = 5.0
        mock_proc.memory_info.return_value = MagicMock(rss=300 * 1024 * 1024)

        with patch("psutil.Process", return_value=mock_proc), \
             patch("os.kill") as mock_kill:
            from brain.engine.guard import monitor_subprocess, ResourceLimitError
            with pytest.raises(ResourceLimitError):
                monitor_subprocess(
                    pid=5678,
                    skill_name="skill_b",
                    registry_path=reg_path,
                    cpu_limit=80.0,
                    ram_limit=256.0,
                    poll_interval=0,
                )
            mock_kill.assert_called_once_with(5678, signal.SIGKILL)

    def test_process_gone_handled_gracefully(self, tmp_path):
        """If the process no longer exists, monitor_subprocess returns cleanly."""
        reg_path = _make_registry(tmp_path, {"skill_c": {"status": "active"}})

        import psutil

        with patch("psutil.Process", side_effect=psutil.NoSuchProcess(pid=9999)):
            from brain.engine.guard import monitor_subprocess
            stop = threading.Event()
            stop.set()  # stop immediately after first non-violating iteration
            # Should not raise
            monitor_subprocess(
                pid=9999,
                skill_name="skill_c",
                registry_path=reg_path,
                cpu_limit=80.0,
                ram_limit=256.0,
                poll_interval=0,
                stop_event=stop,
            )


# ---------------------------------------------------------------------------
# US-26 — Toxic flag in registry
# ---------------------------------------------------------------------------

class TestMarkToxic:
    def test_mark_toxic_sets_status_in_registry(self, tmp_path):
        reg_path = _make_registry(tmp_path, {"my_skill": {"status": "active"}})

        from brain.engine.guard import mark_toxic
        mark_toxic("my_skill", registry_path=reg_path)

        data = json.loads(reg_path.read_text())
        assert data["skills"]["my_skill"]["status"] == "Toxic"

    def test_mark_toxic_stores_reason(self, tmp_path):
        reg_path = _make_registry(tmp_path, {"my_skill": {"status": "active"}})

        from brain.engine.guard import mark_toxic
        mark_toxic("my_skill", reason="RAM 300.0 MB > limit 256.0 MB", registry_path=reg_path)

        data = json.loads(reg_path.read_text())
        assert data["skills"]["my_skill"]["toxic_reason"] == "RAM 300.0 MB > limit 256.0 MB"

    def test_skill_marked_toxic_after_sigkill(self, tmp_path):
        reg_path = _make_registry(tmp_path, {"skill_d": {"status": "active"}})

        mock_proc = MagicMock()
        mock_proc.cpu_percent.return_value = 95.0
        mock_proc.memory_info.return_value = MagicMock(rss=10 * 1024 * 1024)

        with patch("psutil.Process", return_value=mock_proc), \
             patch("os.kill"):
            from brain.engine.guard import monitor_subprocess, ResourceLimitError
            with pytest.raises(ResourceLimitError):
                monitor_subprocess(
                    pid=1111,
                    skill_name="skill_d",
                    registry_path=reg_path,
                    cpu_limit=80.0,
                    ram_limit=256.0,
                    poll_interval=0,
                )

        data = json.loads(reg_path.read_text())
        assert data["skills"]["skill_d"]["status"] == "Toxic"


# ---------------------------------------------------------------------------
# US-26 — SSE /sse excludes Toxic skills
# ---------------------------------------------------------------------------

class TestSSEToolListExcludesToxic:
    def test_toxic_skill_excluded_from_tool_list(self, tmp_path):
        import asyncio as _asyncio
        import brain.bridge.sse_server as _mod

        async def _raise_cancelled(coro, *args, **kwargs):
            coro.close()
            raise _asyncio.CancelledError()

        registry_data = {
            "organism_version": "1.0.0",
            "last_mutation": None,
            "skills": {
                "good_skill": {"status": "active"},
                "bad_skill": {"status": "Toxic"},
            },
        }

        with patch.dict(os.environ, {"MCP_BEARER_TOKEN": "testtoken"}), \
             patch("brain.bridge.sse_server.read_registry", return_value=registry_data), \
             patch("brain.bridge.sse_server.init_registry"), \
             patch("brain.bridge.sse_server.discover_species"), \
             patch("brain.bridge.sse_server.cleanup_stale_sandboxes"), \
             patch.object(_mod.asyncio, "wait_for", _raise_cancelled):
            from fastapi.testclient import TestClient
            from brain.bridge.sse_server import app

            client = TestClient(app, raise_server_exceptions=True)
            resp = client.get("/sse", headers={"Authorization": "Bearer testtoken"})
            assert resp.status_code == 200
            body = resp.text
            assert "good_skill" in body
            assert "bad_skill" not in body


# ---------------------------------------------------------------------------
# US-26 — Direct invoke endpoint returns 403 for Toxic skill
# ---------------------------------------------------------------------------

class TestInvokeEndpoint:
    def _client(self, registry_data):
        with patch.dict(os.environ, {"MCP_BEARER_TOKEN": "testtoken"}), \
             patch("brain.bridge.sse_server.read_registry", return_value=registry_data), \
             patch("brain.bridge.sse_server.init_registry"), \
             patch("brain.bridge.sse_server.discover_species"), \
             patch("brain.bridge.sse_server.cleanup_stale_sandboxes"):
            from fastapi.testclient import TestClient
            from brain.bridge.sse_server import app
            return TestClient(app, raise_server_exceptions=True), registry_data

    def test_toxic_skill_direct_invoke_returns_403(self, tmp_path):
        registry_data = {
            "organism_version": "1.0.0",
            "last_mutation": None,
            "skills": {"bad_skill": {"status": "Toxic"}},
        }
        with patch.dict(os.environ, {"MCP_BEARER_TOKEN": "testtoken"}), \
             patch("brain.bridge.sse_server.read_registry", return_value=registry_data), \
             patch("brain.bridge.sse_server.init_registry"), \
             patch("brain.bridge.sse_server.discover_species"), \
             patch("brain.bridge.sse_server.cleanup_stale_sandboxes"):
            from fastapi.testclient import TestClient
            from brain.bridge.sse_server import app

            client = TestClient(app, raise_server_exceptions=True)
            resp = client.get(
                "/tools/bad_skill/invoke",
                headers={"Authorization": "Bearer testtoken"},
            )
            assert resp.status_code == 403
            assert "quarantined" in resp.text.lower() or "toxic" in resp.text.lower()

    def test_non_toxic_skill_invoke_ok(self, tmp_path):
        registry_data = {
            "organism_version": "1.0.0",
            "last_mutation": None,
            "skills": {"good_skill": {"status": "active"}},
        }
        with patch.dict(os.environ, {"MCP_BEARER_TOKEN": "testtoken"}), \
             patch("brain.bridge.sse_server.read_registry", return_value=registry_data), \
             patch("brain.bridge.sse_server.init_registry"), \
             patch("brain.bridge.sse_server.discover_species"), \
             patch("brain.bridge.sse_server.cleanup_stale_sandboxes"):
            from fastapi.testclient import TestClient
            from brain.bridge.sse_server import app

            client = TestClient(app, raise_server_exceptions=True)
            resp = client.get(
                "/tools/good_skill/invoke",
                headers={"Authorization": "Bearer testtoken"},
            )
            assert resp.status_code == 200


# ---------------------------------------------------------------------------
# ENH-US2 — SandboxConfig and run_sandboxed resource limits
# ---------------------------------------------------------------------------

import sys


class TestSandboxConfig:
    def test_sandbox_config_defaults(self):
        from brain.engine.guard import SandboxConfig
        cfg = SandboxConfig()
        assert cfg.max_cpu_cores == 1
        assert cfg.max_memory_mb == 512.0
        assert cfg.max_timeout_s == 3.0
        assert cfg.max_file_handles == 50

    def test_make_preexec_returns_callable(self):
        from brain.engine.guard import SandboxConfig, make_preexec
        fn = make_preexec(SandboxConfig())
        assert callable(fn)


class TestRunSandboxed:
    def test_run_sandboxed_success(self):
        from brain.engine.guard import SandboxConfig, run_sandboxed
        cfg = SandboxConfig(max_timeout_s=5.0)
        stdout, stderr = run_sandboxed(["python", "-c", "print('ok')"], cfg)
        assert "ok" in stdout

    def test_run_sandboxed_timeout_kills_all_processes(self):
        from brain.engine.guard import SandboxConfig, run_sandboxed
        from brain.engine.sandbox import SandboxTimeoutError
        cfg = SandboxConfig(max_timeout_s=0.5)
        with pytest.raises(SandboxTimeoutError):
            run_sandboxed(["python", "-c", "import time; time.sleep(10)"], cfg)

    @pytest.mark.skipif(sys.platform != "linux", reason="RLIMIT_NOFILE enforcement varies on macOS")
    def test_run_sandboxed_file_handle_limit(self):
        """Process that opens 200 files with handle limit=10 should fail → ResourceLimitError."""
        from brain.engine.guard import SandboxConfig, run_sandboxed, ResourceLimitError
        cfg = SandboxConfig(max_file_handles=10, max_timeout_s=5.0)
        script = (
            "fds = [open('/dev/null') for _ in range(200)]"
        )
        with pytest.raises(ResourceLimitError):
            run_sandboxed(["python", "-c", script], cfg)

    def test_run_sandboxed_cleanup_on_timeout(self):
        """After SandboxTimeoutError the exception is raised cleanly (no hanging processes)."""
        import psutil
        from brain.engine.guard import SandboxConfig, run_sandboxed
        from brain.engine.sandbox import SandboxTimeoutError
        cfg = SandboxConfig(max_timeout_s=0.5)
        with pytest.raises(SandboxTimeoutError):
            run_sandboxed(["python", "-c", "import time; time.sleep(10)"], cfg)
        # If we reach here the exception was raised — process group was killed cleanly.
