"""Tests for brain/engine/sandbox.py — US-8, US-9 & ENH-US1."""
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from brain.engine.sandbox import Sandbox, SandboxError, SandboxTimeoutError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ok_result(stdout="", stderr=""):
    r = MagicMock()
    r.returncode = 0
    r.stdout = stdout
    r.stderr = stderr
    return r


def _fail_result(stderr="install error"):
    r = MagicMock()
    r.returncode = 1
    r.stdout = ""
    r.stderr = stderr
    return r


# ---------------------------------------------------------------------------
# US-8 AC-1 — path matches /tmp/mutation_{unix_timestamp}
# ---------------------------------------------------------------------------

def test_sandbox_dir_is_tmp_mutation_timestamp():
    s = Sandbox()
    assert re.match(r".*/mutation_\d+$", str(s.path)), (
        f"Expected path like /tmp/mutation_<int>, got {s.path}"
    )


# ---------------------------------------------------------------------------
# US-8 AC-1 — after create(), venv_path exists (mocked subprocess)
# ---------------------------------------------------------------------------

def test_sandbox_contains_venv_after_create(tmp_path):
    with patch("brain.engine.sandbox.subprocess.run", return_value=_ok_result()) as mock_run:
        s = Sandbox(base_dir=tmp_path)
        s.create()
        mock_run.assert_called_once()
        assert s._created is True
    s.cleanup()


# ---------------------------------------------------------------------------
# US-9 AC-1 — pip path is inside venv, not system pip
# ---------------------------------------------------------------------------

def test_pip_targets_sandbox_venv_binary():
    s = Sandbox()
    assert "venv" in str(s.pip), f"pip should be inside venv, got {s.pip}"
    assert str(s.pip).endswith("/bin/pip")


# ---------------------------------------------------------------------------
# US-8 AC-2 — install() calls sandbox pip, not sys.executable pip
# ---------------------------------------------------------------------------

def test_host_site_packages_unmodified(tmp_path):
    import sys

    with patch("brain.engine.sandbox.subprocess.run", return_value=_ok_result()) as mock_run:
        s = Sandbox(base_dir=tmp_path)
        s.install(["requests"])
        cmd = mock_run.call_args[0][0]
        assert str(s.pip) == cmd[0], "install must use sandbox pip"
        assert sys.executable not in cmd, "install must NOT use system python"


# ---------------------------------------------------------------------------
# US-9 AC-2 — non-zero pip exit raises SandboxError
# ---------------------------------------------------------------------------

def test_pip_install_aborted_on_nonzero_exit(tmp_path):
    with patch("brain.engine.sandbox.subprocess.run", return_value=_fail_result()):
        s = Sandbox(base_dir=tmp_path)
        with pytest.raises(SandboxError, match="pip install failed"):
            s.install(["bad-package"])


# ---------------------------------------------------------------------------
# US-8 AC-3 — sandbox dir cleaned up when pip fails
# ---------------------------------------------------------------------------

def test_cleanup_called_on_failure(tmp_path):
    with patch("brain.engine.sandbox.subprocess.run", return_value=_fail_result()):
        s = Sandbox(base_dir=tmp_path)
        s.path.mkdir(parents=True, exist_ok=True)
        with pytest.raises(SandboxError):
            s.install(["bad-package"])
        assert not s.path.exists(), "sandbox dir should be removed after pip failure"


# ---------------------------------------------------------------------------
# US-9 AC-3 — empty requirements → subprocess never called
# ---------------------------------------------------------------------------

def test_pip_skipped_for_empty_requirements(tmp_path):
    with patch("brain.engine.sandbox.subprocess.run") as mock_run:
        s = Sandbox(base_dir=tmp_path)
        s.install([])
        mock_run.assert_not_called()


# ---------------------------------------------------------------------------
# cleanup() removes directory
# ---------------------------------------------------------------------------

def test_cleanup_removes_directory(tmp_path):
    with patch("brain.engine.sandbox.subprocess.run", return_value=_ok_result()):
        s = Sandbox(base_dir=tmp_path)
        s.create()
    s.cleanup()
    assert not s.path.exists()


# ---------------------------------------------------------------------------
# Context manager cleans up on exit
# ---------------------------------------------------------------------------

def test_context_manager_cleans_up_on_exit(tmp_path):
    with patch("brain.engine.sandbox.subprocess.run", return_value=_ok_result()):
        with Sandbox(base_dir=tmp_path) as s:
            sandbox_path = s.path
    assert not sandbox_path.exists(), "context manager should clean up sandbox"


# ---------------------------------------------------------------------------
# ENH-US1 AC-1 — run_isolated returns stdout on success
# ---------------------------------------------------------------------------

def test_run_isolated_success(tmp_path):
    s = Sandbox(base_dir=tmp_path)
    stdout, stderr = s.run_isolated([sys.executable, "-c", "print('hello')"])
    assert "hello" in stdout


# ---------------------------------------------------------------------------
# ENH-US1 AC-1 — run_isolated kills process on timeout
# ---------------------------------------------------------------------------

def test_run_isolated_timeout_kills_process(tmp_path):
    s = Sandbox(base_dir=tmp_path)
    with pytest.raises(SandboxTimeoutError, match="timeout"):
        s.run_isolated(
            [sys.executable, "-c", "import time; time.sleep(10)"],
            timeout=0.5,
        )


# ---------------------------------------------------------------------------
# ENH-US1 AC-1 — parent process unaffected after child timeout
# ---------------------------------------------------------------------------

def test_run_isolated_timeout_does_not_affect_parent(tmp_path):
    s = Sandbox(base_dir=tmp_path)
    with pytest.raises(SandboxTimeoutError):
        s.run_isolated(
            [sys.executable, "-c", "import time; time.sleep(10)"],
            timeout=0.5,
        )
    # parent must continue normally after child is killed
    result = s.run_isolated([sys.executable, "-c", "print('alive')"])
    assert "alive" in result[0]


# ---------------------------------------------------------------------------
# ENH-US1 AC-2 — memory-limited subprocess raises SandboxError
# (RLIMIT_AS enforcement is Linux-only; skip on macOS)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    platform.system() == "Darwin",
    reason="RLIMIT_AS not reliably enforced on macOS; feature targets Linux Droplet",
)
def test_run_isolated_with_memory_limit(tmp_path):
    # 50 MB address-space limit — small enough to prevent a 500 MB allocation
    limit = 50 * 1024 * 1024
    s = Sandbox(base_dir=tmp_path)
    with pytest.raises(SandboxError):
        s.run_isolated(
            [sys.executable, "-c", "x = bytearray(500 * 1024 * 1024)"],
            memory_limit_bytes=limit,
        )


# ---------------------------------------------------------------------------
# Lysosome: purge_pip_cache() — runs `pip cache purge` to prevent /tmp bloat
# ---------------------------------------------------------------------------

def test_purge_pip_cache_runs_pip_cache_purge(tmp_path):
    """purge_pip_cache() must invoke `pip cache purge` via subprocess."""
    with patch("brain.engine.sandbox.subprocess.run", return_value=_ok_result()) as mock_run:
        s = Sandbox(base_dir=tmp_path)
        s.purge_pip_cache()
        calls = mock_run.call_args_list
        assert any("cache" in str(c) and "purge" in str(c) for c in calls), (
            "purge_pip_cache must call 'pip cache purge'"
        )


def test_purge_pip_cache_uses_sandbox_pip(tmp_path):
    """purge_pip_cache() must use the sandbox pip binary, not system pip."""
    with patch("brain.engine.sandbox.subprocess.run", return_value=_ok_result()) as mock_run:
        s = Sandbox(base_dir=tmp_path)
        s.purge_pip_cache()
        calls = mock_run.call_args_list
        pip_purge_call = next(
            (c for c in calls if "cache" in str(c) and "purge" in str(c)), None
        )
        assert pip_purge_call is not None
        cmd = pip_purge_call[0][0]
        assert str(s.pip) == cmd[0], "purge_pip_cache must use sandbox pip, not system pip"


def test_cleanup_calls_purge_pip_cache(tmp_path):
    """cleanup() must call purge_pip_cache() to clear pip build cache."""
    with patch("brain.engine.sandbox.subprocess.run", return_value=_ok_result()):
        s = Sandbox(base_dir=tmp_path)
        s.create()

    with patch.object(s, "purge_pip_cache") as mock_purge:
        s.cleanup()
        mock_purge.assert_called_once()


def test_context_manager_purges_pip_cache(tmp_path):
    """Context manager exit must trigger pip cache purge."""
    with patch("brain.engine.sandbox.subprocess.run", return_value=_ok_result()):
        s = Sandbox(base_dir=tmp_path)
        with patch.object(s, "purge_pip_cache") as mock_purge:
            s.__exit__(None, None, None)
            mock_purge.assert_called_once()


def test_purge_pip_cache_tolerates_failure(tmp_path):
    """purge_pip_cache() must not raise even if pip cache purge fails."""
    with patch("brain.engine.sandbox.subprocess.run", return_value=_fail_result("cache purge failed")):
        s = Sandbox(base_dir=tmp_path)
        # Should not raise
        s.purge_pip_cache()


def test_disk_usage_flat_after_cleanup(tmp_path):
    """After cleanup(), the sandbox directory must not exist (disk reclaimed)."""
    with patch("brain.engine.sandbox.subprocess.run", return_value=_ok_result()):
        s = Sandbox(base_dir=tmp_path)
        s.create()
        # Simulate some files in the sandbox
        (s.path / "dummy.whl").write_bytes(b"x" * 1024)
    s.cleanup()
    assert not s.path.exists(), "cleanup must fully remove the sandbox dir"
