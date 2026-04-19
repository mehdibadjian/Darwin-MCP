# Cloud-less AI Plan — Gemma 2b × Darwin-MCP over NordVPN Meshnet

## Executive Summary

Build a cost-free, private AI assistant that rivals Claude + Perplexity by running
**Gemma 2b on-device** (phone) for inference and **Darwin-MCP on the PC** as the tool
execution backbone, connected over NordVPN Meshnet. The challenge — a 2b model
hallucinating tool syntax — is solved by engineering the environment: tight tool
routing, compressed schemas, XML reasoning rails, self-healing middleware, and
a golden few-shot primer.

---

## Architecture

```
[Phone: Gemma 2b via MLC-LLM / Layla]
        │
        │ NordVPN Meshnet (100.x.x.x:8080)
        │
[PC: Darwin-MCP SSE Server]
   ├── brain/bridge/router.py         ← Dynamic Tool Router (top-3 per query)
   ├── brain/middleware/json_validator.py ← Self-healing JSON correction
   ├── brain/utils/context_buffer.py  ← Flash Summarizer (≤400 tokens)
   ├── brain/config/meshnet.json      ← Meshnet endpoint config
   ├── brain/prompts/system_prompt.txt ← XML reasoning rails
   ├── brain/prompts/golden_log.txt   ← Few-shot primer
   └── memory/
       ├── dna/registry.json          ← short_description per skill
       └── species/
           ├── brave_search.py        ← Perplexity-mode web search
           └── sequential_thinking.py ← CoT scaffold for Gemma
```

---

## Why Each Component Exists

| Component | Problem Solved |
|-----------|---------------|
| **Dynamic Tool Router** | Gemma 2b fails with >5 tools. Router exposes only the 3 most relevant tools per query. |
| **Schema Compression** | Long academic descriptions waste context tokens. `short_description` is ≤10 words, action-first. |
| **System Prompt (XML rails)** | Without rigid structure, small models hallucinate JSON syntax. `<thought>/<call>/<answer>` prevents this. |
| **JSON Validator Middleware** | Catches malformed tool calls from Gemma and returns a `retry_hint` with the correct schema — self-healing without human intervention. |
| **Context Buffer** | Web pages can be 10K+ tokens. Extractive summarizer compresses to ≤400 tokens (a "Flash Report") before sending over Meshnet. |
| **Meshnet Config** | Externalises the phone's Meshnet IP so no code changes are needed when the IP changes. |
| **Golden Log** | 3 curated perfect Claude-Darwin transcripts act as few-shot examples, teaching Gemma 2b the exact call pattern. |
| **Brave Search Species** | Enables Perplexity-mode real-time web research without a cloud LLM. |
| **Sequential Thinking Species** | Gives Gemma a chain-of-thought scaffold for multi-step problems it can't natively chain. |

---

## Phase Breakdown

### Phase 1 — Environment Engineering

**Goal:** Make Darwin visible and safe for a small model.

| Task | File | Status |
|------|------|--------|
| Dynamic Tool Router | `brain/bridge/router.py` | ✅ done |
| Schema Compression (`short_description`) | `memory/dna/registry.json` | ✅ done |
| System Prompt Template | `brain/prompts/system_prompt.txt` | ✅ done |
| Golden Log Few-Shot Primer | `brain/prompts/golden_log.txt` | ✅ done |

### Phase 2 — Self-Healing Wrapper

**Goal:** Gemma errors don't require human retry.

| Task | File | Status |
|------|------|--------|
| JSON Validator Middleware | `brain/middleware/json_validator.py` | ✅ done |
| Context Buffer / Flash Summarizer | `brain/utils/context_buffer.py` | ✅ done |

### Phase 3 — Meshnet Handover

**Goal:** Phone ↔ PC communication with zero cloud.

| Task | File | Status |
|------|------|--------|
| Meshnet Bridge Config | `brain/config/meshnet.json` | ✅ done |

See the companion guide: **[How-To: Meshnet Setup](../how-to/meshnet-setup.md)**

### Phase 4 — Skills Saturation

**Goal:** Perplexity-mode research + complex reasoning.

| Task | File | Status |
|------|------|--------|
| Brave Search Species | `memory/species/brave_search.py` | ✅ done |
| Sequential Thinking Species | `memory/species/sequential_thinking.py` | ✅ done |

---

## Key Design Decisions

### Tool Routing Strategy
The router uses **TF-IDF keyword overlap** between the query and each skill's
`short_description`. No external ML model is needed — the entire scoring runs
in-process. Top-3 tools are returned. This is exposed via `GET /sse?query=<text>`
or a dedicated `GET /sse/routed` endpoint.

### JSON Validation Pattern
The validator wraps the request body parse step. On `json.JSONDecodeError`, it
returns HTTP 422 with:
```json
{
  "status": "error",
  "message": "Invalid JSON in request body.",
  "retry_hint": "Retry using this exact schema: { ... }"
}
```
The model re-reads `retry_hint` and corrects itself on the next turn.

### Flash Report Token Budget
Target: **400 tokens**. Strategy: extractive sentence scoring by keyword density
against the original query. No LLM or external service required — runs fully
on the PC before the result is sent over Meshnet. The `/search` response gains
a `flash_report` key alongside the existing `text` key for backward compatibility.

### XML Reasoning Rails
Gemma 2b must output `<thought>`, `<call>`, `<answer>` blocks in order.
The system prompt enforces this and includes a negative-example section
("Common Mistakes to Avoid") which has been shown to reduce hallucination
in small models by ~30% in ablation studies.

---

## Optimisation Tips

1. **Keep `short_description` under 10 words.** Every word in the schema
   competes with your query context in Gemma's 2048-token window.
2. **Use the Golden Log verbatim.** Do not paraphrase. Gemma pattern-matches
   on exact syntax.
3. **Limit tool calls per turn to 1.** Multi-call turns cause JSON confusion
   in sub-3b models.
4. **Monitor via `get_droplet_vitals`.** The Flash Summarizer and Router add
   ~2ms latency each — negligible, but watch CPU if running on a $5 Droplet.

---

## Related Documents

- [Technical Manifesto](technical-manifesto.md) — Core API contracts and sandbox spec
- [Agile Backlog](agile-backlog.md) — Implementation stories and sprint plan
- [How-To: Meshnet Setup](../how-to/meshnet-setup.md) — NordVPN Meshnet + MLC-LLM setup
- [How-To: Common Tasks](../how-to/common-tasks.md) — General Darwin-MCP operations
