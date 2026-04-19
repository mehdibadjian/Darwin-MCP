"""Tests for memory/species/generate_vitals_dashboard.py — TDD: write before species exists."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "memory" / "species"))
from generate_vitals_dashboard import generate_vitals_dashboard


class TestDryRun:
    def test_dry_run_returns_ok_no_files_written(self, tmp_path):
        result = generate_vitals_dashboard(output_dir=str(tmp_path / "ui"), dry_run=True)
        assert result["status"] == "ok"
        assert result["dry_run"] is True
        assert not (tmp_path / "ui").exists()

    def test_dry_run_manifest_contains_all_panels(self, tmp_path):
        result = generate_vitals_dashboard(output_dir=str(tmp_path / "ui"), dry_run=True)
        files = result["files_created"]
        for expected in [
            "package.json", "tailwind.config.js",
            "app/api/dna/route.ts", "app/api/feed/route.ts", "app/api/evolve/route.ts",
            "components/LiveFeed.tsx", "components/DnaMap.tsx", "components/ManualOverride.tsx",
            "app/page.tsx", "app/globals.css", ".env.local",
        ]:
            assert expected in files, f"Missing expected file: {expected}"


class TestScaffold:
    def test_creates_root_directory(self, tmp_path):
        result = generate_vitals_dashboard(output_dir=str(tmp_path / "vitals_ui"))
        assert result["status"] == "ok"
        assert Path(result["root"]).is_dir()

    def test_tailwind_config_has_sovereign_colors(self, tmp_path):
        root = tmp_path / "ui"
        generate_vitals_dashboard(output_dir=str(root))
        content = (root / "tailwind.config.js").read_text()
        assert "#00ff41" in content
        assert "#0a0a0a" in content

    def test_api_dna_route_has_brain_root(self, tmp_path):
        root = tmp_path / "ui"
        generate_vitals_dashboard(output_dir=str(root), brain_root="/custom/brain")
        content = (root / "app" / "api" / "dna" / "route.ts").read_text()
        assert "/custom/brain" in content

    def test_env_local_has_brain_port(self, tmp_path):
        root = tmp_path / "ui"
        generate_vitals_dashboard(output_dir=str(root), brain_port=9000)
        content = (root / ".env.local").read_text()
        assert "9000" in content

    def test_existing_directory_returns_error(self, tmp_path):
        root = tmp_path / "ui"
        root.mkdir()
        result = generate_vitals_dashboard(output_dir=str(root))
        assert result["status"] == "error"
        assert "already exists" in result["error"]

    def test_package_json_includes_tailwind(self, tmp_path):
        root = tmp_path / "ui"
        generate_vitals_dashboard(output_dir=str(root))
        pkg = json.loads((root / "package.json").read_text())
        assert "tailwindcss" in pkg["devDependencies"]
        assert "next" in pkg["dependencies"]

    def test_sovereign_theme_in_globals_css(self, tmp_path):
        root = tmp_path / "ui"
        generate_vitals_dashboard(output_dir=str(root))
        css = (root / "app" / "globals.css").read_text()
        assert "#00ff41" in css
        assert "JetBrains Mono" in css

    def test_returns_sorted_files_created(self, tmp_path):
        root = tmp_path / "ui"
        result = generate_vitals_dashboard(output_dir=str(root))
        assert result["files_created"] == sorted(result["files_created"])
