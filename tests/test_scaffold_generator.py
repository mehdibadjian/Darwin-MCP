"""Tests for memory/species/scaffold_generator.py — scaffold_generator skill."""
import shutil
import tempfile
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "memory" / "species"))
from scaffold_generator import scaffold_generator


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_output(tmp_path):
    """Yield a clean temp directory; teardown removes any subdirs created."""
    yield tmp_path


# ---------------------------------------------------------------------------
# FastAPI scaffold
# ---------------------------------------------------------------------------

class TestFastAPI:
    def test_creates_root_directory(self, tmp_output):
        result = scaffold_generator("FastAPI", "My App", output_dir=str(tmp_output / "my-app"))
        assert result["status"] == "ok"
        assert Path(result["root"]).is_dir()

    def test_required_files_exist(self, tmp_output):
        root = tmp_output / "fastapi-proj"
        scaffold_generator("FastAPI", "FastAPI Proj", output_dir=str(root))
        assert (root / "main.py").exists()
        assert (root / "requirements.txt").exists()
        assert (root / "routers" / "__init__.py").exists()
        assert (root / "models" / "__init__.py").exists()
        assert (root / "schemas" / "__init__.py").exists()
        assert (root / "tests" / "test_main.py").exists()

    def test_main_py_contains_fastapi(self, tmp_output):
        root = tmp_output / "fa"
        scaffold_generator("fastapi", "FA", output_dir=str(root))
        content = (root / "main.py").read_text()
        assert "FastAPI" in content

    def test_returns_files_created_list(self, tmp_output):
        result = scaffold_generator("FastAPI", "X", output_dir=str(tmp_output / "x"))
        assert isinstance(result["files_created"], list)
        assert len(result["files_created"]) > 0

    def test_case_insensitive(self, tmp_output):
        result = scaffold_generator("FASTAPI", "Y", output_dir=str(tmp_output / "y"))
        assert result["status"] == "ok"
        assert result["project_type"] == "fastapi"


# ---------------------------------------------------------------------------
# React scaffold
# ---------------------------------------------------------------------------

class TestReact:
    def test_creates_src_directory(self, tmp_output):
        root = tmp_output / "react-app"
        scaffold_generator("React", "React App", output_dir=str(root))
        assert (root / "src").is_dir()

    def test_required_files_exist(self, tmp_output):
        root = tmp_output / "ra"
        scaffold_generator("React", "RA", output_dir=str(root))
        assert (root / "package.json").exists()
        assert (root / "src" / "App.tsx").exists()
        assert (root / "src" / "index.tsx").exists()
        assert (root / "public" / "index.html").exists()

    def test_package_json_contains_name_slug(self, tmp_output):
        root = tmp_output / "my-react"
        scaffold_generator("React", "My React App", output_dir=str(root))
        content = (root / "package.json").read_text()
        assert "my-react-app" in content


# ---------------------------------------------------------------------------
# Tailwind scaffold
# ---------------------------------------------------------------------------

class TestTailwind:
    def test_tailwind_config_exists(self, tmp_output):
        root = tmp_output / "tw"
        scaffold_generator("Tailwind", "TW", output_dir=str(root))
        assert (root / "tailwind.config.js").exists()
        assert (root / "postcss.config.js").exists()

    def test_index_css_has_tailwind_directives(self, tmp_output):
        root = tmp_output / "tw2"
        scaffold_generator("tailwindcss", "TW2", output_dir=str(root))
        content = (root / "src" / "index.css").read_text()
        assert "@tailwind base" in content
        assert "@tailwind components" in content
        assert "@tailwind utilities" in content


# ---------------------------------------------------------------------------
# NextJS scaffold
# ---------------------------------------------------------------------------

class TestNextJS:
    def test_creates_app_directory(self, tmp_output):
        root = tmp_output / "next-app"
        scaffold_generator("NextJS", "Next App", output_dir=str(root))
        assert (root / "app").is_dir()

    def test_required_files_exist(self, tmp_output):
        root = tmp_output / "nj"
        scaffold_generator("nextjs", "NJ", output_dir=str(root))
        assert (root / "package.json").exists()
        assert (root / "next.config.js").exists()
        assert (root / "tsconfig.json").exists()
        assert (root / "app" / "page.tsx").exists()
        assert (root / "app" / "layout.tsx").exists()


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestDryRun:
    def test_dry_run_returns_ok_no_files_written(self, tmp_output):
        root = tmp_output / "ghost"
        result = scaffold_generator("FastAPI", "Ghost", output_dir=str(root), dry_run=True)
        assert result["status"] == "ok"
        assert result["dry_run"] is True
        assert not root.exists(), "dry_run must not create any directories"

    def test_dry_run_manifest_matches_real_scaffold(self, tmp_output):
        root_dry = tmp_output / "dry"
        root_real = tmp_output / "real"
        dry = scaffold_generator("NextJS", "Compare", output_dir=str(root_dry), dry_run=True)
        real = scaffold_generator("NextJS", "Compare", output_dir=str(root_real))
        assert dry["files_created"] == real["files_created"]

    def test_dry_run_message_contains_dry_run_label(self, tmp_output):
        result = scaffold_generator("React", "R", output_dir=str(tmp_output / "r"), dry_run=True)
        assert "dry_run" in result["message"]

    def test_dry_run_does_not_block_subsequent_real_scaffold(self, tmp_output):
        root = tmp_output / "reuse"
        scaffold_generator("FastAPI", "Reuse", output_dir=str(root), dry_run=True)
        result = scaffold_generator("FastAPI", "Reuse", output_dir=str(root))
        assert result["status"] == "ok"
        assert root.exists()

    def test_unknown_project_type_returns_error(self, tmp_output):
        result = scaffold_generator("Django", "X", output_dir=str(tmp_output / "x"))
        assert result["status"] == "error"
        assert "supported" in result

    def test_existing_directory_returns_error(self, tmp_output):
        root = tmp_output / "existing"
        root.mkdir()
        result = scaffold_generator("FastAPI", "Existing", output_dir=str(root))
        assert result["status"] == "error"
        assert "already exists" in result["error"]

    def test_name_slug_used_as_default_dir(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = scaffold_generator("FastAPI", "Hello World")
        assert result["status"] == "ok"
        assert Path(result["root"]).name == "hello-world"
        shutil.rmtree(result["root"])
