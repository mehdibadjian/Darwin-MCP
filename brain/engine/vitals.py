"""System Vitals — Droplet health metrics collection (ENH-US9)."""
import os
import logging
from datetime import datetime
from typing import Any

import psutil

logger = logging.getLogger(__name__)


def collect() -> dict:
    """Collect system and process-level metrics.

    Returns a dict with keys:
      cpu_percent: float                          # system-wide CPU %
      memory: {used: int, total: int, percent: float}
      disk: list[{mountpoint: str, used: int, total: int, percent: float}]
      process: {pid: int, cpu_percent: float, rss_mb: float, open_files: int}
      collected_at: str                           # ISO8601 UTC timestamp

    Must return in < 100ms under normal conditions.
    """
    cpu = psutil.cpu_percent(interval=None)

    vm = psutil.virtual_memory()
    memory = {
        "used": vm.used,
        "total": vm.total,
        "percent": vm.percent,
    }

    disk = []
    for part in psutil.disk_partitions():
        try:
            usage = psutil.disk_usage(part.mountpoint)
            disk.append({
                "mountpoint": part.mountpoint,
                "used": usage.used,
                "total": usage.total,
                "percent": usage.percent,
            })
        except PermissionError:
            pass

    proc = psutil.Process(os.getpid())
    try:
        open_files = len(proc.open_files())
    except psutil.AccessDenied:
        open_files = -1

    process = {
        "pid": proc.pid,
        "cpu_percent": proc.cpu_percent(interval=None),
        "rss_mb": proc.memory_info().rss / (1024 * 1024),
        "open_files": open_files,
    }

    return {
        "cpu_percent": float(cpu),
        "memory": memory,
        "disk": disk,
        "process": process,
        "collected_at": datetime.utcnow().isoformat() + "Z",
    }
