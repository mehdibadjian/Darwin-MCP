# Darwin-MCP — The Brain 🧠

A **stateless MCP SSE server** that enables LLMs to evolve, register, and invoke AI skills at runtime. Deploy on a $5 Droplet and watch your LLM build its own tools.

## What Is This?

Darwin-MCP is a system for **dynamic AI skill evolution**. The Host LLM (you, ChatGPT, Claude, etc.) can:

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
┌─────────────┐
│ Host LLM    │ ← You (ChatGPT, Claude, Copilot, etc.)
└──────┬──────┘
       │ MCP SSE (Bearer Token auth)
       ▼
┌─────────────────────────────────┐
│   Brain (mcp-evolution-core)    │ ← This repo, on $5 Droplet
│ • SSE Bridge                    │
│ • Mutation Engine               │
│ • Git Manager                   │
│ • Circuit Breaker               │
└──────┬────────────┬─────────────┘
       │            │
   reads/writes     submodule
       │            │
       ▼            ▼
┌──────────────────────────────────┐
│ Memory (mcp-evolution-vault)     │ ← Private git submodule
│ • /memory/dna/registry.json      │
│ • /memory/species/*.py           │
│ • /memory/requirements.txt       │
└──────────────────────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.9+
- Git (with SSH key configured for private submodule)
- $5 VPS or local development machine

### 1. Clone & Initialize

```bash
git clone https://github.com/yourusername/mcp-evolution-core.git
cd mcp-evolution-core
git submodule update --init --recursive  # Clone the memory submodule
pip install -r brain/requirements.txt
```

### 2. Set Environment

```bash
export MCP_BEARER_TOKEN="your-secure-token-here"
export GIT_SSH_COMMAND="ssh -i ~/.ssh/id_rsa"  # For private submodule
```

### 3. Start the Brain

```bash
# Local development (auto-reload on code changes)
uvicorn brain.bridge.sse_server:app --reload --host 0.0.0.0 --port 8000

# Or use systemd on production Droplet
sudo systemctl start darwin
sudo systemctl status darwin
```

### 4. Connect from Your LLM

Use the MCP CLI or SDK:

```bash
mcp install -t sse://localhost:8000 \
  --bearer-token "your-secure-token-here"
```

The Brain will expose all registered tools from `/memory/species/` as MCP resources.

## Key Concepts

### Species

A **species** is a registered AI skill — a Python module in `/memory/species/`. Each species:
- Has a `.py` file (the code)
- Is tracked in `registry.json`
- Can be invoked by the Host LLM over MCP
- Can evolve (mutate) when the Host sends new code + tests

### Mutation Pipeline

When you send code + tests via `request_evolution`:

1. **Validate** — Check inputs (non-empty strings, valid lists)
2. **Sandbox** — Create `/tmp/mutation_{timestamp}` virtualenv
3. **Install Deps** — `pip install -r requirements.txt` in isolated env
4. **Run Tests** — Execute pytest; fail fast if tests don't pass
5. **Promote** — Write `.py` file to `/memory/species/` only if tests pass
6. **Commit** — Git commit and push to private memory vault
7. **Update Registry** — Atomic write to `registry.json`

**No code enters the system without passing its tests.**

### Registry

The `memory/dna/registry.json` is the **single source of truth**:

```json
{
  "version": "1.0",
  "skills": {
    "leankg": {
      "name": "leankg",
      "version": 3,
      "description": "Knowledge graph explorer",
      "schema": { "type": "object", ... }
    }
  }
}
```

It's read on every startup and updated atomically after each successful mutation.

### Circuit Breaker

The `guard.py` module enforces three safety limits:

| Limit | Default | Purpose |
|-------|---------|---------|
| `MAX_RECURSION_DEPTH` | 8 | Prevent infinite skill → skill chains |
| `MAX_CPU_PERCENT` | 80 | Stop runaway CPU spins |
| `MAX_MEMORY_MB` | 512 | Prevent memory leaks from crashing the Brain |

## Architecture Layers

| Layer | Files | Role |
|-------|-------|------|
| **Presentation (API)** | `brain/bridge/sse_server.py` | HTTP/SSE endpoint, Bearer token auth, MCP transport |
| **Business Logic** | `brain/engine/mutator.py` | Mutation pipeline orchestration |
| **Validation** | `brain/engine/guard.py` | Recursion depth, resource limits, circuit breaker |
| **Sandbox** | `brain/engine/sandbox.py` | Isolated virtualenv creation and cleanup |
| **Data (Registry)** | `brain/utils/registry.py` | Read/write `registry.json` atomically |
| **Infrastructure** | `brain/utils/git_manager.py` | Git commits, push, rebase on conflict |
| **Filesystem Watch** | `brain/watcher/hot_reload.py` | File watcher, emit `list_changed` on mutation |
| **Dependencies** | `brain/engine/deps.py` | `requirements.txt` append and env rebuild |

## Common Tasks

### Ask the Host LLM to Create a New Skill

```python
request_evolution(
    name="my_tool",
    code="def my_tool(x): return x * 2",
    tests="def test(): assert my_tool(5) == 10",
    requirements=["numpy"]  # optional external deps
)
```

### View All Registered Skills

```bash
cat memory/dna/registry.json | jq '.skills | keys'
```

### Check the Brain's Health

```bash
curl -H "Authorization: Bearer $MCP_BEARER_TOKEN" \
  http://localhost:8000/health
```

### Run Tests Locally

```bash
pytest tests/ -v
```

## Documentation

- **[Getting Started](docs/tutorials/getting-started.md)** — Detailed setup, local dev, first mutation
- **[How-To Guides](docs/how-to/common-tasks.md)** — Create skills, debug mutations, deploy to Droplet
- **[Technical Manifesto](docs/reference/technical-manifesto.md)** — API contracts, Git state machine, sandbox isolation
- **[Agile Backlog](docs/reference/agile-backlog.md)** — Epics, user stories, sprint plans

## Deployment

### Local Development

```bash
# Start with auto-reload
uvicorn brain.bridge.sse_server:app --reload

# In another terminal, trigger a mutation
python -c "from brain.engine.mutator import request_evolution; ..."
```

### Production ($5 Droplet)

1. Clone repo and initialize submodule
2. Set `MCP_BEARER_TOKEN` in `/etc/environment`
3. Enable systemd service:
   ```bash
   sudo cp darwin.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now darwin
   ```
4. Monitor:
   ```bash
   sudo journalctl -u darwin -f
   ```

## Directory Structure

```
mcp-evolution-core/
├── README.md                    ← You are here
├── brain/
│   ├── bridge/
│   │   └── sse_server.py       ← HTTP entry point
│   ├── engine/
│   │   ├── mutator.py          ← Mutation orchestration
│   │   ├── sandbox.py          ← Isolated virtualenv
│   │   ├── guard.py            ← Safety limits
│   │   ├── pytest_runner.py    ← Test execution
│   │   └── deps.py             ← Dependency management
│   ├── utils/
│   │   ├── registry.py         ← Registry I/O
│   │   ├── git_manager.py      ← Git operations
│   │   └── web_fetch.py        ← HTTP utilities
│   └── watcher/
│       └── hot_reload.py       ← File watcher
├── memory/                      ← Git submodule (private)
│   ├── dna/
│   │   └── registry.json       ← Source of truth
│   ├── species/                ← AI skill files (.py)
│   └── requirements.txt        ← Shared deps
├── docs/
│   ├── index.md               ← Doc navigation
│   ├── reference/             ← API specs
│   ├── tutorials/             ← Guides
│   └── how-to/                ← Practical examples
├── tests/                      ← pytest test suite
└── darwin.service             ← Systemd unit file
```

## Contributing

1. Create a feature branch: `git checkout -b feat/my-feature`
2. Write tests first (see [How-To: Testing](docs/how-to/common-tasks.md#testing))
3. Implement code to pass tests
4. Commit: `git commit -m "feat: my feature"` (cite user story: `feat(US-5): ...`)
5. Push: `git push origin feat/my-feature`
6. Open a pull request

## License

TBD

## Support & Resources

- **Issues**: [GitHub Issues](https://github.com/yourusername/mcp-evolution-core/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/mcp-evolution-core/discussions)
- **Slack**: #darwin-mcp (if applicable)

---

**The Brain is evolving. Train it well.** 🚀
