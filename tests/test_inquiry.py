"""Tests for brain/engine/inquiry.py — semantic similarity / gene-duplication prevention."""
import pytest
from unittest.mock import patch

from brain.engine.inquiry import (
    check_semantic_similarity,
    SemanticMatch,
    SIMILARITY_THRESHOLD,
)


SAMPLE_REGISTRY = {
    "skills": {
        "csv_parser": {
            "status": "active",
            "description": "Parses CSV files and returns a list of dicts",
            "entry_point": "csv_parser",
        },
        "json_formatter": {
            "status": "active",
            "description": "Formats Python dicts as pretty-printed JSON output",
            "entry_point": "json_formatter",
        },
        "hello_world": {
            "status": "active",
            "description": "Prints a greeting message",
            "entry_point": "hello_world",
        },
    }
}


# ---------------------------------------------------------------------------
# Return type
# ---------------------------------------------------------------------------

def test_returns_none_when_no_similar_skill():
    """No match → None (safe to evolve)."""
    result = check_semantic_similarity("calculate_pi", SAMPLE_REGISTRY)
    assert result is None


def test_returns_semantic_match_on_duplicate():
    """An exact name match → SemanticMatch returned."""
    result = check_semantic_similarity("csv_parser", SAMPLE_REGISTRY)
    assert isinstance(result, SemanticMatch)
    assert result.existing_skill == "csv_parser"
    assert result.score >= SIMILARITY_THRESHOLD


# ---------------------------------------------------------------------------
# Gene duplication prevention — the canonical test case from the spec
# ---------------------------------------------------------------------------

def test_excel_to_json_detected_as_similar_to_csv_parser():
    """'excel_to_json' must be flagged as semantically similar to 'csv_parser'."""
    registry = {
        "skills": {
            "csv_parser": {
                "status": "active",
                "description": "Parses CSV files, converts rows to JSON-compatible dicts",
                "entry_point": "csv_parser",
            }
        }
    }
    result = check_semantic_similarity(
        "excel_to_json",
        registry,
        description="Converts Excel spreadsheet rows to JSON objects",
    )
    assert result is not None, (
        "excel_to_json should be detected as similar to csv_parser — adapt, don't duplicate"
    )
    assert result.existing_skill == "csv_parser"
    assert result.suggestion is not None and len(result.suggestion) > 0


def test_completely_different_skill_returns_none():
    """Unrelated skill names produce no match."""
    result = check_semantic_similarity(
        "send_email_notification",
        SAMPLE_REGISTRY,
        description="Sends an email alert via SMTP",
    )
    assert result is None


# ---------------------------------------------------------------------------
# SemanticMatch fields
# ---------------------------------------------------------------------------

def test_semantic_match_has_suggestion_text():
    """SemanticMatch.suggestion must be a non-empty string."""
    result = check_semantic_similarity("csv_parser", SAMPLE_REGISTRY)
    assert isinstance(result.suggestion, str)
    assert len(result.suggestion) > 10


def test_semantic_match_score_between_0_and_1():
    """SemanticMatch.score must be in [0.0, 1.0]."""
    result = check_semantic_similarity("csv_parser", SAMPLE_REGISTRY)
    assert 0.0 <= result.score <= 1.0


# ---------------------------------------------------------------------------
# Threshold constant
# ---------------------------------------------------------------------------

def test_similarity_threshold_is_reasonable():
    """SIMILARITY_THRESHOLD must be set between 0.5 and 0.95."""
    assert 0.5 <= SIMILARITY_THRESHOLD <= 0.95


# ---------------------------------------------------------------------------
# Toxic skills are excluded from similarity search
# ---------------------------------------------------------------------------

def test_toxic_skill_excluded_from_similarity():
    """Toxic skills must not be suggested as adaptation targets."""
    registry = {
        "skills": {
            "csv_parser": {
                "status": "Toxic",
                "description": "Parses CSV files and returns a list of dicts",
                "entry_point": "csv_parser",
            }
        }
    }
    result = check_semantic_similarity("csv_parser", registry)
    assert result is None, "Toxic skills must not trigger a similarity suggestion"


# ---------------------------------------------------------------------------
# Empty registry edge case
# ---------------------------------------------------------------------------

def test_empty_registry_returns_none():
    """An empty skills dict must return None without raising."""
    result = check_semantic_similarity("any_skill", {"skills": {}})
    assert result is None
