"""Multi-Model Validation — Council of Peers (Darwin-MCP).

When a mutation fails 3 consecutive times, the Brain escalates to a secondary
LLM model for a "Peer Review" — asking a different model to diagnose the bug
and suggest a fix.  This drives mutation success rate toward >98%.

Failure counts are tracked in memory (per-process) keyed by skill name.
They reset when the process restarts or when reset_failure_count() is called
after a successful mutation.

Secondary model integration is intentionally thin: _call_secondary_model()
uses the Meshnet bridge config (brain/config/meshnet.json) when available,
falling back to a no-op stub that returns reviewed=False.  Swapping in a
different API (OpenAI, Anthropic, Gemini) requires only implementing the
_build_prompt() / _parse_response() helpers — no changes to the public API.
"""
from __future__ import annotations

import dataclasses
import json
import logging
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Trigger peer review after this many consecutive failures for the same skill.
FAILURE_COUNT_THRESHOLD: int = 3

# Thread-safe in-memory failure counter keyed by skill name.
_failure_counts: dict[str, int] = {}

# ---------------------------------------------------------------------------
# Public counter API
# ---------------------------------------------------------------------------


def get_failure_count(skill_name: str) -> int:
    """Return the current consecutive failure count for *skill_name*."""
    return _failure_counts.get(skill_name, 0)


def increment_failure_count(skill_name: str) -> int:
    """Increment and return the failure count for *skill_name*."""
    _failure_counts[skill_name] = _failure_counts.get(skill_name, 0) + 1
    return _failure_counts[skill_name]


def reset_failure_count(skill_name: str) -> None:
    """Reset the failure count to zero (call after a successful mutation)."""
    _failure_counts.pop(skill_name, None)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class PeerReviewRequest:
    """Encapsulates everything the secondary model needs to diagnose a failure."""

    skill_name: str
    code: str
    tests: str
    error: str


@dataclasses.dataclass
class PeerReviewResult:
    """Result returned by the secondary model review."""

    reviewed: bool
    fixed_code: Optional[str]
    explanation: Optional[str]


# ---------------------------------------------------------------------------
# Secondary model bridge
# ---------------------------------------------------------------------------


def _build_prompt(request: PeerReviewRequest) -> str:
    return (
        f"You are a senior software engineer reviewing a failing Python skill.\n\n"
        f"Skill name: {request.skill_name}\n\n"
        f"Code:\n```python\n{request.code}\n```\n\n"
        f"Tests:\n```python\n{request.tests}\n```\n\n"
        f"Failure error:\n{request.error}\n\n"
        "Please diagnose the bug and provide corrected Python code. "
        "Reply in JSON: {\"fixed_code\": \"<code>\", \"explanation\": \"<reason>\"}"
    )


def _call_secondary_model(request: PeerReviewRequest) -> PeerReviewResult:
    """Call the local Ollama model (gemma:2b) configured in brain/config/meshnet.json.

    Falls back to a stub (reviewed=False) when Ollama is unavailable.
    """
    try:
        from brain.utils.ollama_client import chat as ollama_chat

        prompt = _build_prompt(request)
        raw = ollama_chat(prompt, timeout=60)
        if not raw:
            return PeerReviewResult(reviewed=False, fixed_code=None, explanation="Ollama returned empty response")

        # Try to parse JSON from the response
        try:
            # Extract JSON block if wrapped in markdown
            json_match = re.search(r'\{.*"fixed_code".*\}', raw, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
            else:
                parsed = json.loads(raw)
            return PeerReviewResult(
                reviewed=True,
                fixed_code=parsed.get("fixed_code"),
                explanation=parsed.get("explanation"),
            )
        except json.JSONDecodeError:
            # Ollama returned prose — extract code block if present
            code_match = re.search(r'```python\n(.*?)```', raw, re.DOTALL)
            fixed_code = code_match.group(1).strip() if code_match else None
            return PeerReviewResult(reviewed=bool(fixed_code), fixed_code=fixed_code, explanation=raw[:200])

    except Exception as exc:
        logger.error(f"Peer review call failed for {request.skill_name}: {exc}")
        raise


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def request_peer_review(
    request: PeerReviewRequest,
    current_failure_count: int,
) -> PeerReviewResult:
    """Trigger a peer review if *current_failure_count* >= FAILURE_COUNT_THRESHOLD.

    Returns a PeerReviewResult with reviewed=False if the threshold hasn't been
    reached, or if the secondary model call fails (graceful degradation).

    Args:
        request:              PeerReviewRequest containing skill info + error.
        current_failure_count: Number of consecutive failures so far.

    Returns:
        PeerReviewResult.
    """
    if current_failure_count < FAILURE_COUNT_THRESHOLD:
        return PeerReviewResult(
            reviewed=False,
            fixed_code=None,
            explanation=f"Threshold not reached ({current_failure_count}/{FAILURE_COUNT_THRESHOLD})",
        )

    logger.info(
        "Council of Peers activated for '%s' after %d failures",
        request.skill_name,
        current_failure_count,
    )
    try:
        return _call_secondary_model(request)
    except Exception as exc:
        logger.warning("Peer review failed for %s: %s", request.skill_name, exc)
        return PeerReviewResult(
            reviewed=False,
            fixed_code=None,
            explanation=f"Peer review unavailable: {exc}",
        )
