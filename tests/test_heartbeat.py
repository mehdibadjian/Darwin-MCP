"""Tests for brain/engine/heartbeat.py — Autonomous Heartbeat."""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from brain.engine.heartbeat import (
    SAFE_CPU_EVOLVE,
    SAFE_CPU_MEDIUM,
    _TASK_CPU_CEILING,
    _cpu_is_safe_for,
    _scan_log_for_anomalies,
    _enqueue_anomaly_reports,
    beat,
)


# ── CPU guard ─────────────────────────────────────────────────────────────────

def test_task_cpu_ceilings_are_tiered():
    """evolve ceiling must be strictest; report must always be 100."""
    assert _TASK_CPU_CEILING["evolve"] <= _TASK_CPU_CEILING["prune"]
    assert _TASK_CPU_CEILING["evolve"] <= _TASK_CPU_CEILING["optimize"]
    assert _TASK_CPU_CEILING["report"] == 100.0


def test_cpu_is_safe_report_always_true():
    """report tasks must never be blocked by the CPU guard."""
    safe, worst = _cpu_is_safe_for("report")
    assert safe is True
    assert worst == 0.0


def test_cpu_is_safe_passes_when_low(monkeypatch):
    monkeypatch.setattr("brain.engine.heartbeat.CPU_SAMPLE_COUNT", 2)
    monkeypatch.setattr("brain.engine.heartbeat.CPU_SAMPLE_INTERVAL", 0.0)
    with patch("psutil.cpu_percent", return_value=10.0):
        safe, worst = _cpu_is_safe_for("evolve")
    assert safe is True
    assert worst == 10.0


def test_cpu_is_safe_blocks_when_high(monkeypatch):
    monkeypatch.setattr("brain.engine.heartbeat.CPU_SAMPLE_COUNT", 2)
    monkeypatch.setattr("brain.engine.heartbeat.CPU_SAMPLE_INTERVAL", 0.0)
    high = SAFE_CPU_EVOLVE + 20.0
    with patch("psutil.cpu_percent", return_value=high):
        safe, worst = _cpu_is_safe_for("evolve")
    assert safe is False
    assert worst >= high


def test_cpu_is_safe_medium_passes_below_medium_ceiling(monkeypatch):
    monkeypatch.setattr("brain.engine.heartbeat.CPU_SAMPLE_COUNT", 1)
    monkeypatch.setattr("brain.engine.heartbeat.CPU_SAMPLE_INTERVAL", 0.0)
    cpu_val = SAFE_CPU_MEDIUM - 5.0
    with patch("psutil.cpu_percent", return_value=cpu_val):
        safe, _ = _cpu_is_safe_for("prune")
    assert safe is True


def test_cpu_is_safe_fast_fails_on_first_bad_sample(monkeypatch):
    """Guard should abort early on the first bad sample, not collect all samples."""
    monkeypatch.setattr("brain.engine.heartbeat.CPU_SAMPLE_COUNT", 3)
    monkeypatch.setattr("brain.engine.heartbeat.CPU_SAMPLE_INTERVAL", 0.0)
    call_count = {"n": 0}

    def fake_cpu(interval=None):
        call_count["n"] += 1
        return SAFE_CPU_EVOLVE + 50.0  # always too high

    with patch("psutil.cpu_percent", side_effect=fake_cpu):
        safe, _ = _cpu_is_safe_for("evolve")
    assert safe is False
    assert call_count["n"] == 1   # bailed after first sample


# ── Log anomaly scanner ───────────────────────────────────────────────────────

def test_scan_log_returns_empty_when_no_file(tmp_path):
    result = _scan_log_for_anomalies(tmp_path / "nonexistent.log")
    assert result == []


def test_scan_log_detects_error(tmp_path):
    log = tmp_path / "evolution.log"
    log.write_text("2026-01-01 INFO normal line\n2026-01-01 ERROR something broke\n")
    found = _scan_log_for_anomalies(log)
    assert len(found) == 1
    assert "ERROR" in found[0]["line"] or "error" in found[0]["pattern"]


def test_scan_log_detects_circuit_breaker(tmp_path):
    log = tmp_path / "evolution.log"
    log.write_text("Circuit breaker triggered for skill foo\n")
    found = _scan_log_for_anomalies(log)
    assert any("circuit" in a["pattern"].lower() for a in found)


def test_scan_log_deduplicates_repeated_lines(tmp_path):
    log = tmp_path / "evolution.log"
    log.write_text("ERROR same line\n" * 5)
    found = _scan_log_for_anomalies(log)
    assert len(found) == 1


def test_scan_log_assigns_critical_priority_1(tmp_path):
    log = tmp_path / "evolution.log"
    log.write_text("CRITICAL meltdown detected\n")
    found = _scan_log_for_anomalies(log)
    assert found[0]["priority"] == 1


# ── Anomaly enqueueing ────────────────────────────────────────────────────────

def test_enqueue_anomaly_reports_deduplicates(tmp_path):
    bp = tmp_path / "dna" / "backlog.json"
    bp.parent.mkdir(parents=True)
    anomalies = [{"line": "ERROR foo", "pattern": r"\bERROR\b", "priority": 2}]
    n1 = _enqueue_anomaly_reports(anomalies, backlog_path=bp)
    n2 = _enqueue_anomaly_reports(anomalies, backlog_path=bp)   # duplicate
    assert n1 == 1
    assert n2 == 0   # already in backlog


# ── beat() integration ────────────────────────────────────────────────────────

def test_beat_returns_report_structure(tmp_path, monkeypatch):
    """beat() must complete without error and return the required keys."""
    # Redirect all file paths to tmp_path
    monkeypatch.setattr("brain.engine.heartbeat._MEMORY_DIR", tmp_path)
    monkeypatch.setattr("brain.engine.heartbeat._STATUS_PATH", tmp_path / "heartbeat_status.json")
    monkeypatch.setattr("brain.engine.heartbeat._LOG_PATH", tmp_path / "evolution.log")
    monkeypatch.setattr("brain.engine.heartbeat._PRUNE_STATE_PATH", tmp_path / "dna" / "last_prune_date.txt")

    # Stub psutil so tests don't need the real package
    mock_psutil = MagicMock()
    mock_psutil.cpu_percent.return_value = 5.0
    mock_psutil.virtual_memory.return_value = MagicMock(percent=30.0)
    monkeypatch.setattr("brain.engine.heartbeat.psutil", mock_psutil, raising=False)
    try:
        import psutil as _psutil
        monkeypatch.setattr(_psutil, "cpu_percent", lambda interval=None: 5.0)
    except ImportError:
        pass

    bp = tmp_path / "dna" / "backlog.json"
    report = beat(backlog_path=bp)

    assert "beat_number" in report
    assert "timestamp" in report
    assert "vitals" in report
    assert "anomalies_found" in report
    assert "items_dispatched" in report
    assert "errors" in report


def test_beat_writes_status_file(tmp_path, monkeypatch):
    status_path = tmp_path / "heartbeat_status.json"
    monkeypatch.setattr("brain.engine.heartbeat._STATUS_PATH", status_path)
    monkeypatch.setattr("brain.engine.heartbeat._LOG_PATH", tmp_path / "evolution.log")
    monkeypatch.setattr("brain.engine.heartbeat._PRUNE_STATE_PATH", tmp_path / "dna" / "last_prune_date.txt")

    mock_psutil = MagicMock()
    mock_psutil.cpu_percent.return_value = 5.0
    mock_psutil.virtual_memory.return_value = MagicMock(percent=30.0)
    monkeypatch.setattr("brain.engine.heartbeat.psutil", mock_psutil, raising=False)

    bp = tmp_path / "dna" / "backlog.json"
    beat(backlog_path=bp)

    assert status_path.exists()
    data = json.loads(status_path.read_text())
    assert data["beats"] == 1
    assert data["last_beat_at"] is not None
