# Intelligence Dashboard — Research & Working Notes

**Research Date**: 2026-04-19
**Researchers**: Claude + pappi

## Initial Understanding

The request is to evolve a new species `generate_vitals_dashboard` using the Two-Stage Handshake: first register the species via `request_evolution`, then invoke it to produce a `vitals_ui/` folder containing a working Next.js + Tailwind dashboard. The dashboard must have three panels: a live tail of `progress.txt`, a visual DNA map from `registry.json`, and a manual `request_evolution` trigger form.

## Research Process

### Files Examined:
- `memory/species/scaffold_generator.py` (full file, 338 lines)
  - Finding: embeds file trees as `_TEMPLATE` dicts; `dry_run` mode; returns manifest dict
  - Pattern to follow exactly for `generate_vitals_dashboard`
- `memory/dna/registry.json` (full file)
  - Finding: 8 registered species; schema has `organism_version`, `last_mutation`, `skills`
  - Key fields per skill: `path`, `entry_point`, `runtime`, `dependencies`, `evolved_at`, `status`, `version`, `success_count`, `failure_count`, `total_calls`, `last_used_at`
- `brain/bridge/sse_server.py` (full file, 324 lines)
  - Finding: `/evolve` POST endpoint accepts `name`, `code`, `tests`, `requirements`; Bearer Token auth via `Authorization: Bearer <token>`; vault routing via `X-Vault-Repo` header
  - Finding: `/sse` GET streams `tool_list` then `list_changed` events; 30 s keepalive
- `brain/engine/mutator.py` (full file, 210 lines)
  - Finding: `request_evolution()` full 9-step pipeline; `git_commit=True` triggers Two-Stage Handshake commit
- `brain/utils/registry.py` (full file)
  - Finding: `REGISTRY_PATH` = `parent.parent.parent / memory / dna / registry.json`; `compute_success_rate()` exists
- `brain/engine/vitals.py` (full file)
  - Finding: `get_evolution_log_tail()` reads last N lines of `evolution.log`; `collect()` returns CPU/RAM/disk
- `progress.txt` (full file)
  - Finding: plain text; sprint records separated by `##` headers; appended over time; ~75 lines currently
- `tests/test_scaffold_generator.py` (full file, 173 lines)
  - Finding: class-based pytest; `sys.path.insert` to add `memory/species`; `tmp_path` fixture; tests file existence + content assertions

### Sub-tasks Spawned:
1. **codebase-explorer** (background explore agent)
   - Confirmed full brain/ structure, species list, registry schema, SSE transport patterns
2. **pattern-discovery** (background explore agent)
   - Confirmed Two-Stage Handshake references, scaffold_generator patterns, test conventions

## Questions Asked & Answers

1. Q: Should the dashboard read registry.json directly from the filesystem or call the Brain's `/sse` endpoint?
   A: Direct filesystem read — simpler, no auth token needed for data reads, consistent with how `vitals.py` works.
   Follow-up: bake `brain_root` path into generated API routes at scaffold time.

2. Q: Should `generate_vitals_dashboard` extend `scaffold_generator` or be standalone?
   A: Standalone — avoids coupling, keeps the species self-contained, follows the single-responsibility pattern of other species.

3. Q: What does "Two-Stage Handshake" mean in this context?
   A: Stage 1 = `request_evolution(name, code, tests)` → species registered in Brain. Stage 2 = invoke the newly-registered species to produce `vitals_ui/`. Found in `brain/engine/mutator.py:65` and confirmed by `brain/bridge/sse_server.py:219`.

## Key Discoveries

### Technical Discoveries:
- `scaffold_generator.py` uses `{name}` and `{name_slug}` as the only substitution tokens. We need `{brain_root}` and `{brain_port}` for the dashboard — handled by the same `.replace()` pattern at `scaffold_generator.py:317`.
- `brain/utils/registry.py:228-241` already has `compute_success_rate()` — we replicate this logic in TypeScript in `app/api/dna/route.ts` rather than calling Python from Next.js.
- Next.js 14 App Router uses `ReadableStream` + `new Response(stream, ...)` for SSE routes — no `res.write()` or Node.js streams needed.
- The `MCP_BEARER_TOKEN` env var is used by the Brain (`sse_server.py:32`); the same token is forwarded from `vitals_ui`'s `.env.local` to the `/api/evolve` proxy route.
- `progress.txt` is append-only plain text — polling by file size delta (tracking `lastSize`) is the correct tail strategy.

### Patterns to Follow:
- Species entry point function name == file stem == registry key (e.g., `scaffold_generator` / `generate_vitals_dashboard`)
- `run()` alias at bottom of every species file (`memory/species/scaffold_generator.py:336`)
- `from __future__ import annotations` at top of every species
- Test file at `tests/test_<species_name>.py`; `sys.path.insert(0, "memory/species")` at top

### Constraints Identified:
- Species must have **zero third-party Python dependencies** — `generate_vitals_dashboard` uses stdlib only (`os`, `pathlib`, `typing`)
- Next.js `app/api/*/route.ts` files use `fs` (Node.js built-in) — no npm packages needed for file reads
- `output_dir` must not already exist — guard matches `scaffold_generator.py:305-309`
- `brain_root` defaults to `Path(__file__).resolve().parent.parent.parent` — same resolution used in `brain/utils/registry.py:26` and `brain/engine/vitals.py:12`

## Design Decisions

### Decision 1: File tree embedding approach
**Options considered:**
- Option A: Embed full file tree as `_DASHBOARD_FILES` dict in the species (like `scaffold_generator`) — self-contained, no filesystem deps at runtime
- Option B: Read template files from a `brain/templates/` directory at invoke time — requires template files to be present on Droplet

**Chosen**: Option A
**Rationale**: Matches existing scaffold_generator pattern exactly; species remains a single portable Python file; no risk of missing template files post-deployment.

### Decision 2: Dashboard data source for registry
**Options considered:**
- Option A: Direct `fs.readFileSync` on `registry.json` — simple, no auth, immediate
- Option B: Call Brain's `/sse` endpoint and parse the `tool_list` event — requires Bearer token in Next.js server

**Chosen**: Option A
**Rationale**: Dashboard is a local dev tool running alongside the Brain on the same machine. Direct file access is faster, simpler, and consistent with how `vitals.py` reads `evolution.log`.

### Decision 3: Live Feed strategy
**Options considered:**
- Option A: Poll file by size delta every 2 s, send new lines as SSE `data:` events — simple, no inotify/chokidar dependency
- Option B: Use `chokidar` or Node.js `fs.watch` — more reactive but adds an npm dependency

**Chosen**: Option A
**Rationale**: Keeps the scaffolded project dependency-minimal; 2 s polling latency is acceptable for a sprint log viewer.

## Open Questions (During Research)

- [x] Does `request_evolution` need `memory_dir` set for git commit? — Resolved: yes, set `memory_dir=str(brain_root / "memory")` and `git_commit=True`
- [x] Does Next.js 14 App Router support SSE via `ReadableStream`? — Resolved: yes, via `new Response(stream, { headers: { "Content-Type": "text/event-stream" } })`
- [x] What port does the Brain run on? — Resolved: default 8000 (from `darwin.service`); configurable via `brain_port` param

## Code Snippets Reference

### success_rate computation (Python → TypeScript):
```python
# brain/utils/registry.py:228-241
def compute_success_rate(skill: dict) -> float:
    total = skill.get("total_calls", 0)
    if total == 0:
        return 1.0
    success = skill.get("success_count", 0)
    failure = skill.get("failure_count", 0)
    denominator = success + failure
    if denominator == 0:
        return 1.0
    return success / denominator
```

```typescript
// app/api/dna/route.ts — replicated in TypeScript
const success = entry.success_count ?? 0;
const failure = entry.failure_count ?? 0;
const total = success + failure;
const successRate = total === 0 ? 1.0 : success / total;
```

### scaffold_generator substitution pattern (to replicate):
```python
# memory/species/scaffold_generator.py:317
filled = content.replace("{name_slug}", name_slug).replace("{name}", name)
```

```python
# generate_vitals_dashboard equivalent
filled = content.replace("{brain_root}", brain_root).replace("{brain_port}", str(brain_port))
```

### request_evolution invocation (Two-Stage Handshake Stage 1):
```python
# brain/engine/mutator.py:65 signature
request_evolution(
    name="generate_vitals_dashboard",
    code=Path("memory/species/generate_vitals_dashboard.py").read_text(),
    tests=Path("tests/test_generate_vitals_dashboard.py").read_text(),
    requirements=[],
    git_commit=True,
    memory_dir=str(brain_root / "memory"),
)
```
