"""Tests for brain/engine/guard.py — US-24 Circuit Breaker Recursion Depth."""
import logging
import os
import unittest
from unittest.mock import MagicMock, patch

import pytest


class TestCheckRecursionDepth:
    def test_depth_within_limit_proceeds(self):
        from brain.engine.guard import check_recursion_depth
        assert check_recursion_depth(1, "my_skill") is True

    def test_depth_exactly_3_proceeds(self):
        from brain.engine.guard import check_recursion_depth
        assert check_recursion_depth(3, "my_skill") is True

    def test_depth_4_raises_recursion_limit_error(self):
        from brain.engine.guard import check_recursion_depth, RecursionLimitError
        with patch("brain.engine.guard.open_github_issue", return_value=(False, "")):
            with pytest.raises(RecursionLimitError):
                check_recursion_depth(4, "bad_skill")

    def test_recursion_error_includes_depth(self):
        from brain.engine.guard import check_recursion_depth, RecursionLimitError
        with patch("brain.engine.guard.open_github_issue", return_value=(False, "")):
            with pytest.raises(RecursionLimitError) as exc_info:
                check_recursion_depth(4, "bad_skill")
        assert exc_info.value.depth == 4
        assert "4" in str(exc_info.value)

    def test_recursion_error_includes_skill_name(self):
        from brain.engine.guard import check_recursion_depth, RecursionLimitError
        with patch("brain.engine.guard.open_github_issue", return_value=(False, "")):
            with pytest.raises(RecursionLimitError) as exc_info:
                check_recursion_depth(4, "doom_skill")
        assert exc_info.value.skill_name == "doom_skill"
        assert "doom_skill" in str(exc_info.value)

    def test_github_issue_opened_at_limit(self):
        from brain.engine.guard import check_recursion_depth, RecursionLimitError
        with patch("brain.engine.guard.open_github_issue", return_value=(True, "http://example.com/1")) as mock_issue:
            with pytest.raises(RecursionLimitError):
                check_recursion_depth(4, "trigger_skill")
        mock_issue.assert_called_once_with("trigger_skill", 4, github_token=None, repo=None)

    def test_github_issue_skipped_without_token(self, caplog):
        import urllib.request
        from brain.engine.guard import open_github_issue
        env = {k: v for k, v in os.environ.items() if k not in ("GITHUB_TOKEN", "GITHUB_REPO")}
        with patch.dict(os.environ, env, clear=True):
            with patch("urllib.request.urlopen") as mock_urlopen:
                with caplog.at_level(logging.WARNING, logger="brain.engine.guard"):
                    success, url = open_github_issue("some_skill", 4)
        mock_urlopen.assert_not_called()
        assert success is False
        assert url == ""


class TestMutatorCircuitBreaker:
    def test_mutator_depth_0_succeeds(self, tmp_path):
        from brain.engine.mutator import request_evolution
        code = "def hello(): return 'hi'"
        tests = "from hello import hello\ndef test_hello():\n    assert hello() == 'hi'"
        result = request_evolution(
            name="hello",
            code=code,
            tests=tests,
            requirements=[],
            species_dir=tmp_path / "species",
            registry_path=str(tmp_path / "registry.json"),
            recursion_depth=0,
        )
        assert result.success is True

    def test_mutator_depth_4_returns_circuit_breaker_error(self, tmp_path):
        from brain.engine.mutator import request_evolution
        with patch("brain.engine.guard.open_github_issue", return_value=(False, "")):
            result = request_evolution(
                name="runaway_skill",
                code="def runaway(): pass",
                tests="def test_r(): pass",
                requirements=[],
                species_dir=tmp_path / "species",
                registry_path=str(tmp_path / "registry.json"),
                recursion_depth=4,
            )
        assert result.success is False
        assert "Circuit breaker" in result.error
        assert "runaway_skill" in result.error
