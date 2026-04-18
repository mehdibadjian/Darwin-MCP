"""Circuit breaker guard for mutation recursion depth — US-24.
Resource monitor with SIGKILL and Toxic flag — US-25, US-26.
"""
import os
import signal
import threading
import time
import logging
from typing import Optional

MAX_RECURSION_DEPTH = 3

logger = logging.getLogger(__name__)


class RecursionLimitError(Exception):
    """Raised when mutation recursion depth exceeds MAX_RECURSION_DEPTH."""

    def __init__(self, depth: int, skill_name: str):
        self.depth = depth
        self.skill_name = skill_name
        super().__init__(
            f"Recursion limit exceeded: depth={depth} for skill '{skill_name}'"
        )


def open_github_issue(skill_name: str, depth: int, github_token: Optional[str] = None, repo: Optional[str] = None):
    """Open a GitHub Issue to report runaway mutation recursion.

    Returns (success: bool, issue_url: str).
    """
    import urllib.request
    import json

    token = github_token or os.environ.get("GITHUB_TOKEN", "")
    repo = repo or os.environ.get("GITHUB_REPO", "")

    if not token or not repo:
        logger.warning("GITHUB_TOKEN or GITHUB_REPO not set — skipping issue creation")
        return False, ""

    url = f"https://api.github.com/repos/{repo}/issues"
    payload = json.dumps({
        "title": f"[Circuit Breaker] Runaway mutation: {skill_name} depth={depth}",
        "body": (
            f"The mutation pipeline for skill `{skill_name}` reached recursion depth "
            f"{depth} (limit: {MAX_RECURSION_DEPTH}). The chain has been halted automatically.\n\n"
            "Manual review required before re-enabling this skill."
        ),
        "labels": ["circuit-breaker", "safety"],
    }).encode()

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"token {token}",
            "Content-Type": "application/json",
            "Accept": "application/vnd.github.v3+json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return True, data.get("html_url", "")
    except Exception as e:
        logger.error(f"Failed to open GitHub issue: {e}")
        return False, ""


# ---------------------------------------------------------------------------
# US-25 / US-26 — Resource monitor
# ---------------------------------------------------------------------------

CPU_LIMIT_PERCENT = 80.0
RAM_LIMIT_MB = 256.0


class ResourceLimitError(Exception):
    """Raised when a subprocess exceeds CPU or RAM limits."""

    def __init__(self, pid: int, reason: str):
        self.pid = pid
        self.reason = reason
        super().__init__(f"Resource limit exceeded for PID {pid}: {reason}")


def _get_process_stats(pid: int):
    """Return (cpu_percent, ram_mb) for *pid*. Returns (0.0, 0.0) if process is gone."""
    try:
        import psutil
        p = psutil.Process(pid)
        cpu = p.cpu_percent(interval=0.1)
        ram = p.memory_info().rss / (1024 * 1024)
        return cpu, ram
    except Exception:
        return 0.0, 0.0


def monitor_subprocess(
    pid: int,
    skill_name: str,
    registry_path=None,
    cpu_limit: float = CPU_LIMIT_PERCENT,
    ram_limit: float = RAM_LIMIT_MB,
    poll_interval: float = 0.5,
    stop_event: Optional[threading.Event] = None,
) -> None:
    """Monitor *pid* in a loop; send SIGKILL and mark Toxic if limits exceeded.

    Designed to run in a background thread. *stop_event* can be set externally
    to stop the monitor cleanly.
    """
    if stop_event is None:
        stop_event = threading.Event()

    while not stop_event.is_set():
        cpu, ram = _get_process_stats(pid)
        reason: Optional[str] = None
        if cpu > cpu_limit:
            reason = f"CPU {cpu:.1f}% > limit {cpu_limit}%"
        elif ram > ram_limit:
            reason = f"RAM {ram:.1f} MB > limit {ram_limit} MB"

        if reason:
            logger.warning(f"Killing PID {pid} ({skill_name}): {reason}")
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            mark_toxic(skill_name, reason, registry_path=registry_path)
            stop_event.set()
            raise ResourceLimitError(pid=pid, reason=reason)

        if poll_interval:
            time.sleep(poll_interval)


def mark_toxic(skill_name: str, reason: str = "resource limit exceeded", registry_path=None) -> dict:
    """Mark *skill_name* as Toxic in registry.json and return the updated registry."""
    from brain.utils.registry import read_registry, write_registry, init_registry
    init_registry(registry_path)
    registry = read_registry(registry_path)
    if skill_name in registry.get("skills", {}):
        registry["skills"][skill_name]["status"] = "Toxic"
        registry["skills"][skill_name]["toxic_reason"] = reason
        write_registry(registry, registry_path)
    return registry


# ---------------------------------------------------------------------------
# US-24 — Recursion depth check
# ---------------------------------------------------------------------------

def check_recursion_depth(depth: int, skill_name: str, github_token: Optional[str] = None, repo: Optional[str] = None) -> bool:
    """Check if recursion depth exceeds the limit.

    Opens a GitHub Issue and raises RecursionLimitError if depth > MAX_RECURSION_DEPTH.
    Returns True if depth <= MAX_RECURSION_DEPTH.
    """
    if depth > MAX_RECURSION_DEPTH:
        open_github_issue(skill_name, depth, github_token=github_token, repo=repo)
        raise RecursionLimitError(depth=depth, skill_name=skill_name)
    return True
