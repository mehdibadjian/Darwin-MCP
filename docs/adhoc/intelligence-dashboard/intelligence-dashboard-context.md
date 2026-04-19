# Intelligence Dashboard — Context & Dependencies

**Last Updated**: 2026-04-19

## Quick Summary

Evolve and invoke a new species `generate_vitals_dashboard` that scaffolds a Sovereign-themed Next.js 14 + Tailwind dashboard (`vitals_ui/`) with three panels: a live SSE tail of `progress.txt`, a DNA Map from `registry.json`, and a manual `request_evolution` trigger form.

## Key Files & Locations

### Files to Create:
- `memory/species/generate_vitals_dashboard.py` — new species; embeds full Next.js file tree as `_DASHBOARD_FILES` dict
- `tests/test_generate_vitals_dashboard.py` — 9 pytest tests (written first, TDD)
- `vitals_ui/` — generated output (not committed; add to `.gitignore`)

### Files to Reference:
- `memory/species/scaffold_generator.py:234-332` — entry point pattern + `dry_run` + manifest return shape
- `memory/species/scaffold_generator.py:157-220` — `_NEXTJS_FILES` dict — base template to extend
- `tests/test_scaffold_generator.py` — test structure to mirror
- `brain/bridge/sse_server.py:219-263` — `/evolve` POST endpoint (proxied by dashboard)
- `brain/utils/registry.py:26-27` — `REGISTRY_PATH` resolution pattern
- `brain/engine/vitals.py:12` — `brain_root` resolution: `Path(__file__).resolve().parent.parent.parent`
- `memory/dna/registry.json` — read directly by `app/api/dna/route.ts`
- `progress.txt` — tailed by `app/api/feed/route.ts`

### Generated Files Inside `vitals_ui/` (16 files):
| File | Purpose |
|------|---------|
| `package.json` | next 14.2.3, react 18, tailwindcss 3.4.3 |
| `tailwind.config.js` | Sovereign palette: `#00ff41` accent, `#0a0a0a` bg |
| `postcss.config.js` | Tailwind + autoprefixer |
| `next.config.js` | `reactStrictMode: true` |
| `tsconfig.json` | TypeScript, bundler resolution |
| `.env.local` | `NEXT_PUBLIC_BRAIN_URL`, `MCP_BEARER_TOKEN` |
| `app/globals.css` | JetBrains Mono import, Tailwind directives, sovereign scrollbar |
| `app/layout.tsx` | Dark RootLayout |
| `app/page.tsx` | Three-panel grid |
| `app/api/dna/route.ts` | GET — reads registry.json directly |
| `app/api/feed/route.ts` | GET — SSE tail of progress.txt (2 s poll) |
| `app/api/evolve/route.ts` | POST — proxy to Brain `/evolve` |
| `components/LiveFeed.tsx` | EventSource client, auto-scroll, last 200 lines |
| `components/DnaMap.tsx` | 15 s refresh, SuccessBar, status badges |
| `components/ManualOverride.tsx` | name/code/tests/requirements form |
| `README.md` | Setup and run instructions |

## Dependencies

### Python (species itself — stdlib only):
- `os`, `pathlib.Path`, `typing.Optional` — no third-party packages
- `requirements` param for `request_evolution`: `[]`

### Node.js (inside `vitals_ui/`):
- `next@14.2.3`, `react@^18.3.0`, `react-dom@^18.3.0`
- `tailwindcss@^3.4.3`, `postcss@^8.4.38`, `autoprefixer@^10.4.19`
- `typescript@^5.4.5`, `@types/node@^20.12.0`, `@types/react@^18.3.0`
- `fs` — Node.js built-in (no extra npm package for file reads)

### External:
- Brain SSE server running on `localhost:8000` (for Manual Override proxy)
- `MCP_BEARER_TOKEN` env var — required for `/api/evolve` to authenticate to Brain

## Key Technical Decisions

1. **Embedded file tree**: `_DASHBOARD_FILES` dict in species (not external templates) — same pattern as `scaffold_generator`; self-contained portable file
2. **Direct filesystem reads**: `app/api/dna/route.ts` reads `registry.json` via `fs.readFileSync` — no Brain HTTP call needed for data
3. **SSE via size delta polling**: `app/api/feed/route.ts` polls `progress.txt` every 2 s tracking file size — no `chokidar` dependency
4. **`brain_root` baked at scaffold time**: substituted as a literal string into API routes — no runtime path resolution needed in TypeScript

## Integration Points

- **Brain `/evolve` endpoint**: `app/api/evolve/route.ts` proxies POST requests; forwards `Authorization: Bearer` from `.env.local`
- **`registry.json`**: read directly at `<brain_root>/memory/dna/registry.json`
- **`progress.txt`**: read directly at `<brain_root>/progress.txt`
- **`_emit_list_changed`**: triggered automatically when `request_evolution` succeeds (Step 9 in mutator.py); connected IDEs see new tool without reconnect

## Environment Requirements

- Python 3.9+ (for species registration/invocation)
- Node.js 18+ (for `vitals_ui` — Next.js 14 requirement)
- Brain SSE server running for Manual Override panel to function
- `MCP_BEARER_TOKEN` set in environment and in `vitals_ui/.env.local`

## Related Documentation

- Research notes: `docs/adhoc/intelligence-dashboard/intelligence-dashboard-research.md`
- Implementation plan: `docs/adhoc/intelligence-dashboard/intelligence-dashboard-plan.md`
- Task checklist: `docs/adhoc/intelligence-dashboard/intelligence-dashboard-tasks.md`
