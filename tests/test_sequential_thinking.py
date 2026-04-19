"""Tests for memory.species.sequential_thinking."""
import pytest
from memory.species.sequential_thinking import sequential_thinking


def test_basic_problem_returns_ok():
    result = sequential_thinking("How do I set up a Python project?")
    assert result["status"] == "ok"
    assert len(result["steps"]) >= 1


def test_steps_end_with_synthesis():
    result = sequential_thinking("What is machine learning and how does it work?")
    last_step = result["steps"][-1]["action"]
    assert "synthes" in last_step.lower() or "final" in last_step.lower()


def test_context_becomes_first_step():
    result = sequential_thinking("Deploy the app.", context="App is a FastAPI service.")
    assert "FastAPI" in result["steps"][0]["action"]


def test_max_steps_respected():
    long_problem = " And also ".join([f"Do step {i}" for i in range(20)])
    result = sequential_thinking(long_problem, max_steps=5)
    assert len(result["steps"]) <= 5


def test_empty_problem_returns_error():
    result = sequential_thinking("")
    assert result["status"] == "error"


def test_hint_present():
    result = sequential_thinking("Build a REST API.")
    assert "hint" in result
    assert len(result["hint"]) > 0


def test_problem_echoed():
    problem = "Create a login form."
    result = sequential_thinking(problem)
    assert result["problem"] == problem


def test_steps_numbered_sequentially():
    result = sequential_thinking("Research, then design, then implement a feature.")
    for i, step in enumerate(result["steps"], start=1):
        assert step["step"] == i
