"""Tests for brain/scripts/sanity_check.sh and brain/scripts/install_cron.sh."""
import os
import subprocess
import stat
from pathlib import Path
from unittest.mock import patch, MagicMock, call

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "brain" / "scripts"
SANITY_SCRIPT = SCRIPTS_DIR / "sanity_check.sh"
INSTALL_CRON_SCRIPT = SCRIPTS_DIR / "install_cron.sh"


# ---------------------------------------------------------------------------
# Script existence and permissions
# ---------------------------------------------------------------------------

def test_sanity_check_script_exists():
    """sanity_check.sh must exist in brain/scripts/."""
    assert SANITY_SCRIPT.exists(), f"Missing: {SANITY_SCRIPT}"


def test_install_cron_script_exists():
    """install_cron.sh must exist in brain/scripts/."""
    assert INSTALL_CRON_SCRIPT.exists(), f"Missing: {INSTALL_CRON_SCRIPT}"


def test_sanity_check_is_executable():
    """sanity_check.sh must have execute permission."""
    mode = SANITY_SCRIPT.stat().st_mode
    assert mode & stat.S_IXUSR, "sanity_check.sh must be executable"


def test_install_cron_is_executable():
    """install_cron.sh must have execute permission."""
    mode = INSTALL_CRON_SCRIPT.stat().st_mode
    assert mode & stat.S_IXUSR, "install_cron.sh must be executable"


# ---------------------------------------------------------------------------
# Content: sanity_check.sh must contain the three required operations
# ---------------------------------------------------------------------------

def test_sanity_check_port_check_present():
    """sanity_check.sh must check if SSE port 8000 is responding."""
    content = SANITY_SCRIPT.read_text()
    assert "8000" in content, "sanity_check.sh must check port 8000"


def test_sanity_check_stale_lock_removal_present():
    """sanity_check.sh must remove stale .git/index.lock files."""
    content = SANITY_SCRIPT.read_text()
    assert "index.lock" in content, "sanity_check.sh must handle stale .git/index.lock files"


def test_sanity_check_git_submodule_update_present():
    """sanity_check.sh must run git submodule update --remote."""
    content = SANITY_SCRIPT.read_text()
    assert "submodule" in content and "update" in content and "--remote" in content, (
        "sanity_check.sh must call 'git submodule update --remote'"
    )


def test_sanity_check_restarts_service_on_port_failure():
    """sanity_check.sh must restart darwin.service when port 8000 is unresponsive."""
    content = SANITY_SCRIPT.read_text()
    assert "darwin" in content, "sanity_check.sh must restart darwin.service when port check fails"


# ---------------------------------------------------------------------------
# Content: install_cron.sh must add hourly schedule
# ---------------------------------------------------------------------------

def test_install_cron_hourly_schedule():
    """install_cron.sh must schedule sanity_check.sh to run every hour."""
    content = INSTALL_CRON_SCRIPT.read_text()
    # Accepts any valid hourly cron expression: "0 * * * *" or "@hourly"
    assert ("0 * * * *" in content or "@hourly" in content), (
        "install_cron.sh must contain an hourly cron schedule"
    )


def test_install_cron_references_sanity_script():
    """install_cron.sh must reference sanity_check.sh."""
    content = INSTALL_CRON_SCRIPT.read_text()
    assert "sanity_check.sh" in content


# ---------------------------------------------------------------------------
# Syntax validation (bash -n)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not os.path.exists("/bin/bash") and not os.path.exists("/usr/bin/bash"),
    reason="bash not available in this environment",
)
def test_sanity_check_bash_syntax_valid():
    """sanity_check.sh must have valid bash syntax."""
    result = subprocess.run(
        ["bash", "-n", str(SANITY_SCRIPT)],
        capture_output=True, text=True
    )
    assert result.returncode == 0, f"bash syntax error: {result.stderr}"


@pytest.mark.skipif(
    not os.path.exists("/bin/bash") and not os.path.exists("/usr/bin/bash"),
    reason="bash not available in this environment",
)
def test_install_cron_bash_syntax_valid():
    """install_cron.sh must have valid bash syntax."""
    result = subprocess.run(
        ["bash", "-n", str(INSTALL_CRON_SCRIPT)],
        capture_output=True, text=True
    )
    assert result.returncode == 0, f"bash syntax error: {result.stderr}"
