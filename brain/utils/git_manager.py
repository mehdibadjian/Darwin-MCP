"""Git Manager for Darwin-God-MCP — US-13, US-14, US-15, US-16.

Handles: git add → commit (evolution: {name} v{version}) → push to origin main,
with automatic pull --rebase + retry on push rejection.
"""
import re
import subprocess
from pathlib import Path


class GitError(Exception):
    pass


class PushRejectedError(GitError):
    pass


class RebaseError(GitError):
    pass


def _run_git(args, cwd, timeout=30):
    """Run a git command in cwd. Returns (returncode, stdout, stderr)."""
    result = subprocess.run(
        ["git"] + args,
        capture_output=True, text=True, timeout=timeout, cwd=str(cwd)
    )
    return result.returncode, result.stdout, result.stderr


def commit_and_push(name, version, memory_dir=None):
    """Execute git add ., commit with 'evolution: {name} v{version}', push to origin main.

    Handles push rejection via pull --rebase + retry.
    Returns (success: bool, message: str).
    """
    if memory_dir is None:
        memory_dir = Path(__file__).resolve().parent.parent.parent / "memory"
    memory_dir = Path(memory_dir)

    # git add .
    rc, stdout, stderr = _run_git(["add", "."], cwd=memory_dir)
    if rc != 0:
        raise GitError(f"git add failed: {stderr}")

    # git commit
    message = f"evolution: {name} v{version}"
    rc, stdout, stderr = _run_git(["commit", "-m", message], cwd=memory_dir)
    if rc != 0:
        raise GitError(f"git commit failed: {stderr}")

    # git push
    rc, stdout, stderr = _run_git(["push", "origin", "main"], cwd=memory_dir)
    if rc == 0:
        return True, f"Pushed: {message}"

    # Push rejected — try pull --rebase
    rc_rebase, stdout_rebase, stderr_rebase = _run_git(
        ["pull", "--rebase", "origin", "main"], cwd=memory_dir
    )
    if rc_rebase != 0:
        # Rebase failed — abort to leave repo in clean state
        _run_git(["rebase", "--abort"], cwd=memory_dir)
        files = re.findall(r"[\w/.-]+\.py", stderr_rebase)
        raise RebaseError(
            f"rebase failed during push conflict resolution. "
            f"Affected files: {files}. Git output: {stderr_rebase}"
        )

    # Retry push after successful rebase
    rc2, stdout2, stderr2 = _run_git(["push", "origin", "main"], cwd=memory_dir)
    if rc2 != 0:
        raise PushRejectedError(f"Retry push failed after rebase: {stderr2}")
    return True, f"Pushed after rebase: {message}"
