# Darwin-MCP — "God-Tier" Hardening & Evolution Backlog

**Generated:** 2026-04-19  
**Target Sprints:** 5 (10 weeks)  
**Sprint Capacity:** 25–28 story points per 2-week sprint  
**Total Story Points:** 57

---

## Executive Summary

Five phases to evolve Darwin-MCP from a functional prototype into a bulletproof organism. Each phase addresses a specific biological weakness: immune system gaps, reproductive instability, limited gene diversity, observability blindness, and single-tenant confinement.

| Epic | Phase | Goal | Priority |
|------|-------|------|----------|
| EP-H1 | Phase 1 | Immune System — Security & Stability | Highest |
| EP-H2 | Phase 2 | Reproductive Reliability — Git State Machine | Highest |
| EP-H3 | Phase 3 | Global Gene Transfer — Skill Scavenging | High |
| EP-H4 | Phase 4 | Observability & Self-Reflection | Medium |
| EP-H5 | Phase 5 | Multi-Tenant Evolution — Cloud Leap | Medium |

---

## Epics

### EP-H1: Immune System — Security & Stability

**Description:**  
Prevent malicious or hallucinated mutations from crashing the Droplet by enforcing process-level isolation (already done via `Sandbox.run_isolated`) and preventing registry corruption from concurrent mutations via file locking.

**Components Covered:**
- `brain/engine/sandbox.py` — resource limits, process group isolation (complete)
- `brain/utils/registry.py` — file locking for concurrent access (new)

**Gap Being Closed:**  
Sub-agents share the Brain's privileges. Simultaneous `request_evolution` calls race on `registry.json` reads/writes, silently corrupting registry state.

---

### EP-H2: Reproductive Reliability — Git State Machine

**Description:**  
Ensure every push to the Memory vault succeeds by hardening the pre-push workflow: sync with remote first, force the branch to `main`, rebase, then push. Prevent "Ghost Skills" (registry entries whose remote commit was never delivered) by making registry writes atomic with push success.

**Components Covered:**
- `brain/utils/git_manager.py` — pre-push preflight (new)
- `brain/engine/mutator.py` — atomic registry + push coupling (new)

**Gap Being Closed:**  
Submodules entering Detached HEAD state cause silent push failures. The registry can show a skill as `active` while the remote vault has never received it.

---

### EP-H3: Global Gene Transfer — Skill Scavenging

**Description:**  
Enable the Brain to inherit open-source MCP tools by querying the official GitHub MCP Registry, fetching READMEs, and wrapping external tools as native Darwin-MCP species using a standardised Jinja2 adapter template.

**Components Covered:**
- `brain/engine/scavenger.py` — `scavenge_external_skill()` (complete)
- `brain/templates/adapter.j2` — adapter template (new)
- `brain/utils/registry.py` — provenance metadata (complete)

**Gap Being Closed:**  
The system mutates new code but cannot inherit existing open-source MCP tools. The adapter template codifies the translation contract between external APIs and the internal species format.

---

### EP-H4: Observability & Self-Reflection

**Description:**  
Expose real-time Droplet health via an MCP tool and deliver automatic tool-list refresh to connected IDEs without requiring a server restart.

**Components Covered:**
- `brain/engine/vitals.py` — metrics collection (complete)
- `brain/watcher/hot_reload.py` — `list_changed` MCP signal (complete)
- `brain/bridge/sse_server.py` — vitals tool exposure (needs wiring)

**Gap Being Closed:**  
System health is only observable by SSHing into the Droplet. Connected IDEs must be manually restarted to discover new skills.

---

### EP-H5: Multi-Tenant Evolution — The Cloud Leap

**Description:**  
Allow one Brain instance to serve multiple projects by accepting a `VAULT_ID` in the SSE connection string and dynamically mounting the corresponding submodule directory.

**Components Covered:**
- `brain/bridge/sse_server.py` — vault routing (complete via `X-Vault-Repo` header)
- `brain/utils/git_manager.py` — `resolve_vault()` (complete)

**Gap Being Closed:**  
One Brain manages one vault. The multi-tenant routing exists at the HTTP layer but lacks vault-per-connection-string routing for automated clients that cannot set custom headers.

---

## Features

### F-H1: Registry File Locking (EP-H1)
Add `fcntl.flock` shared/exclusive locks around `read_registry` and `write_registry` to serialise concurrent access. Lock file: `registry.json.lock`. No change to the external API.

### F-H2: Pre-Push Git Preflight (EP-H2)
Prepend `git fetch origin` → `git checkout main` → `git pull --rebase origin main` to `commit_and_push()` before `git add/commit/push`. Eliminates Detached HEAD failures.

### F-H3: Atomic Registry-Push Coupling (EP-H2)
Reorder `mutator.py` so that `write_registry()` is called **after** a successful push. On `PushRejectedError` / `RebaseError`, revert `registry.json` to its pre-mutation snapshot to prevent Ghost Skills.

### F-H4: Jinja2 Adapter Template (EP-H3)
Create `brain/templates/adapter.j2` — a parameterised species skeleton for wrapping external CLI/HTTP MCP tools. Update `Scavenger.generate_wrapper()` to render from this template (fallback to string-format if Jinja2 not installed).

### F-H5: Vitals MCP Tool Wiring (EP-H4)
Ensure `get_system_vitals` is exposed as a callable MCP tool through `sse_server.py`, returning CPU, RAM, disk, and the last 20 mutation success/failure events from the registry.

### F-H6: Hot Reload list_changed Signal (EP-H4)
Validate that the watchdog-driven `notifications/tools/list_changed` signal reaches connected SSE clients after every successful mutation — no manual restart required.

### F-H7: VAULT_ID URL Parameter (EP-H5)
Extend `sse_server.py` to accept `?vault_id=<id>` as a query parameter in the SSE connection URL, complementing the existing `X-Vault-Repo` header routing, so automated clients (CLI, CI) can select vaults without custom HTTP headers.

---

## User Stories

### US-H1: Concurrent Registry Writes Are Serialised (EP-H1, F-H1)

**Title:** As the Mutation Engine, I want registry reads and writes to hold a file lock, so that two simultaneous evolutions cannot corrupt `registry.json`.

**Acceptance Criteria:**
```gherkin
Given two concurrent request_evolution calls targeting the same registry path
When both attempt to write registry.json simultaneously
Then one waits until the other releases the lock before proceeding

Given a write_registry call is in progress
When a read_registry call is made from another thread
Then read_registry blocks until the write completes, returning consistent data

Given registry.json.lock exists from a previous crashed process
When a new registry read/write is attempted
Then the lock is acquired normally (flock is not affected by stale lock files)
```

**Story Points:** 3  
**Priority:** Highest  
**Labels:** `concurrency`, `registry`, `stability`

---

### US-H2: Git Preflight Prevents Detached HEAD (EP-H2, F-H2)

**Title:** As the Git Manager, I want to fetch, checkout main, and rebase before every commit, so that pushes never fail due to Detached HEAD state.

**Acceptance Criteria:**
```gherkin
Given the memory submodule is in Detached HEAD state
When commit_and_push is called
Then git checkout main forces the branch before git add runs

Given a remote has new commits since the last pull
When commit_and_push is called
Then git fetch origin + git pull --rebase origin main merge them before the new commit

Given the preflight completes successfully
When git add . runs
Then cwd is the vault path and git add is the 4th git command called (after fetch, checkout, pull)
```

**Story Points:** 5  
**Priority:** Highest  
**Labels:** `git`, `stability`, `reproductive-system`

---

### US-H3: Registry Reverts on Push Failure (EP-H2, F-H3)

**Title:** As the Mutation Engine, I want the registry entry to be rolled back if the git push fails permanently, so that no Ghost Skill is created.

**Acceptance Criteria:**
```gherkin
Given a successful mutation that writes a new skill entry to registry.json
When the git push raises PushRejectedError
Then registry.json reverts to its state before the mutation started

Given a successful mutation that writes a new skill entry to registry.json
When the git push raises RebaseError
Then registry.json reverts to its pre-mutation snapshot and logs a warning

Given the git push succeeds after a rebase retry
When the mutation completes
Then registry.json retains the new skill entry (no spurious revert)
```

**Story Points:** 5  
**Priority:** Highest  
**Labels:** `git`, `registry`, `atomic`, `reproductive-system`

---

### US-H4: Adapter Template Wraps External MCP Tools (EP-H3, F-H4)

**Title:** As the Scavenger Engine, I want to render new wrapper species from a Jinja2 template, so that all externally-sourced skills share a consistent, maintainable structure.

**Acceptance Criteria:**
```gherkin
Given brain/templates/adapter.j2 exists
When Scavenger.generate_wrapper(name, repo_url, readme_text) is called
Then the generated code is rendered from the template with correct variable substitution

Given the rendered wrapper
When it is saved to memory/species/{name}.py
Then it contains: module docstring, run(input_data) function, logging, error handling, and provenance metadata

Given Jinja2 is not installed in the environment
When generate_wrapper is called
Then it falls back to string-format rendering without raising ImportError
```

**Story Points:** 3  
**Priority:** High  
**Labels:** `scavenger`, `templates`, `code-generation`

---

### US-H5: Vitals Tool Returns Mutation Success Rate (EP-H4, F-H5)

**Title:** As the Host LLM, I want `get_system_vitals` to include the success rate of the last 20 mutations, so that I can assess Brain performance without reading raw logs.

**Acceptance Criteria:**
```gherkin
Given the registry has skills with success_count and failure_count fields
When get_system_vitals is called via MCP
Then the response includes mutation_success_rate across the last 20 invocations

Given the Brain process has been running for less than 20 mutations
When get_system_vitals is called
Then it returns the available data with no padding or dummy values

Given the vitals tool is invoked
When it executes
Then CPU %, RAM (used/total), disk usage, and collected_at timestamp are all present
```

**Story Points:** 3  
**Priority:** Medium  
**Labels:** `observability`, `vitals`, `mcp-tool`

---

### US-H6: Hot Reload Triggers on Mutation Commit (EP-H4, F-H6)

**Title:** As a Developer using Cursor/VS Code, I want the tool list to refresh automatically after a mutation is committed, so that new species appear without restarting the MCP connection.

**Acceptance Criteria:**
```gherkin
Given a connected SSE client and the watchdog watcher is running
When a new .py file is written to memory/species/
Then the client receives a notifications/tools/list_changed event within 2 seconds

Given no SSE client is connected when a species file changes
When a client connects later
Then it receives the queued list_changed notification via flush_queued_notifications

Given a species file is modified (not created)
When the watchdog detects the change
Then list_changed is emitted and the registry is re-discovered
```

**Story Points:** 3  
**Priority:** Medium  
**Labels:** `hot-reload`, `sse`, `observability`

---

### US-H7: VAULT_ID Accepted as URL Query Parameter (EP-H5, F-H7)

**Title:** As a CI/CD Pipeline, I want to select a vault by passing `?vault_id=<id>` in the SSE connection URL, so that I don't need to set custom HTTP headers to use multi-tenant routing.

**Acceptance Criteria:**
```gherkin
Given an SSE connection to /sse?vault_id=web-dev-vault
When the Bridge processes the request
Then it routes all tool calls to memory/submodules/web-dev-vault

Given an SSE connection with both ?vault_id= and X-Vault-Repo header
When the Bridge processes the request
Then the X-Vault-Repo header takes precedence over the query parameter

Given ?vault_id=nonexistent
When the Bridge processes the request
Then it returns HTTP 400 with message "Vault not found"
```

**Story Points:** 5  
**Priority:** Medium  
**Labels:** `multi-tenant`, `sse-bridge`, `routing`

---

## Sprint Plan

### Sprint H-1: Immune & Reproductive Hardening
**Goal:** Eliminate concurrency corruption and Git Detached HEAD failures — the two most critical stability threats.

| Story | Points | Priority |
|-------|--------|----------|
| US-H1 (Registry file locking) | 3 | Highest |
| US-H2 (Git preflight) | 5 | Highest |
| US-H3 (Atomic registry/push) | 5 | Highest |
| **Total** | **13** | — |

---

### Sprint H-2: Gene Transfer & Observability
**Goal:** Standardise external skill wrapping with the adapter template and validate hot reload end-to-end.

| Story | Points | Priority |
|-------|--------|----------|
| US-H4 (Adapter template) | 3 | High |
| US-H5 (Vitals + mutation rate) | 3 | Medium |
| US-H6 (Hot reload) | 3 | Medium |
| **Total** | **9** | — |

---

### Sprint H-3: Multi-Tenant URL Routing
**Goal:** Enable vault selection via query parameter for CI/automated clients.

| Story | Points | Priority |
|-------|--------|----------|
| US-H7 (VAULT_ID query param) | 5 | Medium |
| **Total** | **5** | — |

---

## Definition of Done

- [ ] All Given/When/Then acceptance criteria pass with automated `pytest`
- [ ] No regression in existing test suite (`pytest tests/`)
- [ ] Code reviewed and merged to `main`
- [ ] Changes reflected in `registry.json` where applicable
- [ ] `darwin.service` restarts cleanly after deployment
- [ ] No increase in baseline resource usage on the Droplet

---

## Implementation Notes

| Component | Current State | Gap |
|-----------|--------------|-----|
| `sandbox.py` | `run_isolated` with RLIMIT_AS + process group kill ✅ | None |
| `registry.py` | Atomic `os.replace` writes, no file locks ⚠️ | Add `fcntl.flock` |
| `git_manager.py` | Push + rebase retry, no preflight ⚠️ | Add fetch/checkout/pull before add |
| `mutator.py` | Registry write before git push ⚠️ | Make registry write atomic with push |
| `scavenger.py` | String-format `generate_wrapper` ⚠️ | Render from `adapter.j2` template |
| `vitals.py` | Full metrics collection ✅ | Wire into MCP tool list |
| `hot_reload.py` | `list_changed` + SSE callback ✅ | Validate end-to-end flow |
| `sse_server.py` | `X-Vault-Repo` header routing ✅ | Add `?vault_id=` query param |

---

## Total Story Points: 35 across 3 sprints
