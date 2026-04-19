"""Dynamic Tool Router — Cloud-less AI plan, Phase 1a.

Scores registry skills against a query using TF-IDF-style keyword overlap
and returns only the top-N most relevant tools. Keeps Gemma 2b's visible
tool list small enough to prevent hallucination.
"""
from __future__ import annotations

import math
import re
from typing import Optional


def _tokenize(text: str) -> list[str]:
    """Lowercase, strip punctuation, split on whitespace."""
    return re.findall(r"[a-z0-9]+", text.lower())


def _tf(tokens: list[str]) -> dict[str, float]:
    total = len(tokens) or 1
    freq: dict[str, int] = {}
    for t in tokens:
        freq[t] = freq.get(t, 0) + 1
    return {t: c / total for t, c in freq.items()}


def _idf(term: str, documents: list[list[str]]) -> float:
    n_docs = len(documents)
    n_containing = sum(1 for doc in documents if term in doc)
    return math.log((n_docs + 1) / (n_containing + 1)) + 1.0


def _score(query_tokens: list[str], doc_tokens: list[str], all_docs: list[list[str]]) -> float:
    """TF-IDF cosine-like score between query and a single document."""
    if not query_tokens or not doc_tokens:
        return 0.0
    doc_tf = _tf(doc_tokens)
    score = 0.0
    for term in set(query_tokens):
        if term in doc_tf:
            idf = _idf(term, all_docs)
            score += doc_tf[term] * idf
    return score


def route_tools(
    query: str,
    tools: dict,
    top_n: int = 3,
    description_key: str = "short_description",
) -> dict:
    """Return the *top_n* most query-relevant tools from *tools*.

    Args:
        query: The user's raw query string.
        tools: Full skill dict from registry.json (name → entry).
        top_n: Maximum number of tools to expose.
        description_key: Registry field to use for scoring. Falls back to
                         ``description`` if ``short_description`` is absent.

    Returns:
        A filtered dict with at most *top_n* entries.
    """
    if not query or not tools:
        # Return up to top_n tools when there's no query to score against.
        return dict(list(tools.items())[:top_n])

    query_tokens = _tokenize(query)

    # Build per-tool description corpus for IDF calculation.
    tool_entries = list(tools.items())
    documents: list[list[str]] = []
    for _, entry in tool_entries:
        desc = entry.get(description_key) or entry.get("description", "")
        documents.append(_tokenize(desc))

    # Score each tool.
    scored: list[tuple[float, str, dict]] = []
    for i, (name, entry) in enumerate(tool_entries):
        s = _score(query_tokens, documents[i], documents)
        # Tie-break: include the tool name itself as a bonus signal.
        name_bonus = 0.5 if any(t in _tokenize(name) for t in query_tokens) else 0.0
        scored.append((s + name_bonus, name, entry))

    scored.sort(key=lambda x: x[0], reverse=True)
    return {name: entry for _, name, entry in scored[:top_n]}


def get_routed_tools(
    query: Optional[str],
    registry: dict,
    top_n: int = 3,
) -> dict:
    """Convenience wrapper used by sse_server.

    Filters out Toxic skills first, then delegates to :func:`route_tools`.
    Returns all non-Toxic tools (up to *top_n*) when *query* is empty.
    """
    active_tools = {
        name: entry
        for name, entry in registry.get("skills", {}).items()
        if entry.get("status") != "Toxic"
    }
    return route_tools(query or "", active_tools, top_n=top_n)
