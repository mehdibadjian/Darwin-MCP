"""Tests for ENH-US9: System Vitals Metrics Collection."""
import os
import time

from brain.engine.vitals import collect


def test_collect_returns_dict():
    result = collect()
    assert isinstance(result, dict)


def test_collect_has_required_keys():
    result = collect()
    assert {"cpu_percent", "memory", "disk", "process", "collected_at"} <= result.keys()


def test_collect_cpu_percent_is_float():
    result = collect()
    assert isinstance(result["cpu_percent"], float)
    assert 0.0 <= result["cpu_percent"] <= 100.0


def test_collect_memory_fields():
    result = collect()
    mem = result["memory"]
    assert {"used", "total", "percent"} <= mem.keys()
    assert mem["total"] > 0
    assert 0.0 <= mem["percent"] <= 100.0


def test_collect_disk_is_list_with_entries():
    result = collect()
    disk = result["disk"]
    assert isinstance(disk, list)
    assert len(disk) >= 1
    for entry in disk:
        assert {"mountpoint", "used", "total", "percent"} <= entry.keys()


def test_collect_process_fields():
    result = collect()
    proc = result["process"]
    assert {"pid", "cpu_percent", "rss_mb", "open_files"} <= proc.keys()
    assert proc["pid"] == os.getpid()


def test_collect_has_timestamp():
    result = collect()
    assert isinstance(result["collected_at"], str)
    assert result["collected_at"].endswith("Z")


def test_collect_returns_within_100ms():
    t0 = time.time()
    collect()
    assert time.time() - t0 < 0.1
