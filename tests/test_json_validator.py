"""Tests for brain.middleware.json_validator."""
import json
import pytest
from brain.middleware.json_validator import validate_json_body, JSONValidatorMiddleware


def test_valid_json_passes():
    body = json.dumps({"name": "test", "code": "pass", "tests": "pass"}).encode()
    valid, error = validate_json_body(body, "/evolve")
    assert valid is True
    assert error is None


def test_invalid_json_returns_error():
    body = b'{"name": "test", "code": broken}'
    valid, error = validate_json_body(body, "/evolve")
    assert valid is False
    assert error is not None
    assert "retry_hint" in error
    assert "/evolve" in error["retry_hint"]


def test_empty_body_is_valid():
    valid, error = validate_json_body(b"", "/evolve")
    assert valid is True
    assert error is None


def test_retry_hint_contains_schema_for_evolve():
    body = b"{bad json"
    _, error = validate_json_body(body, "/evolve")
    assert "name" in error["retry_hint"]
    assert "code" in error["retry_hint"]
    assert "tests" in error["retry_hint"]


def test_retry_hint_contains_schema_for_search():
    body = b"{bad json"
    _, error = validate_json_body(body, "/search")
    assert "query" in error["retry_hint"]


def test_unknown_path_still_returns_error():
    body = b"{bad"
    valid, error = validate_json_body(body, "/unknown")
    assert valid is False
    assert error is not None


def test_schema_keys_present_in_middleware():
    assert "/evolve" in JSONValidatorMiddleware._SCHEMAS
    assert "/search" in JSONValidatorMiddleware._SCHEMAS
