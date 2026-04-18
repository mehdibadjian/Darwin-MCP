"""Circuit breaker guard for mutation recursion depth — US-24."""
import os
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


def check_recursion_depth(depth: int, skill_name: str, github_token: Optional[str] = None, repo: Optional[str] = None) -> bool:
    """Check if recursion depth exceeds the limit.

    Opens a GitHub Issue and raises RecursionLimitError if depth > MAX_RECURSION_DEPTH.
    Returns True if depth <= MAX_RECURSION_DEPTH.
    """
    if depth > MAX_RECURSION_DEPTH:
        open_github_issue(skill_name, depth, github_token=github_token, repo=repo)
        raise RecursionLimitError(depth=depth, skill_name=skill_name)
    return True
