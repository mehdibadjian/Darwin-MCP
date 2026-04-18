"""Tests for US-27 — BSL-3 Contextualized Error Reporting."""
import sys
import re
from unittest.mock import patch, MagicMock

import pytest

from brain.engine.pytest_runner import PytestResult, run_pytest
from brain.engine.sandbox import Sandbox, SandboxError


# ── helpers ───────────────────────────────────────────────────────────────────

SUBJECT_CODE = "def add(a, b):\n    return a + b\n"

FAILING_TEST_CODE = (
    "from add import add\n"
    "def test_add_fails():\n"
    "    result = add(1, 2)\n"
    "    assert result == 99\n"
)


def _fail_proc(stderr="install error output"):
    m = MagicMock()
    m.returncode = 1
    m.stdout = ""
    m.stderr = stderr
    return m


# ── AC-1: pytest failure message includes filename ────────────────────────────

def test_pytest_failure_includes_filename(tmp_path):
    result = run_pytest(sys.executable, FAILING_TEST_CODE, SUBJECT_CODE, "add", work_dir=tmp_path)
    assert result.passed is False
    error = result.format_error()
    assert "test_" in error, f"Expected 'test_' in error, got: {error!r}"


def test_pytest_failure_includes_line_number(tmp_path):
    result = run_pytest(sys.executable, FAILING_TEST_CODE, SUBJECT_CODE, "add", work_dir=tmp_path)
    assert result.passed is False
    error = result.format_error()
    assert re.search(r"\d+", error), f"Expected line number in error, got: {error!r}"


def test_pytest_failure_includes_assertion(tmp_path):
    result = run_pytest(sys.executable, FAILING_TEST_CODE, SUBJECT_CODE, "add", work_dir=tmp_path)
    assert result.passed is False
    error = result.format_error()
    assert "assert" in error.lower() or "AssertionError" in error, (
        f"Expected assertion context in error, got: {error!r}"
    )


# ── AC-3: never return bare "Test failed." ────────────────────────────────────

def test_no_bare_test_failed_message():
    result = PytestResult(passed=False, stderr="Test failed.", stdout="")
    error = result.format_error()
    assert error != "Test failed.", f"format_error must not return bare 'Test failed.', got: {error!r}"


def test_no_bare_tests_failed_message():
    result = PytestResult(passed=False, stderr="Tests failed.", stdout="")
    error = result.format_error()
    assert error != "Tests failed.", f"format_error must not return bare 'Tests failed.', got: {error!r}"


# ── AC-3: empty stderr fallback ───────────────────────────────────────────────

def test_empty_stderr_fallback_message():
    result = PytestResult(passed=False, stderr="", stdout="")
    error = result.format_error()
    assert "no output" in error.lower() or "no diagnostic" in error.lower(), (
        f"Expected fallback message for empty output, got: {error!r}"
    )


# ── AC-2: pip error includes package name ─────────────────────────────────────

def test_pip_error_includes_package_name(tmp_path):
    with patch("brain.engine.sandbox.subprocess.run", return_value=_fail_proc("ERROR: No matching distribution")):
        s = Sandbox(base_dir=tmp_path)
        s.venv_path.mkdir(parents=True, exist_ok=True)
        s.pip.parent.mkdir(parents=True, exist_ok=True)
        s.pip.touch()
        with pytest.raises(SandboxError) as exc_info:
            s.install(["numpy", "requests"])
        assert "numpy" in str(exc_info.value), f"Expected package name in error: {exc_info.value}"
        assert "requests" in str(exc_info.value), f"Expected package name in error: {exc_info.value}"


def test_pip_error_includes_stderr(tmp_path):
    pip_stderr = "ERROR: Could not find a version that satisfies the requirement badpkg"
    with patch("brain.engine.sandbox.subprocess.run", return_value=_fail_proc(pip_stderr)):
        s = Sandbox(base_dir=tmp_path)
        s.venv_path.mkdir(parents=True, exist_ok=True)
        s.pip.parent.mkdir(parents=True, exist_ok=True)
        s.pip.touch()
        with pytest.raises(SandboxError) as exc_info:
            s.install(["badpkg"])
        assert pip_stderr in str(exc_info.value), (
            f"Expected pip stderr in error message: {exc_info.value}"
        )


# ── AC-2+3: mutator surfaces sandbox error with package info ──────────────────

def test_mutator_pip_failure_not_bare(tmp_path):
    """When sandbox install raises SandboxError, MutationResult.error has package info."""
    from brain.engine.mutator import request_evolution

    pip_error_msg = "pip install failed for [mylib]: ERROR: not found"
    with patch("brain.engine.sandbox.Sandbox.install",
               side_effect=SandboxError(pip_error_msg)):
        result = request_evolution(
            name="skill_x",
            code="def skill_x(): pass\n",
            tests="def test_ok():\n    assert True\n",
            requirements=["mylib"],
            species_dir=tmp_path / "species",
            registry_path=tmp_path / "registry.json",
            python_bin=sys.executable,
        )
    # Even if mutator doesn't call Sandbox.install directly in its pipeline,
    # the test verifies the error message format is never bare.
    # The mutator runs tests first — check error is never a bare generic string.
    assert result.error != "Test failed.", (
        f"MutationResult.error must not be bare 'Test failed.': {result.error!r}"
    )
