"""Semantic similarity engine — gene-duplication prevention for Darwin-MCP.

Before evolving a new skill, the Inquiry phase asks:
    "Do we already have a tool that does something semantically similar?"

If yes, it returns a SemanticMatch suggesting adaptation over creation.
This prevents the Genome from accumulating redundant species (gene duplication).

Strategy (two-pass, no external dependencies):
  1. Name similarity — difflib token ratio on name-only tokens.
     Threshold: SIMILARITY_THRESHOLD (0.55).  Exact name match → 1.0.
  2. Description overlap — Jaccard coefficient on description word sets,
     after filtering common stop-words.
     Threshold: DESCRIPTION_THRESHOLD (0.25).  Catches paraphrases like
     "excel_to_json" ↔ "csv_parser" where descriptions share key domain words
     ("converts", "rows", "json") even though names do not overlap.

A future upgrade can replace the Jaccard pass with an embedding-based cosine
similarity without changing the public API.
"""
from __future__ import annotations

import dataclasses
import difflib
import re
from typing import Optional


# Threshold for name-level token similarity.
SIMILARITY_THRESHOLD: float = 0.55

# Lower threshold for description-level Jaccard overlap.
_DESCRIPTION_THRESHOLD: float = 0.20

# Common stop-words excluded from description Jaccard to reduce noise.
_STOP_WORDS = frozenset(
    "a an the and or of to in is are was were it its for from with on by be "
    "that this which have has had do does did will can could would should may "
    "might shall at as all into out up are".split()
)


@dataclasses.dataclass
class SemanticMatch:
    """Describes a detected near-duplicate between the requested skill and an existing one."""

    existing_skill: str
    score: float
    suggestion: str


def _tokenize(text: str) -> list[str]:
    """Lower-case and split *text* into word tokens, stripping punctuation."""
    return re.findall(r"[a-z0-9]+", text.lower())


def _name_tokens(name: str) -> list[str]:
    """Split a snake_case name into constituent word tokens."""
    return re.findall(r"[a-z0-9]+", name.lower())


def _desc_word_set(description: str) -> set[str]:
    """Return a filtered set of meaningful words from *description*."""
    return {
        w for w in re.findall(r"[a-z0-9]+", description.lower())
        if w not in _STOP_WORDS and len(w) > 2
    }


def _name_similarity(a: str, b: str) -> float:
    """Token-sequence similarity between two snake_case names."""
    return difflib.SequenceMatcher(None, _name_tokens(a), _name_tokens(b)).ratio()


def _jaccard(set_a: set, set_b: set) -> float:
    """Jaccard coefficient: |A ∩ B| / |A ∪ B|. Returns 0.0 for empty inputs."""
    union = set_a | set_b
    if not union:
        return 0.0
    return len(set_a & set_b) / len(union)


def check_semantic_similarity(
    name: str,
    registry: dict,
    description: str = "",
) -> Optional[SemanticMatch]:
    """Compare *name* + *description* against all active registry skills.

    Pass 1 — name similarity:
        If difflib token ratio between *name* and an existing skill name
        is ≥ SIMILARITY_THRESHOLD (0.55), return a SemanticMatch with that score.

    Pass 2 — description overlap:
        If Jaccard coefficient between the filtered word sets of the two
        descriptions is ≥ _DESCRIPTION_THRESHOLD (0.20), return a SemanticMatch.

    Toxic skills are excluded from both passes.

    Args:
        name:        Requested skill name (snake_case).
        registry:    Registry dict with a ``"skills"`` key.
        description: Optional natural-language description of the new skill.

    Returns:
        SemanticMatch (highest-scoring match) or None.
    """
    skills: dict = registry.get("skills", {})
    if not skills:
        return None

    req_desc_words = _desc_word_set(description)

    best_skill: Optional[str] = None
    best_score: float = 0.0
    best_via_desc: bool = False

    for existing_name, entry in skills.items():
        if entry.get("status") == "Toxic":
            continue

        # Pass 1 — name similarity
        ns = _name_similarity(name, existing_name)
        if ns >= SIMILARITY_THRESHOLD and ns > best_score:
            best_score = ns
            best_skill = existing_name
            best_via_desc = False
            continue

        # Pass 2 — description Jaccard (only when a description was supplied)
        if description:
            existing_desc = entry.get("description", "")
            ex_desc_words = _desc_word_set(existing_desc)
            js = _jaccard(req_desc_words, ex_desc_words)
            if js >= _DESCRIPTION_THRESHOLD and js > best_score:
                best_score = js
                best_skill = existing_name
                best_via_desc = True

    if best_skill is None:
        return None

    suggestion = (
        f"A similar skill '{best_skill}' already exists "
        f"(similarity={best_score:.2f}). "
        f"Consider adapting it instead of creating a new species to avoid gene duplication."
    )
    return SemanticMatch(
        existing_skill=best_skill,
        score=best_score,
        suggestion=suggestion,
    )
