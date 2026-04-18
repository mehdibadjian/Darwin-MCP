"""Tests for brain/engine/sandbox.py — US-8 & US-9."""
import re
import shutil
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from brain.engine.sandbox import Sandbox, SandboxError


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
