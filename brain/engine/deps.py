"""Dependency tracking and environment rebuild utilities — US-22 & US-23."""
import subprocess
import sys
from pathlib import Path


REQUIREMENTS_PATH = Path(__file__).resolve().parent.parent.parent / "memory" / "requirements.txt"


def update_requirements(new_deps, requirements_path=None):
    """Append new deps to requirements.txt if not already present.

    Creates the file (and any parent dirs) if absent.
    Returns list of actually-added deps.
    """
    if requirements_path is None:
        requirements_path = REQUIREMENTS_PATH
    requirements_path = Path(requirements_path)
    requirements_path.parent.mkdir(parents=True, exist_ok=True)

    existing = set()
    if requirements_path.exists():
        existing = {
            line.strip()
            for line in requirements_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        }

    added = []
    with requirements_path.open("a", encoding="utf-8") as f:
        for dep in new_deps:
            dep = dep.strip()
            if dep and dep not in existing:
                f.write(dep + "\n")
                added.append(dep)
    return added


def rebuild_env(requirements_path=None, python_bin=None):
    """Run pip install -r requirements.txt in the Brain's virtualenv.

    Returns (success: bool, error: str).
    """
    if requirements_path is None:
        requirements_path = REQUIREMENTS_PATH
    if python_bin is None:
        python_bin = sys.executable

    result = subprocess.run(
        [str(python_bin), "-m", "pip", "install", "-r", str(requirements_path)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        return False, result.stderr
    return True, ""
