# Intelligence Dashboard — `generate_vitals_dashboard` Implementation Plan

**Created**: 2026-04-19
**Last Updated**: 2026-04-19

## Overview

Evolve a new species `generate_vitals_dashboard` that, when invoked, produces a lightweight single-page Next.js 14 + Tailwind "Intelligence Dashboard" (`vitals_ui/`) — giving Darwin-MCP a visual face. The dashboard streams `progress.txt` as a live feed, renders a DNA Map of all registered species from `registry.json`, and provides a Manual Override form to trigger `request_evolution` without an IDE.

The species is authored, tested, and registered via the **Two-Stage Handshake** (`request_evolution` → invoke). It mirrors the file-generation pattern of the existing `scaffold_generator` species, but extends the Next.js template with a Sovereign-themed UI, live SSE feed route, DNA-reader API route, and a manual evolution POST proxy route.

---

## Current State Analysis

The organism has a working `scaffold_generator` species that produces bare Next.js, React, FastAPI, and Tailwind scaffolds. It does **not** include:
- Tailwind CSS in the NextJS template
- Domain-specific API routes
- SSE streaming from local files
- Any custom UI

### Key Code Locations:
- `memory/species/scaffold_generator.py:234-332` — `scaffold_generator()` entry point; `dry_run` supported; returns manifest dict
- `memory/species/scaffold_generator.py:157-220` — `_NEXTJS_FILES` template dict — base pattern to follow
- `memory/dna/registry.json` — single source of truth; 8 registered species today
- `brain/utils/registry.py:26-27` — `REGISTRY_PATH` relative to Brain root
- `brain/bridge/sse_server.py:219-263` — `/evolve` POST endpoint: fields `name`, `code`, `tests`, `requirements`
- `brain/bridge/sse_server.py:127-183` — `/sse` GET with Bearer Token auth + 30 s keepalive
- `brain/engine/vitals.py:15-23` — `get_evolution_log_tail()` — last N lines of evolution.log
- `progress.txt` — sprint metabolism record at repo root; plain text, appended per sprint
- `tests/test_scaffold_generator.py` — 17 tests; class-based; `sys.path.insert` pattern

### Current scaffold_generator NextJS template (the base we extend):
```python
# memory/species/scaffold_generator.py:157-220
_NEXTJS_FILES = {
    "package.json":    '{ "dependencies": { "next": "14.0.0" ... } }',
    "next.config.js":  'module.exports = { reactStrictMode: true };',
    "tsconfig.json":   '{ ... }',
    "app/layout.tsx":  'export default function RootLayout ...',
    "app/page.tsx":    'export default function Home() { return <main><h1>{name}</h1></main> }',
    "app/globals.css": '* { box-sizing: border-box; margin: 0; }',
    "components/.gitkeep": "",
    "lib/.gitkeep": "",
    "public/.gitkeep": "",
    "README.md": '...',
}
```

The base template lacks: Tailwind, API routes, SSE streaming, any domain data.

---

## Desired End State

A registered species `generate_vitals_dashboard` that:

1. **Produces `vitals_ui/`** — a complete, runnable Next.js 14 + Tailwind project
2. **Three Dashboard Panels**:
   - **Live Feed** (`/api/feed` SSE route) — tails `progress.txt`; streams new lines every 2 s; seeds with last 20 lines on connect
   - **DNA Map** (`/api/dna` GET route) — reads `registry.json`; returns all species with `success_rate`, `total_calls`, `evolved_at`, `status`, `version`
   - **Manual Override** (`/api/evolve` POST proxy) — proxies to Brain's `/evolve` endpoint
3. **Sovereign Theme** — dark bg `#0a0a0a`, green accent `#00ff41`, monospaced (`JetBrains Mono`)
4. **Species registered** in `registry.json` with `status: active`
5. All **9+ pytest tests pass** in the sandbox before promotion

Verify with: `cd vitals_ui && npm install && npm run build` exits 0, and `npm run dev` renders the three panels.

---

## What We're NOT Doing

- Not modifying `scaffold_generator.py` — `generate_vitals_dashboard` is its own self-contained species
- Not adding auth to the dashboard — local dev tool only
- Not deploying `vitals_ui` to the Droplet — runs locally via `npm run dev`
- Not using WebSockets — SSE is sufficient and consistent with the Brain's own transport
- Not extending the Brain's SSE server or existing `/sse` endpoint
- Not adding a `nextjs+tailwind` template to `scaffold_generator`
- Not making the dashboard production-hardened (no error boundaries, no auth)

---

## Implementation Approach

`generate_vitals_dashboard` embeds the full dashboard file tree as a Python dict `_DASHBOARD_FILES` — exactly the same pattern as `scaffold_generator`'s `_NEXTJS_FILES`. When invoked it:

1. Resolves `output_dir` (defaults to `<cwd>/vitals_ui`)
2. Guards against an existing directory
3. Resolves `brain_root` (defaults to parent³ of `__file__`, same as every Brain module)
4. Writes all files, substituting `{brain_root}` and `{brain_port}` placeholders
5. Returns a manifest dict identical in shape to `scaffold_generator`'s output

The Brain root path is baked into the generated API routes **at scaffold time** — the dashboard reads `registry.json` and `progress.txt` directly from the filesystem, requiring no HTTP call to the Brain for data reads. The Manual Override panel POSTs to the Brain's `/evolve` (URL from `.env.local`).

---

## Phase 1: TDD — Write Tests First

### Overview
Create the pytest test file _before_ the species exists. Tests will fail (ImportError), which is expected. Once the species is implemented they must all pass.

**File**: `tests/test_generate_vitals_dashboard.py` *(new)*

```python
"""Tests for memory/species/generate_vitals_dashboard.py"""
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
            assert expected in files, f"Missing: {expected}"


class TestScaffold:
    def test_creates_root_directory(self, tmp_path):
        result = generate_vitals_dashboard(output_dir=str(tmp_path / "vitals_ui"))
        assert result["status"] == "ok"
        assert Path(result["root"]).is_dir()

    def test_tailwind_config_has_sovereign_colors(self, tmp_path):
        root = tmp_path / "ui"
        generate_vitals_dashboard(output_dir=str(root))
        content = (root / "tailwind.config.js").read_text()
        assert "#00ff41" in content   # sovereign accent
        assert "#0a0a0a" in content   # sovereign bg

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
```

**Verify tests fail**: `pytest tests/test_generate_vitals_dashboard.py -v` → `ImportError`

---

## Phase 2: Species Implementation — `generate_vitals_dashboard.py`

### Overview
Write the species file at `memory/species/generate_vitals_dashboard.py`. Zero third-party Python dependencies — stdlib only.

**File**: `memory/species/generate_vitals_dashboard.py` *(new)*

### Full species structure:

```python
"""generate_vitals_dashboard — Intelligence Dashboard Evolution.

Scaffolds a Sovereign-themed Next.js 14 + Tailwind dashboard that
visualises progress.txt and registry.json via a local SSE stream.

Panels:
  Live Feed     — tails progress.txt via /api/feed (SSE)
  DNA Map       — reads registry.json via /api/dna (JSON REST)
  Manual Override — POSTs to Brain /evolve via /api/evolve (proxy)
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import Optional


_DASHBOARD_FILES: dict[str, str] = {
    "package.json": '''{ ... next 14.2.3, tailwindcss 3.4.3 ... }''',
    "tailwind.config.js": '''... sovereign color palette (#00ff41 accent, #0a0a0a bg) ...''',
    "postcss.config.js": "module.exports = { plugins: { tailwindcss: {}, autoprefixer: {} } };\n",
    "next.config.js": "module.exports = { reactStrictMode: true };\n",
    "tsconfig.json": "...",
    ".env.local": "NEXT_PUBLIC_BRAIN_URL=http://localhost:{brain_port}\n",
    "app/globals.css": "... @import JetBrains Mono, Tailwind directives, sovereign scrollbar ...",
    "app/layout.tsx": "... dark RootLayout ...",
    "app/page.tsx": "... three-panel grid: LiveFeed + ManualOverride | DnaMap ...",
    "app/api/dna/route.ts": "... reads {brain_root}/memory/dna/registry.json, computes success_rate ...",
    "app/api/feed/route.ts": "... SSE stream of {brain_root}/progress.txt, seeds last 20 lines ...",
    "app/api/evolve/route.ts": "... POST proxy → Brain /evolve with Bearer token ...",
    "components/LiveFeed.tsx": "... useEventSource /api/feed, auto-scroll, keeps last 200 lines ...",
    "components/DnaMap.tsx": "... fetch /api/dna every 15s, SuccessBar component, status badges ...",
    "components/ManualOverride.tsx": "... form with name/code/tests/requirements fields ...",
    "README.md": "... setup + run instructions ...",
}


def generate_vitals_dashboard(
    output_dir: Optional[str] = None,
    brain_root: Optional[str] = None,
    brain_port: int = 8000,
    dry_run: bool = False,
) -> dict:
    """Scaffold the Intelligence Dashboard Next.js project.

    Args:
        output_dir:  Target directory. Defaults to <cwd>/vitals_ui.
        brain_root:  Absolute path to mcp-evolution-core root.
                     Defaults to parent³ of __file__ (same resolution
                     used throughout the Brain codebase).
        brain_port:  Brain SSE server port. Written to .env.local.
        dry_run:     Return manifest without writing files.

    Returns:
        {"status", "dry_run", "name", "root", "files_created", "message"}
    """
    if brain_root is None:
        brain_root = str(Path(__file__).resolve().parent.parent.parent)

    root = Path(output_dir).expanduser().resolve() if output_dir else Path.cwd() / "vitals_ui"
    files_manifest = sorted(_DASHBOARD_FILES.keys())

    if dry_run:
        return {
            "status": "ok", "dry_run": True, "name": "vitals_ui",
            "root": str(root), "files_created": files_manifest,
            "message": f"🔬 dry_run: dashboard would create {len(files_manifest)} files at {root}",
        }

    if root.exists():
        return {"status": "error", "error": f"Output directory already exists: {root}", "root": str(root)}

    files_created: list[str] = []
    for rel_path, content in _DASHBOARD_FILES.items():
        abs_path = root / rel_path
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        filled = content.replace("{brain_root}", brain_root).replace("{brain_port}", str(brain_port))
        abs_path.write_text(filled, encoding="utf-8")
        files_created.append(rel_path)

    return {
        "status": "ok", "dry_run": False, "name": "vitals_ui",
        "root": str(root), "files_created": sorted(files_created),
        "message": f"✅ Intelligence Dashboard scaffolded → {root} ({len(files_created)} files)",
    }


def run(output_dir: Optional[str] = None, brain_root: Optional[str] = None) -> dict:
    return generate_vitals_dashboard(output_dir=output_dir, brain_root=brain_root)
```

> **Note**: The actual `_DASHBOARD_FILES` dict in the committed file contains the full verbatim content of every file — not pseudocode. The snippets above are abbreviated for plan readability. See the research notes for the complete file contents.

### Success Criteria — Phase 2:

#### Automated Verification:
- [ ] All 9 tests pass: `pytest tests/test_generate_vitals_dashboard.py -v`
- [ ] Full suite still passes: `pytest tests/ -v --ignore=tests/test_sandbox.py --ignore=tests/test_deps.py`

#### Manual Verification:
- [ ] `brain_root` placeholder correctly substituted in `app/api/dna/route.ts`
- [ ] `brain_port` placeholder correctly substituted in `.env.local`
- [ ] `tailwind.config.js` sovereign color palette present

---

## Phase 3: Two-Stage Handshake

### Stage 1 — Register via `request_evolution`

```python
# Via MCP tool call or direct Python:
from brain.engine.mutator import request_evolution
from pathlib import Path

brain_root = Path(__file__).resolve().parent  # repo root

result = request_evolution(
    name="generate_vitals_dashboard",
    code=Path("memory/species/generate_vitals_dashboard.py").read_text(),
    tests=Path("tests/test_generate_vitals_dashboard.py").read_text(),
    requirements=[],          # stdlib only
    git_commit=True,
    memory_dir=str(brain_root / "memory"),
)
# Expect: result.success == True, result.version == 1
```

Full pipeline steps triggered:
1. Input validation → 2. Semantic similarity check (no duplicate) → 3. Pytest in sandbox → 4. Species file promoted to `memory/species/` → 5. Atomic `registry.json` update → 6. `rebuild_env` (no-op, no new deps) → 7. Git commit + push → 8. `_emit_list_changed` to IDEs

Expected `registry.json` entry after Stage 1:
```json
"generate_vitals_dashboard": {
  "path": "<brain_root>/memory/species/generate_vitals_dashboard.py",
  "entry_point": "generate_vitals_dashboard",
  "runtime": "python3",
  "dependencies": [],
  "evolved_at": "<UTC timestamp>",
  "status": "active",
  "version": 1
}
```

### Stage 2 — Invoke to Produce `vitals_ui/`

```python
from memory.species.generate_vitals_dashboard import generate_vitals_dashboard
import os

result = generate_vitals_dashboard(
    output_dir=os.path.join(brain_root, "vitals_ui"),
    brain_root=brain_root,
    brain_port=8000,
)
# Expect: {"status": "ok", "files_created": [16 files], "root": ".../vitals_ui"}
```

### Success Criteria — Phase 3:

#### Automated Verification:
- [ ] `registry.json` contains `generate_vitals_dashboard` with `status: active`
- [ ] `vitals_ui/` directory exists with 16+ files
- [ ] `cd vitals_ui && npm install && npm run build` exits 0

#### Manual Verification:
- [ ] `npm run dev` starts on `http://localhost:3000`
- [ ] DNA Map panel shows all 9 species from `registry.json`
- [ ] Live Feed streams new lines when `progress.txt` is appended to
- [ ] Manual Override form submits and shows success/error response
- [ ] Sovereign dark theme renders: green `#00ff41` accents, `#0a0a0a` background, monospaced font

---

## Testing Strategy

### Unit Tests
- **File**: `tests/test_generate_vitals_dashboard.py`
- **Classes**: `TestDryRun` (2 tests) + `TestScaffold` (7 tests) = **9 total**
- Pattern mirrors `tests/test_scaffold_generator.py` exactly

### Integration Validation
```bash
# 1. Confirm dry_run works
python -c "
import sys; sys.path.insert(0, 'memory/species')
from generate_vitals_dashboard import generate_vitals_dashboard
import json
r = generate_vitals_dashboard(dry_run=True)
print(json.dumps(r, indent=2))
"

# 2. Full pytest suite (fast subset)
pytest tests/ -v --ignore=tests/test_sandbox.py --ignore=tests/test_deps.py

# 3. Build validation (after Stage 2)
cd vitals_ui && npm install && npm run build
```

---

## Performance Considerations

- Species file generation: CPU/disk-bound, completes in < 100 ms
- `/api/feed` SSE: polls `progress.txt` every 2 s — negligible I/O (file stat + partial read)
- `/api/dna` JSON: one `fs.readFileSync` per 15 s refresh — negligible
- Zero impact on the Brain SSE server or its existing `/sse` endpoint

## Migration Notes

- Add `vitals_ui/` to `.gitignore` — it's a generated artefact, not source-controlled
- `.env.local` is already excluded by Next.js's default `.gitignore`
- `MCP_BEARER_TOKEN` must be set in `.env.local` for Manual Override to authenticate to the Brain
- No schema changes to `registry.json` — new species entry follows existing schema

## References

- Scaffold pattern: `memory/species/scaffold_generator.py:157-332`
- `request_evolution` pipeline: `brain/engine/mutator.py:65-209`
- Brain `/evolve` endpoint: `brain/bridge/sse_server.py:219-263`
- Registry schema: `brain/utils/registry.py:30-34`
- `progress.txt`: repo root — plain text, sprint-appended
- Test pattern: `tests/test_scaffold_generator.py`
