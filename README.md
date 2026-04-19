# Darwin-MCP — The Sovereign Organism 🧬

[![Tests](https://img.shields.io/badge/tests-298%20passing-brightgreen)](https://github.com/mehdibadjian/Darwin-MCP/actions)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/protocol-MCP%20SSE-purple)](https://modelcontextprotocol.io/)
[![Status](https://img.shields.io/badge/status-sovereign-gold)](https://github.com/mehdibadjian/Darwin-MCP)
[![License](https://img.shields.io/badge/license-TBD-lightgrey)](LICENSE)

> A living system where LLMs write, test, register, and invoke AI skills at runtime — governed by biosafety, resurrected by cron, and immune to gene duplication.

---

## The Triad Architecture

Darwin-MCP is not a server. It is an **organism** — composed of three decoupled entities with precisely defined roles:

```
┌─────────────────────────────────────────────────────────────────┐
│  HOST  (The Mind)                                               │
│  ChatGPT · Claude · Copilot · Gemma 2b on your phone           │
│  Issues mutation requests · Invokes skills · Reads SSE stream   │
└──────────────────────┬──────────────────────────────────────────┘
                       │  MCP SSE over HTTPS  (Bearer Token)
                       │  — or —  NordVPN Meshnet (cloud-less mode)
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│  BRAIN  (The Logic)   ← This repository                        │
│  github.com/mehdibadjian/Darwin-MCP                             │
│                                                                 │
│  bridge/sse_server.py   ← Membrane: SSE transport + auth        │
│  bridge/router.py       ← Dynamic Tool Router (TF-IDF top-3)   │
│  engine/mutator.py      ← Ribosome: mutation pipeline           │
│  engine/sandbox.py      ← Lysosome: isolated venv + cache purge │
│  engine/guard.py        ← Circuit breaker: CPU/RAM/depth limits │
│  engine/inquiry.py      ← LeanKG Guard: gene duplication check  │
│  engine/peer_review.py  ← Council of Peers: multi-model review  │
│  watcher/hot_reload.py  ← MCP notifications/tools/list_changed  │
│  scripts/sanity_check.sh← Resurrection: hourly health monitor   │
│  utils/git_manager.py   ← Git state machine                     │
│  utils/registry.py      ← Atomic registry I/O                   │
└──────────────────────┬──────────────────────────────────────────┘
                       │  Git Submodule  (SSH)
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│  MEMORY  (The Vault)  ← Private submodule                      │
│  github.com/mehdibadjian/mcp-evolution-vault                    │
│                                                                 │
│  dna/registry.json   ← Single source of truth for all skills   │
│  species/*.py        ← Living AI skill files (the genome)      │
└─────────────────────────────────────────────────────────────────┘
```

**The Brain is stateless. The Memory is stateful. The Host is autonomous.**
The separation is absolute — the Brain can be redeployed, upgraded, or swapped without touching a single species file.

---

## The Viral Lifecycle

Every new skill passes through three phases before it earns a place in the genome:

### Phase 1 — Inquiry
Before synthesising anything, the Brain checks whether a semantically equivalent skill already exists.

```python
# LeanKG Guard prevents gene duplication
# "excel_to_json" → detected as similar to "csv_parser" → suggest adaptation
match = check_semantic_similarity("excel_to_json", registry,
    description="Converts Excel rows to JSON objects")
# Returns: SemanticMatch(existing_skill='csv_parser', score=0.27,
#   suggestion='Consider adapting csv_parser instead...')
```

If a near-duplicate is detected, the pipeline halts and suggests adaptation. Gene duplication is evolution's waste — Darwin-MCP rejects it.

### Phase 2 — Infection (Sandbox)
New code runs in complete isolation: a temporary virtualenv at `/tmp/mutation_{timestamp}`, with its own pip, its own dependencies, and no access to the host environment.

```
/tmp/mutation_1745123456/
└── venv/
    ├── bin/pip        ← isolated pip (never touches system)
    ├── bin/python     ← isolated python
    └── lib/           ← dependencies quarantined here
```

After every mutation — success or failure — the **Lysosome** runs:
1. `pip cache purge` via the sandbox pip (reclaims `~/.cache/pip` space)
2. `shutil.rmtree` on the entire sandbox directory

On a $5 Droplet, disk usage stays flat across thousands of mutations.

### Phase 3 — Replication (Promotion)
Only code that passes all its tests is promoted to the genome:

```
request_evolution()
  │
  ├─ 1. Validate inputs
  ├─ 1b. Semantic similarity check (LeanKG Guard)
  ├─ 2. Resolve species/registry paths
  ├─ 3. Run pytest in sandbox → fail hard if any test fails
  │      └─ on failure: increment_failure_count(name)
  │         └─ at 3 failures: Council of Peers escalation
  ├─ 4. Write species file to memory/species/{name}.py
  ├─ 5. Atomic registry update (registry.json)
  ├─ 6. Dependency tracking + env rebuild
  ├─ 7. Git commit + push to private vault (atomic with registry)
  ├─ 8. Record invocation stats
  └─ 9. Emit notifications/tools/list_changed → IDE refreshes instantly
```

**No code enters the genome without passing its tests. No exceptions.**

---

## Sovereign Features

### 🧹 Lysosome — Automatic Garbage Collection
`brain/engine/sandbox.py` · commit `4cfe20a`

After every mutation, `Sandbox.cleanup()` calls `purge_pip_cache()` — running `pip cache purge` via the sandbox's own pip binary. Disk usage on the $5 Droplet remains flat regardless of mutation volume.

### 🔔 MCP-Compliant `notifications/tools/list_changed`
`brain/watcher/hot_reload.py` · commit `66692a9`

The Brain emits the official MCP notification format the moment a mutation succeeds:
```python
MCP_LIST_CHANGED = {"method": "notifications/tools/list_changed", "params": {}}
```
Connected IDEs (Cursor, Claude Desktop, VS Code) refresh their tool palette instantly — no reconnect required.

### 🔧 Resurrection — Self-Healing Crontab
`brain/scripts/sanity_check.sh` · commit `afdcd5f`

An hourly cron job performs three checks:
1. **Port 8000** — restarts `darwin.service` if the SSE server is unresponsive
2. **Stale `.git/index.lock` files** — removed silently after a crashed mid-mutation
3. **`git submodule update --remote`** — keeps the Brain in sync with the Vault

The system recovers from a mid-mutation power failure without manual SSH intervention.

```bash
# Install once
bash brain/scripts/install_cron.sh
```

### 🔬 LeanKG Guard — Gene Duplication Prevention
`brain/engine/inquiry.py` · commit `4e3fd05`

Before evolving any new skill, the Brain runs a two-pass semantic similarity check:
- **Pass 1** — difflib token ratio on skill names (threshold: 0.55)
- **Pass 2** — Jaccard coefficient on description word sets (threshold: 0.20)

If either pass detects a near-duplicate, evolution is blocked and the Host receives a suggestion to adapt the existing species. The algorithm is API-stable — drop in an embedding model later without touching `request_evolution`.

### 🤝 Council of Peers — Multi-Model Validation
`brain/engine/peer_review.py` · commit `97f6885`

After 3 consecutive failures for the same skill, the Brain escalates to a secondary LLM configured in `brain/config/meshnet.json`. The secondary model receives the failing code, tests, and error context, and returns a `fixed_code` + `explanation`. If no secondary model is configured, the system degrades gracefully.

```python
# Automatically triggered inside request_evolution() — no changes needed
# To configure: set base_url + api_key + model in brain/config/meshnet.json
```

### 🌐 Cloud-less AI Mode (Gemma 2b on Phone)
`brain/bridge/router.py` · `brain/middleware/json_validator.py`

Run a free, private AI assistant over NordVPN Meshnet with zero API costs:

| Component | Role |
|-----------|------|
| **Dynamic Tool Router** | `GET /sse?query=<text>` — TF-IDF scoring, returns top-3 tools. Prevents hallucination on small models. |
| **JSON Validator Middleware** | Catches malformed tool calls, returns `retry_hint` so Gemma 2b self-corrects. |
| **Flash Summarizer** | Compresses web pages to ≤400 tokens before Meshnet transmission. |
| **XML Reasoning Rails** | `<thought>/<call>/<answer>` system prompt enforces rigid syntax on small models. |
| **Golden Log** | 3 curated transcripts as few-shot context at session start. |

**→ [Meshnet Setup Guide](docs/how-to/meshnet-setup.md)**

### 🛡️ Three-Layer Biosafety
| Level | Component | Protection |
|-------|-----------|-----------|
| **BSL-1** | `brain/engine/deps.py` | Dependency isolation — each mutation gets its own `requirements.txt` scope |
| **BSL-2** | `brain/engine/guard.py` | Circuit breaker — recursion depth ≤3, CPU ≤80%, RAM ≤256 MB, Toxic flag |
| **BSL-3** | `brain/engine/mutator.py` | Contextualized error reporting — file + line + assertion detail in every failure |

---

## Quick Start

### Prerequisites
- Python 3.9+
- Git with SSH key configured for the private Memory submodule
- $5 Droplet or local machine

### 1. Clone & Initialize

```bash
git clone https://github.com/mehdibadjian/Darwin-MCP.git
cd Darwin-MCP
git submodule update --init --recursive
pip install -r brain/requirements.txt
```

### 2. Configure

```bash
# Required
export MCP_BEARER_TOKEN="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
export GIT_SSH_COMMAND="ssh -i ~/.ssh/id_rsa"

# Optional — enables Brave Search species and cloud-less mode
export BRAVE_API_KEY="your-brave-api-key"
```

### 3. Start the Brain

```bash
# Development (hot-reload)
uvicorn brain.bridge.sse_server:app --reload --host 0.0.0.0 --port 8000

# Production (systemd — see Production Deployment below)
sudo systemctl start darwin
```

### 4. Connect Your LLM

```json
// Cursor / Claude Desktop — settings.json
{
  "mcpServers": {
    "darwin-brain": {
      "url": "https://brain.yourdomain.com/sse",
      "headers": { "Authorization": "Bearer <your-token>" }
    }
  }
}
```

### 5. Evolve Your First Skill

```python
from brain.engine.mutator import request_evolution

result = request_evolution(
    name="double_it",
    code="def double_it(x): return x * 2",
    tests="def test_double(): assert double_it(5) == 10",
    requirements=[],
    description="Multiplies a number by two",
    git_commit=True,
)
print(result.message)
# → "Skill 'double_it' evolved successfully at version 1"
# Connected IDEs refresh their tool list automatically.
```

---

## Production Deployment

### Step 1 — Install Nginx & Certbot

```bash
sudo apt update && sudo apt install -y nginx certbot python3-certbot-nginx
```

### Step 2 — Configure Reverse Proxy

```bash
sudo cp brain/config/nginx.conf.template /etc/nginx/sites-available/darwin-mcp
sudo sed -i 's/DOMAIN_NAME/brain.yourdomain.com/g' /etc/nginx/sites-available/darwin-mcp
sudo ln -s /etc/nginx/sites-available/darwin-mcp /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### Step 3 — SSL Certificate

```bash
sudo certbot --nginx -d brain.yourdomain.com
# Auto-renewal is managed by Certbot's systemd timer.
```

### Step 4 — Harden the Bearer Token

```bash
# Generate and store — never hardcode
echo "MCP_BEARER_TOKEN=$(python3 -c 'import secrets; print(secrets.token_hex(32))')" \
  | sudo tee /opt/mcp-evolution-core/.env
sudo chmod 600 /opt/mcp-evolution-core/.env
```

### Step 5 — Install Systemd Service

```bash
sudo cp darwin.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now darwin
sudo journalctl -u darwin -f
```

### Step 6 — Self-Healing Crontab

```bash
sudo -u darwin bash brain/scripts/install_cron.sh
# Runs sanity_check.sh hourly: port check + lock cleanup + submodule sync
```

### Step 7 — Firewall

```bash
sudo ufw allow 22 && sudo ufw allow 80 && sudo ufw allow 443
sudo ufw deny 8000   # port 8000 never exposed directly — Nginx only
sudo ufw enable
```

**→ [Full Deployment Hardening Guide](docs/how-to/deployment-hardening.md)**

---

## Architecture Reference

| Component | File | Role |
|-----------|------|------|
| **Membrane** | `brain/bridge/sse_server.py` | SSE transport, Bearer auth, MCP protocol, vault routing |
| **Tool Router** | `brain/bridge/router.py` | TF-IDF query→tool scoring, top-N filtering |
| **Ribosome** | `brain/engine/mutator.py` | Full mutation pipeline orchestration |
| **Lysosome** | `brain/engine/sandbox.py` | Isolated virtualenv + post-mutation pip cache purge |
| **Circuit Breaker** | `brain/engine/guard.py` | Recursion depth, CPU/RAM limits, Toxic flag |
| **LeanKG Guard** | `brain/engine/inquiry.py` | Semantic similarity — blocks gene duplication |
| **Council of Peers** | `brain/engine/peer_review.py` | Multi-model fallback after 3 failures |
| **JSON Middleware** | `brain/middleware/json_validator.py` | Self-healing malformed JSON with retry hints |
| **Flash Summarizer** | `brain/utils/context_buffer.py` | Extractive ≤400-token compression |
| **Registry I/O** | `brain/utils/registry.py` | Atomic read/write of `registry.json` with file locking |
| **Git Manager** | `brain/utils/git_manager.py` | Commit, push, rebase; atomic with registry write |
| **Hot Reload** | `brain/watcher/hot_reload.py` | Watchdog + MCP `notifications/tools/list_changed` |
| **Resurrection** | `brain/scripts/sanity_check.sh` | Hourly: port check, lock cleanup, submodule sync |
| **Nginx Template** | `brain/config/nginx.conf.template` | Production reverse proxy with SSL + SSE headers |

---

## Common Commands

```bash
# Run the full test suite
pytest tests/ -q
# → 298 passed, 2 skipped

# Evolve a skill via the REST API
curl -X POST https://brain.yourdomain.com/evolve \
  -H "Authorization: Bearer $MCP_BEARER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"add","code":"def add(a,b): return a+b","tests":"def test(): assert add(2,3)==5","requirements":[]}'

# Query tools by relevance (cloud-less routing)
curl -H "Authorization: Bearer $MCP_BEARER_TOKEN" \
  "https://brain.yourdomain.com/sse?query=search+the+web"

# Web search via Brain
curl -X POST https://brain.yourdomain.com/search \
  -H "Authorization: Bearer $MCP_BEARER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "latest Python release", "fetch": true}'

# View the genome
cat memory/dna/registry.json | jq '.skills | keys'

# Check Droplet vitals
curl https://brain.yourdomain.com/tools/get_droplet_vitals/invoke \
  -H "Authorization: Bearer $MCP_BEARER_TOKEN"
```

---

## Directory Structure

```
Darwin-MCP/
├── brain/
│   ├── bridge/
│   │   ├── sse_server.py          ← Membrane: SSE + auth + vault routing
│   │   └── router.py              ← Dynamic Tool Router
│   ├── config/
│   │   ├── meshnet.json           ← Meshnet / Council of Peers config
│   │   └── nginx.conf.template    ← Production Nginx template
│   ├── engine/
│   │   ├── mutator.py             ← Full mutation pipeline
│   │   ├── sandbox.py             ← Lysosome: isolated venv + cache purge
│   │   ├── guard.py               ← Circuit breaker (BSL-2)
│   │   ├── inquiry.py             ← LeanKG Guard: semantic similarity
│   │   ├── peer_review.py         ← Council of Peers: multi-model fallback
│   │   ├── scavenger.py           ← External skill harvesting
│   │   ├── vitals.py              ← Droplet metrics MCP tool
│   │   ├── pytest_runner.py       ← Sandboxed test execution
│   │   └── deps.py                ← Dependency tracking (BSL-1)
│   ├── middleware/
│   │   └── json_validator.py      ← Self-healing JSON (BSL-3)
│   ├── prompts/
│   │   ├── system_prompt.txt      ← XML reasoning rails (cloud-less)
│   │   └── golden_log.txt         ← Few-shot primer (cloud-less)
│   ├── scripts/
│   │   ├── sanity_check.sh        ← Resurrection: hourly health monitor
│   │   └── install_cron.sh        ← Crontab installer
│   ├── utils/
│   │   ├── registry.py            ← Atomic registry I/O
│   │   ├── git_manager.py         ← Git state machine
│   │   ├── web_fetch.py           ← HTTP fetch + DuckDuckGo search
│   │   └── context_buffer.py      ← Flash Summarizer
│   └── watcher/
│       └── hot_reload.py          ← Watchdog + MCP list_changed
├── memory/                         ← Git submodule (private vault)
│   ├── dna/registry.json           ← The genome index
│   └── species/*.py                ← Living skill files
├── docs/
│   ├── reference/
│   │   ├── technical-manifesto.md
│   │   ├── agile-backlog.md
│   │   └── hardening-backlog.md
│   ├── tutorials/getting-started.md
│   └── how-to/
│       ├── common-tasks.md
│       ├── meshnet-setup.md
│       └── deployment-hardening.md
├── tests/                           ← pytest suite (298 passing)
├── darwin.service                   ← Systemd unit (uvicorn + hardening)
└── CONTRIBUTING.md
```

---

## Documentation

| Document | Purpose |
|----------|---------|
| **[Getting Started](docs/tutorials/getting-started.md)** | Local setup, first skill, verify install |
| **[Common Tasks](docs/how-to/common-tasks.md)** | Create, debug, deploy, rollback skills |
| **[Deployment Hardening](docs/how-to/deployment-hardening.md)** | Nginx, SSL, bearer token, UFW, crontab |
| **[Meshnet Setup](docs/how-to/meshnet-setup.md)** | NordVPN Meshnet + Gemma 2b on phone |
| **[Technical Manifesto](docs/reference/technical-manifesto.md)** | API contracts, Git state machine, BSL layers |
| **[Hardening Backlog](docs/reference/hardening-backlog.md)** | Security epics, user stories, sprint plans |
| **[Agile Backlog](docs/reference/agile-backlog.md)** | Full feature backlog and story points |
| **[CONTRIBUTING](CONTRIBUTING.md)** | Contribution model, mutation standards, branching |

---

## Support

- **Issues** — [github.com/mehdibadjian/Darwin-MCP/issues](https://github.com/mehdibadjian/Darwin-MCP/issues)
- **Discussions** — [github.com/mehdibadjian/Darwin-MCP/discussions](https://github.com/mehdibadjian/Darwin-MCP/discussions)

---

## License

TBD

---

*The genome is open. Evolve responsibly.* 🧬
