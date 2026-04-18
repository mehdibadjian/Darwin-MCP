import configparser
import pathlib

SERVICE_FILE = pathlib.Path(__file__).parent.parent / "darwin.service"


def _parse_unit():
    content = SERVICE_FILE.read_text()
    # configparser requires a DEFAULT section; prepend a dummy one
    cfg = configparser.RawConfigParser(strict=False)
    cfg.read_string("[DEFAULT]\n" + content)
    return cfg


def test_service_file_exists():
    assert SERVICE_FILE.exists(), "darwin.service not found at repo root"


def test_working_directory():
    cfg = _parse_unit()
    assert cfg.get("Service", "WorkingDirectory") == "/opt/mcp-evolution-core"


def test_execstart_uses_venv_python():
    cfg = _parse_unit()
    exec_start = cfg.get("Service", "ExecStart")
    assert ".venv/bin/python" in exec_start, f"ExecStart should use venv python, got: {exec_start}"
    assert "/usr/bin/python" not in exec_start


def test_restart_on_failure():
    cfg = _parse_unit()
    assert cfg.get("Service", "Restart") == "on-failure"


def test_restart_sec():
    cfg = _parse_unit()
    assert cfg.get("Service", "RestartSec") == "5"


def test_start_limit_burst():
    cfg = _parse_unit()
    assert cfg.get("Service", "StartLimitBurst") == "5"


def test_start_limit_interval():
    cfg = _parse_unit()
    assert cfg.get("Service", "StartLimitIntervalSec") == "60"


def test_wanted_by_multi_user():
    cfg = _parse_unit()
    assert cfg.get("Install", "WantedBy") == "multi-user.target"
