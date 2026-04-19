"""Tests for brain/utils/git_manager.py — US-13, US-14, US-15, US-16, ENH-US8."""
import subprocess
import threading
from pathlib import Path
from unittest.mock import call, patch, MagicMock

import pytest

from brain.utils.git_manager import (
    GitError,
    PushRejectedError,
    RebaseError,
    VaultNotFoundError,
    commit_and_push,
    resolve_vault,
    invalidate_vault_cache,
    sync_submodule_pointer,
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
# Pre-push preflight adds: fetch(0) → checkout(1) → pull-rebase(2)
# then: add(3) → commit(4) → push(5)
# ---------------------------------------------------------------------------

def test_git_add_runs_in_memory_dir():
    """git add . must be called with cwd=memory_dir (4th command after preflight)."""
    ok = _make_result(0)
    with patch("subprocess.run", return_value=ok) as mock_run:
        commit_and_push("mypkg", 1, memory_dir=MEMORY_DIR)
    add_call = mock_run.call_args_list[3]
    assert add_call[0][0] == ["git", "add", "."]
    assert add_call[1]["cwd"] == str(MEMORY_DIR)


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
    commit_call = mock_run.call_args_list[4]
    assert commit_call[0][0] == ["git", "commit", "-m", "evolution: pdf_parser v1"]


def test_commit_message_no_extra_text():
    """Commit message must contain ONLY 'evolution: {name} v{version}'."""
    ok = _make_result(0)
    with patch("subprocess.run", return_value=ok) as mock_run:
        commit_and_push("pdf_parser", 1, memory_dir=MEMORY_DIR)
    commit_call = mock_run.call_args_list[4]
    msg = commit_call[0][0][3]  # 4th element of git commit -m <msg>
    assert msg == "evolution: pdf_parser v1"


def test_commit_message_version_incremented():
    """Version number in commit message reflects the version argument."""
    ok = _make_result(0)
    with patch("subprocess.run", return_value=ok) as mock_run:
        commit_and_push("pdf_parser", 3, memory_dir=MEMORY_DIR)
    commit_call = mock_run.call_args_list[4]
    assert commit_call[0][0][3] == "evolution: pdf_parser v3"


# ---------------------------------------------------------------------------
# US-15 — push rejection → pull --rebase → retry
# ---------------------------------------------------------------------------

def test_push_rejection_triggers_rebase():
    """When push fails with 'rejected', git pull --rebase must be called."""
    ok = _make_result(0)
    rejected = _make_result(1, stderr="error: failed to push some refs (rejected)")
    # fetch, checkout, pull-rebase → ok; add, commit → ok; push → rejected; pull-rebase → ok; retry push → ok
    with patch("subprocess.run", side_effect=[ok, ok, ok, ok, ok, rejected, ok, ok]) as mock_run:
        commit_and_push("mypkg", 1, memory_dir=MEMORY_DIR)
    cmds = [c[0][0] for c in mock_run.call_args_list]
    assert ["git", "pull", "--rebase", "--autostash", "origin", "main"] in cmds


def test_rebase_success_retries_push():
    """After successful rebase, git push origin main must be called a second time."""
    ok = _make_result(0)
    rejected = _make_result(1, stderr="rejected")
    with patch("subprocess.run", side_effect=[ok, ok, ok, ok, ok, rejected, ok, ok]) as mock_run:
        commit_and_push("mypkg", 1, memory_dir=MEMORY_DIR)
    push_calls = [c for c in mock_run.call_args_list if c[0][0] == ["git", "push", "origin", "main"]]
    assert len(push_calls) == 2


def test_retry_push_failure_raises_error():
    """If the retry push also fails, PushRejectedError must be raised."""
    ok = _make_result(0)
    rejected = _make_result(1, stderr="rejected")
    with patch("subprocess.run", side_effect=[ok, ok, ok, ok, ok, rejected, ok, rejected]):
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
    with patch("subprocess.run", side_effect=[ok, ok, ok, ok, ok, rejected, rebase_fail, abort]):
        with pytest.raises(RebaseError):
            commit_and_push("mypkg", 1, memory_dir=MEMORY_DIR)
    # last call must be rebase --abort
    with patch("subprocess.run", side_effect=[ok, ok, ok, ok, ok, rejected, rebase_fail, abort]) as mock_run:
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
    with patch("subprocess.run", side_effect=[ok, ok, ok, ok, ok, rejected, rebase_fail, abort]):
        with pytest.raises(RebaseError, match="(?i)rebase"):
            commit_and_push("mypkg", 1, memory_dir=MEMORY_DIR)


def test_rebase_error_includes_affected_files():
    """RebaseError message must include file names extracted from git stderr."""
    ok = _make_result(0)
    rejected = _make_result(1, stderr="rejected")
    rebase_fail = _make_result(1, stderr="CONFLICT: Merge conflict in memory/species/my_skill.py")
    abort = _make_result(0)
    with patch("subprocess.run", side_effect=[ok, ok, ok, ok, ok, rejected, rebase_fail, abort]):
        with pytest.raises(RebaseError) as exc_info:
            commit_and_push("mypkg", 1, memory_dir=MEMORY_DIR)
    assert "my_skill.py" in str(exc_info.value)


def test_rebase_error_includes_git_stderr():
    """RebaseError message must include the raw git stderr output."""
    ok = _make_result(0)
    rejected = _make_result(1, stderr="rejected")
    rebase_fail = _make_result(1, stderr="fatal: rebase conflict detail here")
    abort = _make_result(0)
    with patch("subprocess.run", side_effect=[ok, ok, ok, ok, ok, rejected, rebase_fail, abort]):
        with pytest.raises(RebaseError) as exc_info:
            commit_and_push("mypkg", 1, memory_dir=MEMORY_DIR)
    assert "fatal: rebase conflict detail here" in str(exc_info.value)


# ---------------------------------------------------------------------------
# ENH-US8 — Dynamic Git Submodule Mounting
# ---------------------------------------------------------------------------

def test_resolve_vault_none_returns_memory_dir(tmp_path):
    """vault_id=None → returns memory_dir itself (must exist)."""
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir()
    result = resolve_vault(None, memory_dir=memory_dir)
    assert result == memory_dir


def test_resolve_vault_valid_id(tmp_path):
    """resolve_vault('web-dev-vault', memory_dir) → memory_dir/submodules/web-dev-vault."""
    memory_dir = tmp_path / "memory"
    vault_path = memory_dir / "submodules" / "web-dev-vault"
    vault_path.mkdir(parents=True)
    invalidate_vault_cache()
    result = resolve_vault("web-dev-vault", memory_dir=memory_dir)
    assert result == vault_path


def test_resolve_vault_invalid_id_raises(tmp_path):
    """Path doesn't exist → VaultNotFoundError."""
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir()
    invalidate_vault_cache()
    with pytest.raises(VaultNotFoundError, match="web-dev-vault"):
        resolve_vault("web-dev-vault", memory_dir=memory_dir)


def test_resolve_vault_caches_result(tmp_path):
    """Second call with same vault_id returns cached Path without extra filesystem stat."""
    memory_dir = tmp_path / "memory"
    vault_path = memory_dir / "submodules" / "my-vault"
    vault_path.mkdir(parents=True)
    invalidate_vault_cache()

    first = resolve_vault("my-vault", memory_dir=memory_dir)
    # Remove the directory — if cache works, second call must NOT raise
    vault_path.rmdir()
    second = resolve_vault("my-vault", memory_dir=memory_dir)
    assert first == second


def test_invalidate_vault_cache_clears_entry(tmp_path):
    """After invalidate, next call re-resolves from filesystem."""
    memory_dir = tmp_path / "memory"
    vault_path = memory_dir / "submodules" / "my-vault"
    vault_path.mkdir(parents=True)
    invalidate_vault_cache()

    resolve_vault("my-vault", memory_dir=memory_dir)
    # Remove dir and invalidate — next call must raise because path gone
    vault_path.rmdir()
    invalidate_vault_cache("my-vault")
    with pytest.raises(VaultNotFoundError):
        resolve_vault("my-vault", memory_dir=memory_dir)


def test_commit_and_push_uses_vault_path(tmp_path):
    """commit_and_push with vault_id uses resolved submodule path as cwd."""
    memory_dir = tmp_path / "memory"
    vault_path = memory_dir / "submodules" / "web-dev-vault"
    vault_path.mkdir(parents=True)
    invalidate_vault_cache()

    ok = _make_result(0)
    with patch("subprocess.run", return_value=ok) as mock_run:
        commit_and_push("mypkg", 1, memory_dir=memory_dir, vault_id="web-dev-vault")

    cwds = [c[1]["cwd"] for c in mock_run.call_args_list]
    assert all(cwd == str(vault_path) for cwd in cwds)


# ---------------------------------------------------------------------------
# US-H2 — Pre-push preflight: fetch → checkout main → pull --rebase
# ---------------------------------------------------------------------------

def test_preflight_fetch_is_first_command():
    """git fetch origin must be the very first command called."""
    ok = _make_result(0)
    with patch("subprocess.run", return_value=ok) as mock_run:
        commit_and_push("mypkg", 1, memory_dir=MEMORY_DIR)
    first = mock_run.call_args_list[0][0][0]
    assert first == ["git", "fetch", "origin"]


def test_preflight_checkout_main_is_second():
    """git checkout main must be the second command (after fetch)."""
    ok = _make_result(0)
    with patch("subprocess.run", return_value=ok) as mock_run:
        commit_and_push("mypkg", 1, memory_dir=MEMORY_DIR)
    second = mock_run.call_args_list[1][0][0]
    assert second == ["git", "checkout", "main"]


def test_preflight_pull_rebase_is_third():
    """git pull --rebase --autostash origin main must be the third command."""
    ok = _make_result(0)
    with patch("subprocess.run", return_value=ok) as mock_run:
        commit_and_push("mypkg", 1, memory_dir=MEMORY_DIR)
    third = mock_run.call_args_list[2][0][0]
    assert third == ["git", "pull", "--rebase", "--autostash", "origin", "main"]


def test_preflight_fetch_failure_raises_git_error():
    """If git fetch origin fails, GitError is raised before any commit."""
    fail = _make_result(1, stderr="fatal: repository not found")
    with patch("subprocess.run", return_value=fail):
        with pytest.raises(GitError, match="fetch"):
            commit_and_push("mypkg", 1, memory_dir=MEMORY_DIR)


def test_preflight_checkout_failure_raises_git_error():
    """If git checkout main fails, GitError is raised before git add."""
    ok = _make_result(0)
    fail = _make_result(1, stderr="error: pathspec 'main' did not match")
    with patch("subprocess.run", side_effect=[ok, fail]):
        with pytest.raises(GitError, match="checkout"):
            commit_and_push("mypkg", 1, memory_dir=MEMORY_DIR)


def test_concurrent_vaults_isolated(tmp_path):
    """Two threads using different vault_ids commit to their own paths without interference."""
    memory_dir = tmp_path / "memory"
    vault_a = memory_dir / "submodules" / "vault-a"
    vault_b = memory_dir / "submodules" / "vault-b"
    vault_a.mkdir(parents=True)
    vault_b.mkdir(parents=True)
    invalidate_vault_cache()

    recorded = {"a": [], "b": []}
    ok = _make_result(0)

    def run_a():
        with patch("subprocess.run", return_value=ok) as mock_run:
            commit_and_push("pkg", 1, memory_dir=memory_dir, vault_id="vault-a")
            recorded["a"] = [c[1]["cwd"] for c in mock_run.call_args_list]

    def run_b():
        with patch("subprocess.run", return_value=ok) as mock_run:
            commit_and_push("pkg", 1, memory_dir=memory_dir, vault_id="vault-b")
            recorded["b"] = [c[1]["cwd"] for c in mock_run.call_args_list]

    t1 = threading.Thread(target=run_a)
    t2 = threading.Thread(target=run_b)
    t1.start(); t2.start()
    t1.join(); t2.join()

    assert all(cwd == str(vault_a) for cwd in recorded["a"])
    assert all(cwd == str(vault_b) for cwd in recorded["b"])


# ---------------------------------------------------------------------------
# Two-Stage Submodule Handshake (sync_parent / sync_submodule_pointer)
# ---------------------------------------------------------------------------

BRAIN_ROOT = MEMORY_DIR.parent  # /fake


def test_sync_parent_false_no_parent_commits():
    """Default (sync_parent=False): no rev-parse or parent git add/commit called."""
    ok = _make_result(0)
    with patch("subprocess.run", return_value=ok) as mock_run:
        commit_and_push("mypkg", 1, memory_dir=MEMORY_DIR)
    cmds = [c[0][0] for c in mock_run.call_args_list]
    assert ["git", "rev-parse", "HEAD"] not in cmds


def test_sync_parent_rev_parse_called_after_push():
    """When sync_parent=True, git rev-parse HEAD is called in the vault after push."""
    ok = _make_result(0, stdout="abc1234xyz\n")
    with patch("subprocess.run", return_value=ok) as mock_run:
        commit_and_push("mypkg", 1, memory_dir=MEMORY_DIR, sync_parent=True, brain_root=BRAIN_ROOT)
    cmds = [c[0][0] for c in mock_run.call_args_list]
    assert ["git", "rev-parse", "HEAD"] in cmds


def test_sync_parent_adds_submodule_in_brain_root():
    """Stage 2: git add <submodule_name> must be called with cwd=brain_root."""
    ok = _make_result(0, stdout="abc1234xyz\n")
    with patch("subprocess.run", return_value=ok) as mock_run:
        commit_and_push("mypkg", 1, memory_dir=MEMORY_DIR, sync_parent=True, brain_root=BRAIN_ROOT)
    parent_add_calls = [
        c for c in mock_run.call_args_list
        if c[0][0][:2] == ["git", "add"] and c[1]["cwd"] == str(BRAIN_ROOT)
    ]
    assert len(parent_add_calls) == 1
    assert parent_add_calls[0][0][0][2] == MEMORY_DIR.name  # "memory"


def test_sync_parent_commits_pointer_in_brain_root():
    """Stage 2: chore commit message contains the short hash and targets brain_root."""
    ok = _make_result(0, stdout="abc1234xyz\n")
    with patch("subprocess.run", return_value=ok) as mock_run:
        commit_and_push("mypkg", 1, memory_dir=MEMORY_DIR, sync_parent=True, brain_root=BRAIN_ROOT)
    parent_commits = [
        c for c in mock_run.call_args_list
        if len(c[0][0]) >= 4
        and c[0][0][:3] == ["git", "commit", "-m"]
        and c[1]["cwd"] == str(BRAIN_ROOT)
    ]
    assert len(parent_commits) == 1
    msg = parent_commits[0][0][0][3]
    assert msg.startswith("chore: sync vault at ")
    assert "abc1234" in msg  # first 7 chars of the mocked hash


def test_sync_parent_after_rebase_retry():
    """Stage 2 also runs when push succeeds only after a rebase-retry."""
    ok = _make_result(0, stdout="def5678xyz\n")
    rejected = _make_result(1, stderr="rejected")
    side = [ok, ok, ok, ok, ok, rejected, ok, ok, ok, ok, ok]
    with patch("subprocess.run", side_effect=side) as mock_run:
        commit_and_push("mypkg", 1, memory_dir=MEMORY_DIR, sync_parent=True, brain_root=BRAIN_ROOT)
    parent_commits = [
        c for c in mock_run.call_args_list
        if len(c[0][0]) >= 4
        and c[0][0][:3] == ["git", "commit", "-m"]
        and c[1]["cwd"] == str(BRAIN_ROOT)
    ]
    assert len(parent_commits) == 1


def test_sync_submodule_pointer_standalone(tmp_path):
    """sync_submodule_pointer can be called directly with explicit vault/brain paths."""
    vault = tmp_path / "memory"
    brain = tmp_path
    vault.mkdir()
    ok = _make_result(0, stdout="deadbeef12345\n")
    with patch("subprocess.run", return_value=ok) as mock_run:
        sync_submodule_pointer(vault, brain_root=brain)
    cmds = [c[0][0] for c in mock_run.call_args_list]
    assert ["git", "rev-parse", "HEAD"] in cmds
    assert ["git", "add", "memory"] in cmds
    commit_msgs = [c[0][0][3] for c in mock_run.call_args_list if c[0][0][:3] == ["git", "commit", "-m"]]
    assert any("deadbee" in m for m in commit_msgs)  # first 7 chars of "deadbeef12345"
