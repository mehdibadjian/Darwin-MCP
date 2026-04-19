"""Context Buffer / Flash Summarizer — Cloud-less AI plan, Phase 2b.

Compresses web-fetched content to a ≤400-token "Flash Report" before it
is sent over Meshnet to Gemma 2b. Uses extractive sentence ranking by
keyword density — no external LLM or API required.
"""
from __future__ import annotations

import re
from typing import Optional


# Rough characters-per-token for English text (GPT/Gemma tokenisers average ~4 chars/token).
_CHARS_PER_TOKEN: float = 4.0
_DEFAULT_TOKEN_BUDGET: int = 400


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences on common terminators."""
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if len(p.strip()) > 20]


def _keyword_density(sentence_tokens: list[str], query_tokens: set[str]) -> float:
    """Fraction of sentence tokens that appear in the query."""
    if not sentence_tokens:
        return 0.0
    hits = sum(1 for t in sentence_tokens if t in query_tokens)
    return hits / len(sentence_tokens)


def _score_sentences(
    sentences: list[str],
    query_tokens: set[str],
) -> list[tuple[float, int, str]]:
    """Return (score, original_index, sentence) sorted by descending score."""
    scored = []
    for i, sentence in enumerate(sentences):
        tokens = _tokenize(sentence)
        density = _keyword_density(tokens, query_tokens)
        # Bonus for sentences near the start (lead bias).
        position_bonus = max(0.0, 0.1 - i * 0.01)
        scored.append((density + position_bonus, i, sentence))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored


def flash_report(
    text: str,
    query: str = "",
    token_budget: int = _DEFAULT_TOKEN_BUDGET,
) -> str:
    """Summarise *text* into a Flash Report of at most *token_budget* tokens.

    Strategy: extractive sentence selection by keyword density against *query*.
    Sentences are re-ordered by their original position for readability.

    Args:
        text:         Raw fetched page content.
        query:        The original search query (used for scoring).
        token_budget: Maximum output tokens (default 400).

    Returns:
        A condensed string. If *text* already fits within the budget, it is
        returned unchanged.
    """
    if not text:
        return ""

    char_budget = int(token_budget * _CHARS_PER_TOKEN)

    # Fast path: already fits.
    if len(text) <= char_budget:
        return text

    sentences = _split_sentences(text)
    if not sentences:
        return text[:char_budget]

    query_tokens = set(_tokenize(query)) if query else set()

    scored = _score_sentences(sentences, query_tokens)

    # Greedily pick sentences until we hit the budget, then re-sort by index.
    selected: list[tuple[int, str]] = []
    used_chars = 0
    for _, idx, sentence in scored:
        cost = len(sentence) + 1  # +1 for separator
        if used_chars + cost > char_budget:
            break
        selected.append((idx, sentence))
        used_chars += cost

    if not selected:
        # Fallback: hard-truncate at char_budget.
        return text[:char_budget] + "…"

    # Restore reading order.
    selected.sort(key=lambda x: x[0])
    return " ".join(s for _, s in selected)


def compress_search_results(
    results: list[dict],
    query: str = "",
    token_budget: int = _DEFAULT_TOKEN_BUDGET,
) -> list[dict]:
    """Add a ``flash_report`` key to each result dict that has a ``text`` field.

    The original ``text`` field is preserved for backward compatibility.
    Results without a ``text`` field are passed through unchanged.

    Args:
        results:      List of search result dicts from /search endpoint.
        query:        Original query string for relevance scoring.
        token_budget: Per-result token budget for flash reports.

    Returns:
        The same list with ``flash_report`` added in-place where applicable.
    """
    for result in results:
        if result.get("text"):
            result["flash_report"] = flash_report(
                result["text"], query=query, token_budget=token_budget
            )
    return results
