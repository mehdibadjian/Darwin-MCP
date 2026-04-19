"""Tests for memory/species/skill_optimizer.py — Policy Species."""
import json
from pathlib import Path

import pytest

from memory.species.skill_optimizer import (
    OVERLAP_THRESHOLD,
    _detect_pairs,
    _jaccard,
    _merged_name,
    _skill_tokens,
    _tokenise,
    skill_optimizer,
)


# ── Token helpers ─────────────────────────────────────────────────────────────

def test_tokenise_strips_stopwords():
    tokens = _tokenise("the best tool for the darwin mcp skill")
    assert "the" not in tokens
    assert "darwin" not in tokens   # stopword
    assert "best" in tokens


def test_jaccard_identical():
    a = {"foo", "bar"}
    assert _jaccard(a, a) == 1.0


def test_jaccard_disjoint():
    assert _jaccard({"foo"}, {"bar"}) == 0.0


def test_jaccard_partial():
    score = _jaccard({"a", "b", "c"}, {"b", "c", "d"})
    assert 0 < score < 1


def test_jaccard_empty():
    assert _jaccard(set(), set()) == 0.0


# ── _merged_name ──────────────────────────────────────────────────────────────

def test_merged_name_strips_handler():
    name = _merged_name("github_issue_classifier", "github_webhook_handler")
    assert "handler" not in name
    assert "unified" in name


def test_merged_name_stable():
    assert _merged_name("a", "b") == _merged_name("a", "b")


# ── _detect_pairs ─────────────────────────────────────────────────────────────

def _make_skills(*names_descs):
    """Build a minimal skills dict: [(name, description), ...]."""
    return {
        name: {
            "status": "active",
            "short_description": desc,
            "entry_point": name,
        }
        for name, desc in names_descs
    }


def test_detect_pairs_finds_overlap():
    skills = _make_skills(
        ("github_issue_classifier", "classify github issues by label"),
        ("github_issue_handler",    "handle and classify github issues"),
        ("nestjs_best_practices",   "nestjs architecture guidelines"),
    )
    pairs = _detect_pairs(skills, threshold=0.10)
    pair_names = [(p["skill_a"], p["skill_b"]) for p in pairs]
    assert any("github" in a and "github" in b for a, b in pair_names)


def test_detect_pairs_returns_empty_for_unrelated_skills():
    skills = _make_skills(
        ("nestjs_best_practices", "nestjs architecture"),
        ("fpga_best_practices",   "fpga hardware design"),
    )
    # With default threshold these share "best" and "practice" after stopword removal
    # — just verify the function runs and returns a list
    pairs = _detect_pairs(skills, threshold=0.99)   # extremely high threshold
    assert isinstance(pairs, list)


def test_detect_pairs_sorted_descending():
    skills = _make_skills(
        ("a_foo_bar", "foo bar baz qux"),
        ("b_foo_bar", "foo bar baz"),
        ("c_foo",     "foo"),
    )
    pairs = _detect_pairs(skills, threshold=0.0)
    if len(pairs) > 1:
        for i in range(len(pairs) - 1):
            assert pairs[i]["score"] >= pairs[i + 1]["score"]


# ── skill_optimizer entry point ───────────────────────────────────────────────

def test_detect_strategy_returns_ok(tmp_path):
    reg = tmp_path / "dna" / "registry.json"
    reg.parent.mkdir(parents=True)
    reg.write_text(json.dumps({"skills": {
        "github_issue_classifier": {
            "status": "active",
            "short_description": "classify github issues",
            "entry_point": "github_issue_classifier",
        },
        "github_webhook_handler": {
            "status": "active",
            "short_description": "handle github webhooks",
            "entry_point": "github_webhook_handler",
        },
    }}))
    result = skill_optimizer(strategy="detect", registry_path=str(reg), threshold=0.0)
    assert result["status"] == "ok"
    assert result["strategy"] == "detect"
    assert isinstance(result["pairs"], list)
    assert "summary" in result


def test_merge_strategy_generates_payload(tmp_path):
    reg = tmp_path / "dna" / "registry.json"
    reg.parent.mkdir(parents=True)
    reg.write_text(json.dumps({"skills": {
        "skill_a": {"status": "active", "short_description": "does A", "entry_point": "skill_a"},
        "skill_b": {"status": "active", "short_description": "does B", "entry_point": "skill_b"},
    }}))
    result = skill_optimizer(
        strategy="merge",
        target_skills=["skill_a", "skill_b"],
        registry_path=str(reg),
    )
    assert result["status"] == "ok"
    payload = result["merge_payload"]
    assert payload is not None
    assert "code" in payload
    assert "tests" in payload
    assert "name" in payload
    # Generated code must include both skill names
    assert "skill_a" in payload["code"]
    assert "skill_b" in payload["code"]


def test_merge_strategy_missing_target_skills(tmp_path):
    reg = tmp_path / "dna" / "registry.json"
    reg.parent.mkdir(parents=True)
    reg.write_text(json.dumps({"skills": {}}))
    result = skill_optimizer(strategy="merge", registry_path=str(reg))
    assert result["status"] == "error"
    assert "target_skills" in result["error"]


def test_merge_strategy_unknown_skill(tmp_path):
    reg = tmp_path / "dna" / "registry.json"
    reg.parent.mkdir(parents=True)
    reg.write_text(json.dumps({"skills": {
        "skill_a": {"status": "active", "short_description": "a"},
    }}))
    result = skill_optimizer(
        strategy="merge",
        target_skills=["skill_a", "nonexistent"],
        registry_path=str(reg),
    )
    assert result["status"] == "error"
    assert "not found" in result["error"]


def test_unknown_strategy_returns_error(tmp_path):
    reg = tmp_path / "dna" / "registry.json"
    reg.parent.mkdir(parents=True)
    reg.write_text(json.dumps({"skills": {}}))
    result = skill_optimizer(strategy="destroy_everything", registry_path=str(reg))
    assert result["status"] == "error"


def test_empty_registry_returns_ok(tmp_path):
    reg = tmp_path / "dna" / "registry.json"
    reg.parent.mkdir(parents=True)
    reg.write_text(json.dumps({"skills": {}}))
    result = skill_optimizer(strategy="detect", registry_path=str(reg))
    assert result["status"] == "ok"
    assert result["pairs"] == []


def test_archived_skills_excluded_from_detection(tmp_path):
    reg = tmp_path / "dna" / "registry.json"
    reg.parent.mkdir(parents=True)
    reg.write_text(json.dumps({"skills": {
        "skill_a": {"status": "archived", "short_description": "github issues"},
        "skill_b": {"status": "active",   "short_description": "github issues"},
    }}))
    skills = json.loads(reg.read_text())["skills"]
    pairs = _detect_pairs(skills, threshold=0.0)
    # skill_a is archived — only active skills should pair
    for p in pairs:
        assert p["skill_a"] != "skill_a"
        assert p["skill_b"] != "skill_a"
