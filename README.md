# Darwin-MCP — The Brain 🧠

> **🚧 BETA** — Active development. APIs may change between minor versions. Not recommended for production without review.

![Beta](https://img.shields.io/badge/status-beta-orange) ![Tests](https://img.shields.io/badge/tests-249%20passing-brightgreen) ![Python](https://img.shields.io/badge/python-3.9%2B-blue) ![License](https://img.shields.io/badge/license-TBD-lightgrey)

A **stateless MCP SSE server** that enables LLMs to evolve, register, and invoke AI skills at runtime — and now powers a **cloud-less AI assistant** running Gemma 2b on your phone over NordVPN Meshnet with zero API costs.

## What Is This?

Darwin-MCP is a system for **dynamic AI skill evolution**. The Host LLM (you, ChatGPT, Claude, Gemma 2b, etc.) can:

1. **Request Evolution** — Send Python code + tests to the Brain
2. **Sandbox Test** — Brain validates code in isolation (no dependency conflicts)
3. **Promote to Registry** — Passing tests → species file committed to git
4. **Invoke Skills** — Brain exposes all registered tools over MCP protocol

The system implements **three biosafety layers**:
- **BSL-1**: Dependency isolation (separate `requirements.txt` per mutation)
- **BSL-2**: Resource & recursion limits (CPU, RAM, call depth guardrails)
- **BSL-3**: Detailed error reporting (file + line + context in every failure)

### The Triad Architecture

```
┌──────────────────────────────────────────────┐
│ Host LLM                                     │
│ ChatGPT / Claude / Copilot / Gemma 2b (phone)│
└──────┬───────────────────────────────────────┘
       │ MCP SSE  (Bearer Token auth)
       │ — or — NordVPN Meshnet (cloud-less mode)
       ▼
┌──────────────────────────────────────────────┐
│  Brain  (mcp-evolution-core)  ← This repo    │
│                                              │
│  bridge/                                     │
│    sse_server.py      SSE transport + auth   │
│    router.py          Dynamic Tool Router ✨  │
│                                              │
│  engine/                                     │
│    mutator.py         Mutation pipeline      │
│    guard.py           Circuit breaker        │
│    sandbox.py         Isolated virtualenv    │
│                                              │
│  middleware/                                 │
│    json_validator.py  Self-healing JSON ✨   │
│                                              │
│  utils/                                      │
│    context_buffer.py  Flash Summarizer ✨    │
│    registry.py        Registry I/O           │
│    git_manager.py     Git state machine      │
│    web_fetch.py       HTTP utilities         │
│                                              │
│  prompts/                                    │
│    system_prompt.txt  XML reasoning rails ✨ │
│    golden_log.txt     Few-shot primer ✨     │
│                                              │
│  config/                                     │
│    meshnet.json       Meshnet bridge ✨      │
└──────┬───────────────────────────────────────┘
       │ reads/writes (git submodule)
       ▼
┌──────────────────────────────────────────────┐
│  Memory  (mcp-evolution-vault)  ← Private    │
│  dna/registry.json    Source of truth        │
│  species/*.py         AI skill files         │
│    brave_search.py    Real-time web search ✨ │
│    sequential_thinking.py  CoT scaffold ✨   │
└──────────────────────────────────────────────┘
```

> ✨ = added in the Cloud-less AI update

---

## 🆕 Cloud-less AI Mode

Run a **free, private AI assistant** that rivals Claude + Perplexity with zero cloud costs:

| Component | What it does |
|-----------|-------------|
| **Dynamic Tool Router** | Scores all skills by query relevance; exposes only top-3 to Gemma 2b. Prevents hallucination from tool overload. |
| **JSON Validator Middleware** | Catches malformed tool calls from small models, returns a `retry_hint` so Gemma self-corrects. |
| **Flash Summarizer** | Compresses web pages to ≤400 tokens before sending over Meshnet. No LLM required. |
| **XML Reasoning Rails** | `<thought>/<call>/<answer>` system prompt enforces rigid syntax on small models. |
| **Golden Log** | 3 curated perfect-interaction transcripts act as few-shot examples at context start. |
| **Brave Search** | Perplexity-mode real-time web research via Brave Search API. |
| **Sequential Thinking** | Deterministic chain-of-thought scaffold for multi-step problems. |

**→ [Full Cloud-less AI Plan](docs/reference/cloudless-ai-plan.md)**
**→ [Meshnet Setup Guide](docs/how-to/meshnet-setup.md)**

---

## Quick Start

### Prerequisites

- Python 3.9+
- Git (with SSH key configured for private submodule)
- $5 VPS or local development machine

### 1. Clone & Initialize

```bash
git clone https://github.com/mehdibadjian/Darwin-MCP.git
cd mcp-evolution-core
git submodule update --init --recursive
pip install -r brain/requirements.txt
```

### 2. Set Environment

```bash
export MCP_BEARER_TOKEN="your-secure-token-here"
export GIT_SSH_COMMAND="ssh -i ~/.ssh/id_rsa"  # for private submodule

# Optional — for cloud-less Brave Search
export BRAVE_API_KEY="your-brave-api-key"
```

### 3. Start the Brain

```bash
# Local development (auto-reload)
uvicorn brain.bridge.sse_server:app --reload --host 0.0.0.0 --port 8000

# Production (systemd)
sudo systemctl start darwin
sudo systemctl status darwin
```

### 4. Connect from Your LLM

```bash
mcp install -t sse://localhost:8000 \
  --bearer-token "your-secure-token-here"
```

### 5. Cloud-less Mode (Gemma 2b on phone)

```bash
# Edit brain/config/meshnet.json — set base_url to your phone's Meshnet IP
# Then inject brain/prompts/system_prompt.txt + golden_log.txt into Gemma's context
# Full guide: docs/how-to/meshnet-setup.md
```

---

## Key Concepts

### Species

A **species** is a registered AI skill — a Python module in `/memory/species/`. Each species:
- Has a `.py` file (the code) and an entry in `registry.json`
- Exposes a `short_description` (≤10 words) used by the Tool Router
- Can be invoked by the Host LLM over MCP
- Can evolve (mutate) when the Host sends new code + tests

### Mutation Pipeline

1. **Validate** — Check inputs (non-empty strings, valid lists)
2. **Sandbox** — Create `/tmp/mutation_{timestamp}` virtualenv
3. **Install Deps** — `pip install` in isolated env
4. **Run Tests** — Execute pytest; fail fast if tests don't pass
5. **Promote** — Write `.py` to `/memory/species/` only if tests pass
6. **Commit** — Git commit + push to private memory vault
7. **Update Registry** — Atomic write to `registry.json`

**No code enters the system without passing its tests.**

### Registry

`memory/dna/registry.json` is the **single source of truth**. Each skill entry now includes `short_description` for Tool Router scoring:

```json
{
  "skills": {
    "brave_search": {
      "status": "active",
      "short_description": "Search web for real-time facts.",
      "entry_point": "brave_search",
      "version": 1
    }
  }
}
```

### Dynamic Tool Router

`GET /sse?query=<text>` activates the router. Instead of sending all tools to the model, it scores each skill's `short_description` against the query using TF-IDF overlap and returns only the top-3 matches. Critical for models like Gemma 2b that hallucinate with >5 tools visible.

### Circuit Breaker

| Limit | Default | Purpose |
|-------|---------|---------|
| `MAX_RECURSION_DEPTH` | 3 | Prevent infinite skill → skill chains |
| `MAX_CPU_PERCENT` | 80% | Stop runaway CPU spins |
| `MAX_MEMORY_MB` | 256 MB | Prevent memory leaks crashing the Brain |

---

## Architecture Layers

| Layer | File | Role |
|-------|------|------|
| **SSE Transport** | `brain/bridge/sse_server.py` | HTTP/SSE endpoint, Bearer token auth, MCP protocol |
| **Tool Router** | `brain/bridge/router.py` | TF-IDF query→tool scoring, top-N filtering |
| **Mutation Engine** | `brain/engine/mutator.py` | Full evolution pipeline orchestration |
| **Circuit Breaker** | `brain/engine/guard.py` | Recursion depth, CPU/RAM limits, Toxic flag |
| **Sandbox** | `brain/engine/sandbox.py` | Isolated virtualenv creation and cleanup |
| **JSON Middleware** | `brain/middleware/json_validator.py` | Self-healing malformed JSON correction |
| **Flash Summarizer** | `brain/utils/context_buffer.py` | Extractive ≤400-token compression of web content |
| **Registry I/O** | `brain/utils/registry.py` | Atomic read/write of `registry.json` |
| **Git Manager** | `brain/utils/git_manager.py` | Commit, push, rebase on conflict |
| **Web Fetch** | `brain/utils/web_fetch.py` | HTTP utilities for search + page fetch |
| **Hot Reload** | `brain/watcher/hot_reload.py` | Watchdog, emits `list_changed` SSE events |
| **Deps** | `brain/engine/deps.py` | `requirements.txt` append + env rebuild |

---

## Common Tasks

### Create a New Skill

```python
from brain.engine.mutator import request_evolution

request_evolution(
    name="my_tool",
    code="def my_tool(x): return x * 2",
    tests="def test(): assert my_tool(5) == 10",
    requirements=["numpy"]
)
```

### Route Tools by Query (Cloud-less mode)

```bash
curl -H "Authorization: Bearer $MCP_BEARER_TOKEN" \
  "http://localhost:8000/sse?query=search+the+web+for+news"
# Returns only the 3 most relevant tools — not all skills
```

### Search the Web via Brain

```bash
curl -X POST -H "Authorization: Bearer $MCP_BEARER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "latest Python release", "fetch": true}' \
  http://localhost:8000/search
# Response includes flash_report (≤400 tokens) alongside full text
```

### View Registered Skills

```bash
cat memory/dna/registry.json | jq '.skills | keys'
```

### Run Tests

```bash
pytest tests/ -v
# 249 passing, 2 skipped
```

---

## Documentation

| Document | Purpose |
|----------|---------|
| **[Getting Started](docs/tutorials/getting-started.md)** | Local setup, first skill, verify install |
| **[How-To: Common Tasks](docs/how-to/common-tasks.md)** | Create skills, debug, deploy, rollback |
| **[How-To: Meshnet Setup](docs/how-to/meshnet-setup.md)** | NordVPN Meshnet + Gemma 2b on phone |
| **[Cloud-less AI Plan](docs/reference/cloudless-ai-plan.md)** | Full architecture, design decisions, all components |
| **[Technical Manifesto](docs/reference/technical-manifesto.md)** | API contracts, Git state machine, BSL biosafety |
| **[Agile Backlog](docs/reference/agile-backlog.md)** | Epics, stories, sprint plans |

---

## Deployment

### Local Development

```bash
uvicorn brain.bridge.sse_server:app --reload
```

### Production ($5 Droplet)

```bash
sudo cp darwin.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now darwin
sudo journalctl -u darwin -f
```

---

## Directory Structure

```
mcp-evolution-core/
├── brain/
│   ├── bridge/
│   │   ├── sse_server.py        ← HTTP/SSE entry point
│   │   └── router.py            ← Dynamic Tool Router ✨
│   ├── config/
│   │   └── meshnet.json         ← Meshnet bridge config ✨
│   ├── engine/
│   │   ├── mutator.py           ← Mutation orchestration
│   │   ├── sandbox.py           ← Isolated virtualenv
│   │   ├── guard.py             ← Circuit breaker
│   │   ├── pytest_runner.py     ← Test execution
│   │   └── deps.py              ← Dependency management
│   ├── middleware/
│   │   └── json_validator.py    ← Self-healing JSON ✨
│   ├── prompts/
│   │   ├── system_prompt.txt    ← XML reasoning rails ✨
│   │   └── golden_log.txt       ← Few-shot primer ✨
│   └── utils/
│       ├── registry.py          ← Registry I/O
│       ├── git_manager.py       ← Git operations
│       ├── web_fetch.py         ← HTTP utilities
│       └── context_buffer.py    ← Flash Summarizer ✨
├── memory/                       ← Git submodule (private)
│   ├── dna/registry.json         ← Source of truth
│   └── species/
│       ├── brave_search.py       ← Real-time web search ✨
│       ├── sequential_thinking.py← CoT scaffold ✨
│       ├── leankg.py             ← Code knowledge graph
│       ├── nestjs_best_practices.py
│       └── fpga_best_practices.py
├── docs/
│   ├── index.md
│   ├── reference/
│   │   ├── cloudless-ai-plan.md  ← ✨ new
│   │   ├── technical-manifesto.md
│   │   └── agile-backlog.md
│   ├── tutorials/getting-started.md
│   └── how-to/
│       ├── common-tasks.md
│       └── meshnet-setup.md      ← ✨ new
├── tests/                        ← pytest suite (249 passing)
└── darwin.service                ← Systemd unit
```

---

## Contributing

> This project is in **beta**. Contributions are welcome — please follow the conventions below exactly.

### Workflow

1. **Branch** — `git checkout -b feat/US-N-short-description`
2. **TDD red** — Write failing tests first, commit them: `test(US-N): describe what is tested`
3. **TDD green** — Implement code to pass tests, commit: `feat(US-N): describe what is built`
4. **Refactor** — Clean up, commit: `refactor(US-N): describe change`
5. **Push & PR** — `git push origin feat/US-N-short-description`

### Commit Format

```
type(scope): short imperative description

Optional body explaining WHY, not WHAT.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
```

**Types:** `feat` · `fix` · `test` · `refactor` · `docs` · `chore`
**Scopes:** `US-N` for story work · `cloudless` · `guard` · `registry` · etc.

### Rules

- ✅ Tests must pass before any `feat` commit: `pytest tests/ -q`
- ✅ Every new module needs a corresponding `tests/test_<module>.py`
- ✅ `short_description` on all new registry skills (≤10 words, action-first verb)
- ✅ No secrets in code — tokens always from environment variables
- ❌ Do not skip the `test` commit — red phase is required
- ❌ Do not commit directly to `main`

### Beta Limitations

| Area | Status |
|------|--------|
| `/health` endpoint | Not yet implemented |
| Multi-tenant vault routing | Beta — API may change |
| Meshnet auto-discovery | Manual config required |
| Brave Search species | Requires `BRAVE_API_KEY` |
| Windows support | Untested |

---

## License

TBD

## Support & Resources

- **Issues**: [GitHub Issues](https://github.com/mehdibadjian/Darwin-MCP/issues)
- **Discussions**: [GitHub Discussions](https://github.com/mehdibadjian/Darwin-MCP/discussions)

---

**The Brain is evolving. Train it well.** 🚀
