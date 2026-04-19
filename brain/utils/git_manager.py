"""Git Manager for Darwin-MCP — US-13, US-14, US-15, US-16, ENH-US8.

Handles: git add → commit (evolution: {name} v{version}) → push to origin main,
with automatic pull --rebase + retry on push rejection.

ENH-US8: Dynamic vault submodule mounting with thread-safe caching.
Submodule Handshake: Two-Stage Local Commit keeps the Brain in sync with Memory.
"""
import logging
import re
import subprocess
import threading
from pathlib import Path


class GitError(Exception):
    pass


class PushRejectedError(GitError):
    pass


class RebaseError(GitError):
    pass


class VaultNotFoundError(GitError):
    """Raised when a vault submodule path does not exist."""


SUBMODULES_DIR_NAME = "submodules"

_vault_cache: dict = {}
_vault_cache_lock = threading.Lock()


def resolve_vault(vault_id, memory_dir=None) -> Path:
    """Resolve vault_id to an absolute Path.

    - vault_id=None or "" → returns memory_dir (primary vault)
    - vault_id="web-dev-vault" → returns memory_dir/submodules/web-dev-vault
    - Raises VaultNotFoundError if the resolved path doesn't exist
    - Caches resolved paths keyed by (vault_id, str(memory_dir))
    """
    if memory_dir is None:
        memory_dir = Path(__file__).resolve().parent.parent.parent / "memory"
    memory_dir = Path(memory_dir)

    if not vault_id:
        return memory_dir

    cache_key = (vault_id, str(memory_dir))
    with _vault_cache_lock:
        if cache_key in _vault_cache:
            return _vault_cache[cache_key]

    path = memory_dir / SUBMODULES_DIR_NAME / vault_id
    if not path.exists():
        raise VaultNotFoundError(f"Vault '{vault_id}' not found at {path}")

    with _vault_cache_lock:
        _vault_cache[cache_key] = path
    return path


def invalidate_vault_cache(vault_id=None) -> None:
    """Remove vault_id from cache (or clear all if None)."""
    with _vault_cache_lock:
        if vault_id is None:
            _vault_cache.clear()
        else:
            keys_to_remove = [k for k in _vault_cache if k[0] == vault_id]
            for k in keys_to_remove:
                del _vault_cache[k]


def _run_git(args, cwd, timeout=30):
    """Run a git command in cwd. Returns (returncode, stdout, stderr)."""
    result = subprocess.run(
        ["git"] + args,
        capture_output=True, text=True, timeout=timeout, cwd=str(cwd)
    )
    return result.returncode, result.stdout, result.stderr


def sync_submodule_pointer(vault_cwd: Path, brain_root=None) -> None:
    """Stage 2 of the Submodule Handshake.

    After committing inside the vault (submodule), call this to record the
    new submodule pointer in the parent Brain repository:

        git rev-parse HEAD          (inside vault — capture new commit hash)
        git add <submodule_name>    (inside brain root)
        git commit -m "chore: sync vault at <short_hash>"

    Silently skips when there is nothing new to commit (pointer already
    current).  Raises GitError on any unexpected failure.
    """
    vault_cwd = Path(vault_cwd)
    parent_root = Path(brain_root) if brain_root else vault_cwd.parent
    submodule_name = vault_cwd.name

    rc, hash_out, _ = _run_git(["rev-parse", "HEAD"], cwd=vault_cwd)
    short_hash = hash_out.strip()[:7] if rc == 0 else "unknown"

    _run_git(["add", submodule_name], cwd=parent_root)
    rc_commit, _, stderr_commit = _run_git(
        ["commit", "-m", f"chore: sync vault at {short_hash}"],
        cwd=parent_root,
    )
    if rc_commit != 0 and "nothing to commit" not in stderr_commit:
        raise GitError(f"Submodule pointer sync failed: {stderr_commit}")
    logging.info("Submodule pointer updated: %s → %s", submodule_name, short_hash)


def commit_and_push(name, version, memory_dir=None, vault_id=None, sync_parent=False, brain_root=None):
    """Execute git add ., commit with 'evolution: {name} v{version}', push to origin main.

    Pre-push preflight (US-H2): fetch → checkout main → pull --rebase, then
    add → commit → push. This prevents Detached HEAD failures and merges any
    concurrent remote changes before creating the new commit.

    If vault_id is provided, resolves vault path via resolve_vault().
    Otherwise uses memory_dir (backward compatible).
    Handles push rejection via pull --rebase + retry.

    When sync_parent=True, performs the Two-Stage Submodule Handshake after a
    successful push: updates the Brain's submodule pointer to the new vault
    commit so `git submodule status` shows no stale '+' marker.

    Returns (success: bool, message: str).
    """
    if vault_id is not None:
        cwd = resolve_vault(vault_id, memory_dir=memory_dir)
    else:
        if memory_dir is None:
            memory_dir = Path(__file__).resolve().parent.parent.parent / "memory"
        cwd = Path(memory_dir)

    # --- Pre-push preflight: sync with remote and land on main branch ---

    # git fetch origin
    rc, stdout, stderr = _run_git(["fetch", "origin"], cwd=cwd)
    if rc != 0:
        raise GitError(f"git fetch origin failed: {stderr}")

    # git checkout main — resolves Detached HEAD
    rc, stdout, stderr = _run_git(["checkout", "main"], cwd=cwd)
    if rc != 0:
        raise GitError(f"git checkout main failed: {stderr}")

    # git pull --rebase --autostash origin main — stashes pending writes, rebases,
    # then restores; prevents "unstaged changes" rejection when registry.json has
    # already been written by the mutator before this preflight runs.
    rc, stdout, stderr = _run_git(["pull", "--rebase", "--autostash", "origin", "main"], cwd=cwd)
    if rc != 0:
        _run_git(["rebase", "--abort"], cwd=cwd)
        files = re.findall(r"[\w/.-]+\.py", stderr)
        raise RebaseError(
            f"rebase failed during pre-push preflight. "
            f"Affected files: {files}. Git output: {stderr}"
        )

    # --- Stage, commit, push ---

    # git add .
    rc, stdout, stderr = _run_git(["add", "."], cwd=cwd)
    if rc != 0:
        raise GitError(f"git add failed: {stderr}")

    # git commit
    message = f"evolution: {name} v{version}"
    rc, stdout, stderr = _run_git(["commit", "-m", message], cwd=cwd)
    if rc != 0:
        raise GitError(f"git commit failed: {stderr}")

    # git push
    rc, stdout, stderr = _run_git(["push", "origin", "main"], cwd=cwd)
    if rc == 0:
        if sync_parent:
            sync_submodule_pointer(cwd, brain_root=brain_root)
        return True, f"Pushed: {message}"

    # Push rejected — try pull --rebase --autostash + retry
    rc_rebase, stdout_rebase, stderr_rebase = _run_git(
        ["pull", "--rebase", "--autostash", "origin", "main"], cwd=cwd
    )
    if rc_rebase != 0:
        _run_git(["rebase", "--abort"], cwd=cwd)
        files = re.findall(r"[\w/.-]+\.py", stderr_rebase)
        raise RebaseError(
            f"rebase failed during push conflict resolution. "
            f"Affected files: {files}. Git output: {stderr_rebase}"
        )

    # Retry push after successful rebase
    rc2, stdout2, stderr2 = _run_git(["push", "origin", "main"], cwd=cwd)
    if rc2 != 0:
        raise PushRejectedError(f"Retry push failed after rebase: {stderr2}")
    if sync_parent:
        sync_submodule_pointer(cwd, brain_root=brain_root)
    return True, f"Pushed after rebase: {message}"
