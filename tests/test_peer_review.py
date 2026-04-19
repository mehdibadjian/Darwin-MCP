"""Tests for brain/engine/peer_review.py — Multi-Model Validation (Council of Peers)."""
import pytest
from unittest.mock import patch, MagicMock, call

from brain.engine.peer_review import (
    PeerReviewRequest,
    PeerReviewResult,
    request_peer_review,
    FAILURE_COUNT_THRESHOLD,
    increment_failure_count,
    get_failure_count,
    reset_failure_count,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

def test_failure_count_threshold_is_3():
    """FAILURE_COUNT_THRESHOLD must equal 3 (trigger peer review after 3 failures)."""
    assert FAILURE_COUNT_THRESHOLD == 3


# ---------------------------------------------------------------------------
# Failure counter — in-memory tracking per skill
# ---------------------------------------------------------------------------

def test_initial_failure_count_is_zero():
    """A skill with no recorded failures has count 0."""
    assert get_failure_count("brand_new_skill") == 0


def test_increment_failure_count():
    """increment_failure_count() must increase count by 1."""
    reset_failure_count("test_skill_counter")
    increment_failure_count("test_skill_counter")
    assert get_failure_count("test_skill_counter") == 1


def test_reset_failure_count():
    """reset_failure_count() must set count back to 0."""
    increment_failure_count("reset_me")
    increment_failure_count("reset_me")
    reset_failure_count("reset_me")
    assert get_failure_count("reset_me") == 0


def test_failure_counts_are_per_skill():
    """Failure count for one skill must not affect another."""
    reset_failure_count("skill_a")
    reset_failure_count("skill_b")
    increment_failure_count("skill_a")
    increment_failure_count("skill_a")
    assert get_failure_count("skill_a") == 2
    assert get_failure_count("skill_b") == 0


# ---------------------------------------------------------------------------
# PeerReviewRequest / PeerReviewResult dataclasses
# ---------------------------------------------------------------------------

def test_peer_review_request_fields():
    """PeerReviewRequest must hold skill_name, code, tests, and error."""
    req = PeerReviewRequest(
        skill_name="my_tool",
        code="def my_tool(): pass",
        tests="def test_my_tool(): pass",
        error="AssertionError",
    )
    assert req.skill_name == "my_tool"
    assert req.code == "def my_tool(): pass"
    assert req.tests == "def test_my_tool(): pass"
    assert req.error == "AssertionError"


def test_peer_review_result_success_fields():
    """PeerReviewResult must hold reviewed, fixed_code, and explanation."""
    result = PeerReviewResult(
        reviewed=True,
        fixed_code="def my_tool(): return 42",
        explanation="Missing return statement",
    )
    assert result.reviewed is True
    assert result.fixed_code is not None
    assert result.explanation is not None


def test_peer_review_result_failure_fields():
    """PeerReviewResult can indicate review failed without fixed code."""
    result = PeerReviewResult(reviewed=False, fixed_code=None, explanation="Peer unavailable")
    assert result.reviewed is False
    assert result.fixed_code is None


# ---------------------------------------------------------------------------
# request_peer_review — calls secondary model after threshold
# ---------------------------------------------------------------------------

def test_peer_review_not_triggered_below_threshold(tmp_path):
    """Peer review must NOT be called when failure count < FAILURE_COUNT_THRESHOLD."""
    req = PeerReviewRequest(
        skill_name="under_threshold",
        code="def f(): pass",
        tests="def test_f(): pass",
        error="some error",
    )
    reset_failure_count("under_threshold")
    with patch("brain.engine.peer_review._call_secondary_model") as mock_call:
        result = request_peer_review(req, current_failure_count=2)
    mock_call.assert_not_called()
    assert result.reviewed is False


def test_peer_review_triggered_at_threshold(tmp_path):
    """Peer review MUST be called when failure count == FAILURE_COUNT_THRESHOLD."""
    req = PeerReviewRequest(
        skill_name="at_threshold",
        code="def f(): pass",
        tests="def test_f(): pass",
        error="TypeError: wrong return type",
    )
    with patch("brain.engine.peer_review._call_secondary_model") as mock_call:
        mock_call.return_value = PeerReviewResult(
            reviewed=True,
            fixed_code="def f(): return None",
            explanation="Added return value",
        )
        result = request_peer_review(req, current_failure_count=3)
    mock_call.assert_called_once()
    assert result.reviewed is True


def test_peer_review_triggered_above_threshold():
    """Peer review MUST also be called when failure count > FAILURE_COUNT_THRESHOLD."""
    req = PeerReviewRequest(
        skill_name="above_threshold",
        code="def f(): pass",
        tests="def test_f(): pass",
        error="NameError",
    )
    with patch("brain.engine.peer_review._call_secondary_model") as mock_call:
        mock_call.return_value = PeerReviewResult(
            reviewed=True, fixed_code="def f(): return 1", explanation="x"
        )
        result = request_peer_review(req, current_failure_count=10)
    mock_call.assert_called_once()
    assert result.reviewed is True


def test_peer_review_returns_not_reviewed_when_secondary_unavailable():
    """If secondary model raises, result.reviewed must be False (graceful degradation)."""
    req = PeerReviewRequest(
        skill_name="unavailable_model",
        code="def f(): pass",
        tests="def test_f(): pass",
        error="err",
    )
    with patch("brain.engine.peer_review._call_secondary_model", side_effect=Exception("model offline")):
        result = request_peer_review(req, current_failure_count=3)
    assert result.reviewed is False
    assert result.fixed_code is None


def test_peer_review_request_contains_error_context():
    """_call_secondary_model must receive the original error message in its prompt."""
    req = PeerReviewRequest(
        skill_name="broken_skill",
        code="def broken(): x = 1/0",
        tests="def test_broken(): broken()",
        error="ZeroDivisionError: division by zero",
    )
    captured = {}

    def fake_call(request: PeerReviewRequest) -> PeerReviewResult:
        captured["request"] = request
        return PeerReviewResult(reviewed=True, fixed_code="def broken(): return 0", explanation="Fix")

    with patch("brain.engine.peer_review._call_secondary_model", side_effect=fake_call):
        request_peer_review(req, current_failure_count=3)

    assert "ZeroDivisionError" in captured["request"].error


# ---------------------------------------------------------------------------
# Integration: mutator tracks failures and triggers peer review
# ---------------------------------------------------------------------------

def test_mutator_increments_failure_count_on_test_failure(tmp_path):
    """request_evolution must increment the failure counter when tests fail."""
    from brain.engine.mutator import request_evolution
    from brain.engine.peer_review import reset_failure_count, get_failure_count

    reset_failure_count("failing_skill")

    with patch("brain.engine.mutator._run_tests", return_value=(False, "AssertionError")):
        result = request_evolution(
            name="failing_skill",
            code="def failing_skill(): pass",
            tests="def test_x(): assert False",
            requirements=[],
            skip_similarity_check=True,
        )

    assert result.success is False
    assert get_failure_count("failing_skill") >= 1
