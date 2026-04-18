"""Tests for US-10 (pytest execution) and US-11 (full stderr reporting)."""
import sys
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# ── helpers ──────────────────────────────────────────────────────────────────

PASSING_SUBJECT = "def add(a, b):\n    return a + b\n"
PASSING_TESTS = (
    "from add import add\n"
    "def test_add():\n"
    "    assert add(1, 2) == 3\n"
)
FAILING_TESTS = (
    "from add import add\n"
    "def test_add_fails():\n"
    "    assert add(1, 2) == 99\n"
)
SYNTAX_ERROR_TESTS = "def test_broken(\n"  # syntax error


def _make_proc(returncode=0, stdout="", stderr=""):
    """Return a mock CompletedProcess-like object."""
    m = MagicMock()
    m.returncode = returncode
    m.stdout = stdout
    m.stderr = stderr
    return m


# ── real subprocess tests (1-4, 7) ────────────────────────────────────────────

def test_passing_tests_return_passed_true(tmp_path):
    from brain.engine.pytest_runner import run_pytest
    result = run_pytest(sys.executable, PASSING_TESTS, PASSING_SUBJECT, "add", work_dir=tmp_path)
    assert result.passed is True


def test_failing_tests_return_passed_false(tmp_path):
    from brain.engine.pytest_runner import run_pytest
    result = run_pytest(sys.executable, FAILING_TESTS, PASSING_SUBJECT, "add", work_dir=tmp_path)
    assert result.passed is False


def test_syntax_error_in_test_file_handled(tmp_path):
    from brain.engine.pytest_runner import run_pytest
    # Must not raise; must return passed=False
    result = run_pytest(sys.executable, SYNTAX_ERROR_TESTS, PASSING_SUBJECT, "add", work_dir=tmp_path)
    assert result.passed is False
    assert result.stderr != "" or result.stdout != ""


def test_stderr_included_verbatim_on_failure(tmp_path):
    from brain.engine.pytest_runner import run_pytest
    result = run_pytest(sys.executable, FAILING_TESTS, PASSING_SUBJECT, "add", work_dir=tmp_path)
    assert result.passed is False
    assert "99" in result.stderr or "assert" in result.stderr.lower()


def test_bsl3_error_includes_file_and_line(tmp_path):
    """BSL-3: failure output must contain filename and line number."""
    from brain.engine.pytest_runner import run_pytest
    result = run_pytest(sys.executable, FAILING_TESTS, PASSING_SUBJECT, "add", work_dir=tmp_path)
    assert "test_add.py" in result.stderr
    # pytest --tb=short always includes a line number after the filename
    import re
    assert re.search(r"test_add\.py:\d+", result.stderr)


# ── mocked subprocess tests (5-6) ────────────────────────────────────────────

def test_stderr_truncated_at_10000_chars(tmp_path):
    from brain.engine.pytest_runner import run_pytest, MAX_STDERR_CHARS
    big_output = "x" * (MAX_STDERR_CHARS * 2)
    mock_proc = _make_proc(returncode=1, stdout=big_output, stderr="")
    with patch("subprocess.run", return_value=mock_proc):
        result = run_pytest(sys.executable, FAILING_TESTS, PASSING_SUBJECT, "add", work_dir=tmp_path)
    assert result.truncated is True
    assert len(result.stderr) == MAX_STDERR_CHARS


def test_truncation_indicated_in_format_error(tmp_path):
    from brain.engine.pytest_runner import run_pytest, MAX_STDERR_CHARS
    big_output = "y" * (MAX_STDERR_CHARS * 2)
    mock_proc = _make_proc(returncode=1, stdout=big_output, stderr="")
    with patch("subprocess.run", return_value=mock_proc):
        result = run_pytest(sys.executable, FAILING_TESTS, PASSING_SUBJECT, "add", work_dir=tmp_path)
    assert "[TRUNCATED" in result.format_error()


# ── mutator integration tests (8-9) ──────────────────────────────────────────

def test_exit_code_zero_triggers_promotion_path(tmp_path):
    """Passing tests → species file written to disk."""
    from brain.engine.mutator import request_evolution
    species_dir = tmp_path / "species"
    reg = tmp_path / "registry.json"
    result = request_evolution(
        name="add",
        code=PASSING_SUBJECT,
        tests=PASSING_TESTS,
        requirements=[],
        species_dir=species_dir,
        registry_path=reg,
        python_bin=sys.executable,
    )
    assert result.success is True
    assert (species_dir / "add.py").exists()


def test_nonzero_exit_aborts_promotion(tmp_path):
    """Failing tests → no species file written."""
    from brain.engine.mutator import request_evolution
    species_dir = tmp_path / "species"
    reg = tmp_path / "registry.json"
    result = request_evolution(
        name="add",
        code=PASSING_SUBJECT,
        tests=FAILING_TESTS,
        requirements=[],
        species_dir=species_dir,
        registry_path=reg,
        python_bin=sys.executable,
    )
    assert result.success is False
    assert not (species_dir / "add.py").exists()
    assert result.error  # error message populated
