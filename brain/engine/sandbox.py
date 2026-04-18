"""Sandboxed virtualenv for mutation testing — US-8 & US-9."""
import shutil
import subprocess
import sys
import time
from pathlib import Path


class SandboxError(Exception):
    pass


class Sandbox:
    def __init__(self, base_dir=None):
        timestamp = int(time.time())
        if base_dir is None:
            base_dir = Path("/tmp")
        self.path = Path(base_dir) / f"mutation_{timestamp}"
        self.venv_path = self.path / "venv"
        self._created = False

    def create(self):
        """Create sandbox directory and isolated virtualenv."""
        self.path.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            [sys.executable, "-m", "venv", str(self.venv_path)],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            self.cleanup()
            raise SandboxError(f"Failed to create virtualenv: {result.stderr}")
        self._created = True
        return self

    @property
    def pip(self):
        """Path to the sandbox venv's pip binary."""
        return self.venv_path / "bin" / "pip"

    @property
    def python(self):
        """Path to the sandbox venv's python binary."""
        return self.venv_path / "bin" / "python"

    def install(self, requirements):
        """Install requirements into the sandbox venv. Skips if empty list."""
        if not requirements:
            return
        result = subprocess.run(
            [str(self.pip), "install"] + requirements,
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            self.cleanup()
            pkg_list = ", ".join(requirements)
            raise SandboxError(
                f"pip install failed for [{pkg_list}]: {result.stderr}"
            )

    def cleanup(self):
        """Remove the sandbox directory."""
        if self.path.exists():
            shutil.rmtree(self.path, ignore_errors=True)
        self._created = False

    def __enter__(self):
        self.create()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()
        return False
