# Intelligence Dashboard — Task Checklist

**Last Updated**: 2026-04-19
**Status**: Not Started

---

## Phase 1: Write Failing Tests (TDD — tests first)

- [ ] **Task 1.1**: Create `tests/test_generate_vitals_dashboard.py`
  - File: `tests/test_generate_vitals_dashboard.py`
  - Effort: S
  - Dependencies: None
  - Acceptance: File exists with `TestDryRun` (2 tests) and `TestScaffold` (7 tests); running pytest yields `ImportError` (species not yet written)

- [ ] **Task 1.2**: Verify tests fail for the right reason
  - Command: `pytest tests/test_generate_vitals_dashboard.py -v`
  - Effort: S
  - Dependencies: Task 1.1
  - Acceptance: Output shows `ImportError: cannot import name 'generate_vitals_dashboard'` — not a syntax error in the test file

### Phase 1 Verification
- [ ] Run: `pytest tests/test_generate_vitals_dashboard.py -v` → ImportError on 9 tests

---

## Phase 2: Implement the Species

- [ ] **Task 2.1**: Create `memory/species/generate_vitals_dashboard.py`
  - File: `memory/species/generate_vitals_dashboard.py`
  - Effort: L
  - Dependencies: Task 1.1
  - Acceptance: File exists; `_DASHBOARD_FILES` dict has all 16 file entries; entry point `generate_vitals_dashboard()` with `output_dir`, `brain_root`, `brain_port`, `dry_run` params; `run()` alias at bottom

- [ ] **Task 2.2**: Verify Sovereign theme in Tailwind config
  - File: `memory/species/generate_vitals_dashboard.py` → `tailwind.config.js` entry
  - Effort: S
  - Dependencies: Task 2.1
  - Acceptance: `tailwind.config.js` template contains `#00ff41` (accent), `#0a0a0a` (bg), `JetBrains Mono`

- [ ] **Task 2.3**: Verify API routes have correct placeholders
  - Files: `app/api/dna/route.ts`, `app/api/feed/route.ts`, `app/api/evolve/route.ts` entries in `_DASHBOARD_FILES`
  - Effort: S
  - Dependencies: Task 2.1
  - Acceptance: Each contains `{brain_root}` or `{brain_port}` literal that gets substituted at scaffold time

- [ ] **Task 2.4**: All 9 tests pass
  - Command: `pytest tests/test_generate_vitals_dashboard.py -v`
  - Effort: S
  - Dependencies: Tasks 2.1–2.3
  - Acceptance: `9 passed` with no warnings about missing files or assertions

- [ ] **Task 2.5**: Full test suite still passes (no regressions)
  - Command: `pytest tests/ -v --ignore=tests/test_sandbox.py --ignore=tests/test_deps.py`
  - Effort: S
  - Dependencies: Task 2.4
  - Acceptance: All previously passing tests still pass

### Phase 2 Verification
- [ ] Run: `pytest tests/test_generate_vitals_dashboard.py -v` → `9 passed`
- [ ] Run: `pytest tests/ --ignore=tests/test_sandbox.py --ignore=tests/test_deps.py` → full suite green
- [ ] Manual: `python -c "import sys; sys.path.insert(0,'memory/species'); from generate_vitals_dashboard import generate_vitals_dashboard; import json; print(json.dumps(generate_vitals_dashboard(dry_run=True), indent=2))"` → 16-file manifest

---

## Phase 3: Two-Stage Handshake

- [ ] **Task 3.1** (Stage 1): Register species via `request_evolution`
  - Method: Call `request_evolution` MCP tool or direct Python with `name="generate_vitals_dashboard"`, `code=<file contents>`, `tests=<test contents>`, `requirements=[]`, `git_commit=True`
  - Effort: S
  - Dependencies: Task 2.5
  - Acceptance: `result.success == True`; `registry.json` contains `generate_vitals_dashboard` entry with `status: active`, `version: 1`

- [ ] **Task 3.2**: Verify registry entry
  - Command: `python -c "from brain.utils.registry import read_registry; import json; r=read_registry(); print(json.dumps(r['skills'].get('generate_vitals_dashboard'), indent=2))"`
  - Effort: S
  - Dependencies: Task 3.1
  - Acceptance: Entry present with `status: active`, `version: 1`, correct `path`

- [ ] **Task 3.3** (Stage 2): Invoke species to produce `vitals_ui/`
  - Method: Call `generate_vitals_dashboard(output_dir="<brain_root>/vitals_ui", brain_root="<brain_root>", brain_port=8000)`
  - Effort: S
  - Dependencies: Task 3.1
  - Acceptance: `vitals_ui/` directory exists with 16 files; `result["status"] == "ok"`

- [ ] **Task 3.4**: Add `vitals_ui/` to `.gitignore`
  - File: `.gitignore`
  - Effort: S
  - Dependencies: Task 3.3
  - Acceptance: `vitals_ui/` line present in `.gitignore`

- [ ] **Task 3.5**: Build validation
  - Command: `cd vitals_ui && npm install && npm run build`
  - Effort: S
  - Dependencies: Task 3.3
  - Acceptance: `npm run build` exits 0 with no TypeScript or Tailwind errors

### Phase 3 Verification
- [ ] Run: `cd vitals_ui && npm run dev` → server starts on `http://localhost:3000`
- [ ] Manual: DNA Map panel shows all species from `registry.json`
- [ ] Manual: Live Feed panel streams lines from `progress.txt`
- [ ] Manual: Manual Override form submits and shows `✅` success message
- [ ] Manual: Dark Sovereign theme visible — green `#00ff41` accents, `#0a0a0a` background, monospaced font

---

## Final Verification

### Automated Checks:
- [ ] `pytest tests/test_generate_vitals_dashboard.py -v` → 9 passed
- [ ] `pytest tests/ --ignore=tests/test_sandbox.py --ignore=tests/test_deps.py` → full suite green
- [ ] `registry.json` has `generate_vitals_dashboard` entry with `status: active`
- [ ] `cd vitals_ui && npm install && npm run build` → exits 0

### Manual Checks:
- [ ] `npm run dev` renders the three-panel dashboard at `http://localhost:3000`
- [ ] All three panels display live data (DNA Map, Live Feed, Manual Override)
- [ ] Sovereign dark theme renders correctly

## Notes Section

- `brain_root` defaults to `Path(__file__).resolve().parent.parent.parent` in the species — same as every other Brain module
- Tests intentionally ignore `test_sandbox.py` and `test_deps.py` in fast-run commands — those require a real virtualenv
- `vitals_ui/node_modules` is excluded by `.gitignore` automatically via Next.js defaults
- `MCP_BEARER_TOKEN` must be set in `vitals_ui/.env.local` for the Manual Override proxy to authenticate against the Brain
