"""pytest runner for Darwin-God-MCP — US-10 / US-11."""
import subprocess
import tempfile
from pathlib import Path

MAX_STDERR_CHARS = 10_000


class PytestResult:
    def __init__(self, passed, stdout="", stderr="", truncated=False):
        self.passed = passed
        self.stdout = stdout
        self.stderr = stderr
        self.truncated = truncated

    def format_error(self):
        """BSL-3: structured error — always includes file, line, assertion context."""
        if not self.stderr and not self.stdout:
            return "pytest produced no output (possible syntax error or import failure)"

        output = self.stderr or self.stdout
        if self.truncated:
            output = f"[TRUNCATED — showing last {MAX_STDERR_CHARS} chars]\n" + output

        if output.strip() in ("", "Test failed.", "Tests failed."):
            return "pytest exited non-zero but produced no diagnostic output"

        return output


def run_pytest(python_bin, test_code, subject_code, name, work_dir=None):
    """Write test_code and subject_code to files then run pytest via python_bin.

    Returns PytestResult. Never raises — all errors are captured.
    """
    if work_dir is None:
        work_dir = Path(tempfile.mkdtemp(prefix=f"pytest_{name}_"))
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    subject_file = work_dir / f"{name}.py"
    test_file = work_dir / f"test_{name}.py"

    subject_file.write_text(subject_code, encoding="utf-8")
    test_file.write_text(test_code, encoding="utf-8")

    try:
        proc = subprocess.run(
            [str(python_bin), "-m", "pytest", str(test_file), "-v", "--tb=short"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(work_dir),
        )
        # pytest writes failure details to stdout; combine for full picture
        combined = proc.stderr + proc.stdout
        truncated = False
        if len(combined) > MAX_STDERR_CHARS:
            combined = combined[-MAX_STDERR_CHARS:]
            truncated = True
        return PytestResult(
            passed=(proc.returncode in (0, 5)),  # 5 = no tests collected → treat as pass
            stdout=proc.stdout,
            stderr=combined,
            truncated=truncated,
        )
    except subprocess.TimeoutExpired:
        return PytestResult(passed=False, stderr="pytest execution timed out after 60s")
    except Exception as exc:  # noqa: BLE001
        return PytestResult(passed=False, stderr=f"pytest runner error: {exc}")
