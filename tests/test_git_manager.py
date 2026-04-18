"""Tests for brain/utils/git_manager.py — US-13, US-14, US-15, US-16."""
import subprocess
from pathlib import Path
from unittest.mock import call, patch, MagicMock

import pytest

from brain.utils.git_manager import (
    GitError,
    PushRejectedError,
    RebaseError,
    commit_and_push,
)

MEMORY_DIR = Path("/fake/memory")


def _make_result(rc=0, stdout="", stderr=""):
    r = MagicMock()
    r.returncode = rc
    r.stdout = stdout
    r.stderr = stderr
    return r


# ---------------------------------------------------------------------------
# US-13 — git add / commit / push sequencing
# ---------------------------------------------------------------------------

def test_git_add_runs_in_memory_dir():
    """git add . must be called with cwd=memory_dir."""
    ok = _make_result(0)
    with patch("subprocess.run", return_value=ok) as mock_run:
        commit_and_push("mypkg", 1, memory_dir=MEMORY_DIR)
    first_call = mock_run.call_args_list[0]
    assert first_call[0][0] == ["git", "add", "."]
    assert first_call[1]["cwd"] == str(MEMORY_DIR)


def test_push_attempted_after_commit():
    """git push origin main must be called after a successful commit."""
    ok = _make_result(0)
    with patch("subprocess.run", return_value=ok) as mock_run:
        commit_and_push("mypkg", 1, memory_dir=MEMORY_DIR)
    cmds = [c[0][0] for c in mock_run.call_args_list]
    assert ["git", "push", "origin", "main"] in cmds


# ---------------------------------------------------------------------------
# US-14 — commit message format
# ---------------------------------------------------------------------------

def test_commit_message_exact_format():
    """Commit message must be exactly 'evolution: pdf_parser v1'."""
    ok = _make_result(0)
    with patch("subprocess.run", return_value=ok) as mock_run:
        commit_and_push("pdf_parser", 1, memory_dir=MEMORY_DIR)
    commit_call = mock_run.call_args_list[1]
    assert commit_call[0][0] == ["git", "commit", "-m", "evolution: pdf_parser v1"]


def test_commit_message_no_extra_text():
    """Commit message must contain ONLY 'evolution: {name} v{version}'."""
    ok = _make_result(0)
    with patch("subprocess.run", return_value=ok) as mock_run:
        commit_and_push("pdf_parser", 1, memory_dir=MEMORY_DIR)
    commit_call = mock_run.call_args_list[1]
    msg = commit_call[0][0][3]  # 4th element of git commit -m <msg>
    assert msg == "evolution: pdf_parser v1"


def test_commit_message_version_incremented():
    """Version number in commit message reflects the version argument."""
    ok = _make_result(0)
    with patch("subprocess.run", return_value=ok) as mock_run:
        commit_and_push("pdf_parser", 3, memory_dir=MEMORY_DIR)
    commit_call = mock_run.call_args_list[1]
    assert commit_call[0][0][3] == "evolution: pdf_parser v3"


# ---------------------------------------------------------------------------
# US-15 — push rejection → pull --rebase → retry
# ---------------------------------------------------------------------------

def test_push_rejection_triggers_rebase():
    """When push fails with 'rejected', git pull --rebase must be called."""
    ok = _make_result(0)
    rejected = _make_result(1, stderr="error: failed to push some refs (rejected)")
    # add, commit → ok; push → rejected; pull --rebase → ok; retry push → ok
    with patch("subprocess.run", side_effect=[ok, ok, rejected, ok, ok]) as mock_run:
        commit_and_push("mypkg", 1, memory_dir=MEMORY_DIR)
    cmds = [c[0][0] for c in mock_run.call_args_list]
    assert ["git", "pull", "--rebase", "origin", "main"] in cmds


def test_rebase_success_retries_push():
    """After successful rebase, git push origin main must be called a second time."""
    ok = _make_result(0)
    rejected = _make_result(1, stderr="rejected")
    with patch("subprocess.run", side_effect=[ok, ok, rejected, ok, ok]) as mock_run:
        commit_and_push("mypkg", 1, memory_dir=MEMORY_DIR)
    push_calls = [c for c in mock_run.call_args_list if c[0][0] == ["git", "push", "origin", "main"]]
    assert len(push_calls) == 2


def test_retry_push_failure_raises_error():
    """If the retry push also fails, PushRejectedError must be raised."""
    ok = _make_result(0)
    rejected = _make_result(1, stderr="rejected")
    with patch("subprocess.run", side_effect=[ok, ok, rejected, ok, rejected]):
        with pytest.raises(PushRejectedError):
            commit_and_push("mypkg", 1, memory_dir=MEMORY_DIR)


# ---------------------------------------------------------------------------
# US-16 — structured rebase error
# ---------------------------------------------------------------------------

def test_rebase_failure_calls_abort():
    """When pull --rebase fails, git rebase --abort must be called."""
    ok = _make_result(0)
    rejected = _make_result(1, stderr="rejected")
    rebase_fail = _make_result(1, stderr="CONFLICT (content): Merge conflict in skill.py")
    abort = _make_result(0)
    with patch("subprocess.run", side_effect=[ok, ok, rejected, rebase_fail, abort]):
        with pytest.raises(RebaseError):
            commit_and_push("mypkg", 1, memory_dir=MEMORY_DIR)
    # last call must be rebase --abort
    with patch("subprocess.run", side_effect=[ok, ok, rejected, rebase_fail, abort]) as mock_run:
        try:
            commit_and_push("mypkg", 1, memory_dir=MEMORY_DIR)
        except RebaseError:
            pass
    last_cmd = mock_run.call_args_list[-1][0][0]
    assert last_cmd == ["git", "rebase", "--abort"]


def test_rebase_error_includes_rebase_keyword():
    """RebaseError message must contain the word 'rebase'."""
    ok = _make_result(0)
    rejected = _make_result(1, stderr="rejected")
    rebase_fail = _make_result(1, stderr="conflict in file.py")
    abort = _make_result(0)
    with patch("subprocess.run", side_effect=[ok, ok, rejected, rebase_fail, abort]):
        with pytest.raises(RebaseError, match="(?i)rebase"):
            commit_and_push("mypkg", 1, memory_dir=MEMORY_DIR)


def test_rebase_error_includes_affected_files():
    """RebaseError message must include file names extracted from git stderr."""
    ok = _make_result(0)
    rejected = _make_result(1, stderr="rejected")
    rebase_fail = _make_result(1, stderr="CONFLICT: Merge conflict in memory/species/my_skill.py")
    abort = _make_result(0)
    with patch("subprocess.run", side_effect=[ok, ok, rejected, rebase_fail, abort]):
        with pytest.raises(RebaseError) as exc_info:
            commit_and_push("mypkg", 1, memory_dir=MEMORY_DIR)
    assert "my_skill.py" in str(exc_info.value)


def test_rebase_error_includes_git_stderr():
    """RebaseError message must include the raw git stderr output."""
    ok = _make_result(0)
    rejected = _make_result(1, stderr="rejected")
    rebase_fail = _make_result(1, stderr="fatal: rebase conflict detail here")
    abort = _make_result(0)
    with patch("subprocess.run", side_effect=[ok, ok, rejected, rebase_fail, abort]):
        with pytest.raises(RebaseError) as exc_info:
            commit_and_push("mypkg", 1, memory_dir=MEMORY_DIR)
    assert "fatal: rebase conflict detail here" in str(exc_info.value)
