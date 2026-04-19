# Darwin-MCP Intelligence Dashboard

Sovereign-themed vitals interface for the Darwin-MCP organism.

## Panels

| Panel | Source | Update cadence |
|-------|--------|----------------|
| **Metabolism Record** | `progress.txt` (SSE tail) | Real-time (2 s poll) |
| **DNA Map** | `registry.json` (direct read) | Every 15 s |
| **Manual Override** | Brain `/evolve` API | On submit |

## Run

```bash
npm install
npm run dev    # http://localhost:3000
```

## Environment

Edit `.env.local`:

```
NEXT_PUBLIC_BRAIN_URL=http://localhost:8000
MCP_BEARER_TOKEN=your-token-here
```

> Scaffolded by Darwin-MCP `generate_vitals_dashboard` species.
