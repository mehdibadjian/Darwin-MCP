# Darwin-MCP Enhancement Backlog

**Generated:** 2026-04-18  
**Target Sprints:** 5 (10 weeks)  
**Sprint Capacity:** 30–35 story points per sprint

---

## Executive Summary

Five major enhancements to harden the Darwin-MCP Brain against resource exhaustion, expand capability discovery, automate skill hygiene, support multi-tenant deployment, and expose system observability.

| Epic | Goal | Priority |
|------|------|----------|
| EP-1 | Immune System (Resource Isolation) | Highest |
| EP-2 | Horizontal Gene Transfer (Skill Scavenging) | High |
| EP-3 | Darwinian Pruning (Skill Senescence) | High |
| EP-4 | Multi-Tenant Vaults | Medium |
| EP-5 | Self-Reflective Bridge (Observability) | Medium |

---

## Epics

### EP-1: Immune System — Process Sandboxing & Resource Isolation

**Description:**  
Prevent malicious or resource-heavy mutations from crashing the $5 Droplet by isolating the validation phase in a sandboxed process with strict resource limits.

**Components Covered:**  
- `brain/engine/sandbox.py`
- `brain/engine/guard.py`
- `brain/engine/pytest_runner.py`
- `brain/engine/mutator.py`

**Success Criteria:**  
- Infinite-loop mutations killed after 2 seconds without affecting SSE server
- Resource limits enforced: CPU, memory, disk I/O, file handles
- Validation runs isolated from the Brain process

---

### EP-2: Horizontal Gene Transfer — Global Skill Scavenger

**Description:**  
Enable the Brain to discover and integrate open-source MCP servers from the official registry, automatically wrapping them as native species without manual reimplementation.

**Components Covered:**  
- `brain/engine/scavenger.py` (new)
- `memory/species/` (wrapper species)
- `brain/utils/registry.py`

**Success Criteria:**  
- Query official MCP server registry via GitHub
- Fetch and parse README for external MCP servers
- Generate wrapper species that translate external APIs to internal format
- Wrapper species committed to vault with provenance metadata

---

### EP-3: Darwinian Pruning — Skill Senescence & Garbage Collection

**Description:**  
Automatically remove low-performing and stale skills from the registry to prevent context bloom and keep the tool list lean and high-quality.

**Components Covered:**  
- `memory/dna/registry.json`
- `brain/engine/pruner.py` (new)
- `brain/watcher/hot_reload.py`

**Success Criteria:**  
- Skills tracked with `last_used_at` and `total_calls` fields
- Senescence policy applied: success_rate < 50% or unused > 30 days
- Stale skills archived to `memory/archive/` automatically
- Registry remains lean without manual curation

---

### EP-4: Multi-Tenant Vaults — Dynamic Vault Switching

**Description:**  
Allow a single Brain instance to serve multiple Projects by dynamically switching between different vault submodules based on request headers or parameters.

**Components Covered:**  
- `brain/bridge/sse_server.py`
- `brain/utils/git_manager.py`
- `brain/engine/mutator.py`

**Success Criteria:**  
- SSE Bridge accepts `X-Vault-Repo` header or URL parameter
- Brain dynamically mounts different submodule paths for Memory/Registry
- Each vault maintains isolated skill registry and evolution state
- Same Droplet serves multiple projects with separate skill ecosystems

---

### EP-5: Self-Reflective Bridge — System Vitals & Observability

**Description:**  
Expose a native MCP tool that allows the Host LLM to query Droplet health (CPU, RAM, disk, evolution logs), enabling proactive monitoring and health diagnostics.

**Components Covered:**  
- `brain/engine/vitals.py` (new)
- `brain/bridge/sse_server.py`
- `memory/dna/registry.json`

**Success Criteria:**  
- Vitals tool returns real-time CPU, RAM, disk usage
- Last 10 lines of evolution.log exposed
- Tool callable via standard MCP protocol
- Host LLM can assess Droplet health and diagnose issues

---

## Features

### F-1: nsjail Sandbox Integration (EP-1)

**Description:**  
Integrate a lightweight jail (nsjail or Docker) for pytest validation to prevent infinite loops and resource exhaustion.

**Definition of Ready:**
- nsjail or minimal Docker container selected and validated on Ubuntu 22.04
- Resource limit benchmarks (CPU, RAM, timeout) documented

---

### F-2: CPU & Memory Guard Rails (EP-1)

**Description:**  
Implement strict resource limits in the sandbox with configurable cgroup constraints and process tree cleanup on timeout.

**Definition of Ready:**
- Guard module enhanced with sandbox-specific limits
- Circuit breaker tests passing

---

### F-3: MCP Server Registry Fetcher (EP-2)

**Description:**  
Build a Scavenger tool that queries the official MCP Registry and extracts server metadata and README content.

**Definition of Ready:**
- Registry API endpoint identified and documented
- GitHub web_fetch capability tested against live registry

---

### F-4: Wrapper Species Generator (EP-2)

**Description:**  
Use the Host LLM to auto-generate a wrapper species that translates external MCP server APIs to internal species format.

**Definition of Ready:**
- LLM prompt template for wrapper generation designed
- Generated wrapper template validated with a test MCP server

---

### F-5: Skill Senescence Tracking (EP-3)

**Description:**  
Extend registry.json schema to track `last_used_at`, `total_calls`, and compute rolling `success_rate`.

**Definition of Ready:**
- Registry schema updated with new fields
- Registry read/write operations backward compatible

---

### F-6: Automated Skill Pruning (EP-3)

**Description:**  
Implement a pruner module that evaluates senescence policy and moves stale skills to archive on a schedule.

**Definition of Ready:**
- Pruning logic implemented with dry-run mode
- Archive directory structure created

---

### F-7: Vault Header Routing (EP-4)

**Description:**  
Modify the SSE Bridge to parse `X-Vault-Repo` header and route requests to the correct submodule mount point.

**Definition of Ready:**
- Header parsing logic implemented and tested
- Multi-vault request routing e2e tested

---

### F-8: Dynamic Git Submodule Mounting (EP-4)

**Description:**  
Extend GitManager to dynamically load and cache submodule paths based on vault identifier.

**Definition of Ready:**
- Git submodule caching implemented
- Submodule switching stress-tested with concurrent requests

---

### F-9: System Metrics Collection (EP-5)

**Description:**  
Create a vitals module that gathers CPU, RAM, disk, and process-level metrics from the Droplet.

**Definition of Ready:**
- psutil or equivalent library integrated
- Metrics collection latency < 100ms

---

### F-10: Vitals MCP Tool Registration (EP-5)

**Description:**  
Register the vitals collector as a native MCP tool in the Brain's registry.

**Definition of Ready:**
- Tool callable via standard MCP protocol
- Tool output schema documented and validated

---

## User Stories

### US-1: Validate Mutation in Isolated Sandbox (EP-1, F-1)

**Title:**  
As a Brain Administrator, I want pytest mutations to run in an isolated sandbox, so that an infinite loop doesn't crash the Droplet.

**Description:**  
The validation phase of `request_evolution` must be isolated from the host OS. nsjail or Docker container provides namespace isolation, preventing system resource access.

**Acceptance Criteria:**

```gherkin
Given a mutation with code: while True: pass
When the mutation is validated in the sandbox
Then it is killed after 2 seconds without affecting the SSE server

Given the sandbox is requested to allocate 10 GB of RAM
When the validation begins
Then the sandbox is killed and an error is logged, not the entire Brain

Given the sandbox is restricted to 1 CPU core
When a multi-threaded mutation runs
Then it is throttled to 1 core and times out cleanly
```

**Story Points:** 8  
**Priority:** Highest  
**Labels:** `infrastructure`, `security`, `resource-isolation`

---

### US-2: Configure Cgroup Resource Limits (EP-1, F-2)

**Title:**  
As a Security Engineer, I want resource limits enforced via cgroups (CPU, RAM, disk I/O, file handles), so that toxic mutations cannot consume host resources.

**Description:**  
The guard module must configure cgroups before launching the sandbox, with configurable limits and circuit-breaker enforcement.

**Acceptance Criteria:**

```gherkin
Given a configuration with max_cpu=1, max_memory=512MB, max_timeout=3s
When a mutation is validated
Then it respects these limits and fails gracefully if exceeded

Given a mutation that forks 100 child processes
When the file handle limit is set to 50
Then the mutation fails with a resource error, and child processes are cleaned up

Given the sandbox has been running for 5 seconds
When the timeout is 3 seconds
Then all processes in the sandbox are killed
```

**Story Points:** 5  
**Priority:** Highest  
**Labels:** `infrastructure`, `guard`, `testing`

---

### US-3: Query Official MCP Server Registry (EP-2, F-3)

**Title:**  
As a Scavenger Engine, I want to fetch and parse the official MCP Server Registry from GitHub, so that I can discover available open-source MCP servers.

**Description:**  
The Scavenger tool queries https://github.com/modelcontextprotocol/servers and extracts metadata (name, description, README) for each registered server.

**Acceptance Criteria:**

```gherkin
Given the MCP Server Registry is available at the official GitHub URL
When the Scavenger queries the registry
Then it returns a list of servers with name, repo URL, and README excerpt

Given a specific MCP server entry
When the Scavenger fetches its README
Then the README is parsed and cached in memory/temp/

Given the GitHub API rate limit is exceeded
When the Scavenger retries
Then it fails gracefully with a "rate limit exceeded" error
```

**Story Points:** 5  
**Priority:** High  
**Labels:** `scavenger`, `external-integration`, `discovery`

---

### US-4: Auto-Generate Wrapper Species from External MCP Server (EP-2, F-4)

**Title:**  
As the Mutator Engine, I want to generate a wrapper species that translates an external MCP server's API to our internal format, so that external tools work natively in the Brain.

**Description:**  
Given an external MCP server's README and API contract, the Host LLM generates a Python wrapper species that acts as a bridge between the external server and the internal species format.

**Acceptance Criteria:**

```gherkin
Given an external MCP server spec (e.g., Google Search via MCP)
When the Scavenger requests a wrapper species
Then the LLM generates a Python file that:
  - Calls the external MCP server's methods
  - Maps responses to internal species/inherited/ format
  - Includes docstrings and error handling

Given the generated wrapper species
When it is committed to memory/species/
Then it appears in the registry with source="external" and provenance metadata

Given a wrapper for an external tool
When the wrapper is invoked
Then it correctly translates input/output and logs the external API call
```

**Story Points:** 8  
**Priority:** High  
**Labels:** `scavenger`, `code-generation`, `integration`

---

### US-5: Extend Registry Schema with Senescence Fields (EP-3, F-5)

**Title:**  
As a Registry Manager, I want to track `last_used_at`, `total_calls`, and compute `success_rate` for each skill, so that the Pruner can identify stale and low-performing skills.

**Description:**  
The registry.json schema is extended with new fields and read/write operations are updated to maintain backward compatibility.

**Acceptance Criteria:**

```gherkin
Given an existing registry.json with 50 skills
When the schema is upgraded
Then all skills have default values for:
  - last_used_at: timestamp of upgrade
  - total_calls: 0
  - success_count: 0
  - failure_count: 0

Given a skill is invoked
When the mutation completes
Then last_used_at is updated and success/failure counts are incremented

Given a skill with success_count=7, failure_count=3
When success_rate is computed
Then success_rate = 7/10 = 0.7 (70%)
```

**Story Points:** 3  
**Priority:** High  
**Labels:** `registry`, `data-model`, `observability`

---

### US-6: Implement Skill Pruning Policy & Automation (EP-3, F-6)

**Title:**  
As a Curator, I want to automatically move skills to archive if success_rate < 50% or last_used_at > 30 days, so that the tool list stays lean and high-quality.

**Description:**  
A scheduled pruner evaluates every skill against the senescence policy, logs decisions, and moves stale skills to `memory/archive/`.

**Acceptance Criteria:**

```gherkin
Given a skill with success_rate = 0.4 (40%)
When the pruner runs
Then the skill is moved to memory/archive/ with a timestamp

Given a skill not used for 31 days
When the pruner runs
Then the skill is archived and a log entry is created

Given the pruner is in dry-run mode
When it evaluates skills
Then no skills are actually moved, only logged

Given 100 skills in the registry
When the pruner completes
Then the registry is reloaded and list_tools returns only active skills
```

**Story Points:** 5  
**Priority:** High  
**Labels:** `pruning`, `registry`, `maintenance`

---

### US-7: Parse X-Vault-Repo Header in SSE Bridge (EP-4, F-7)

**Title:**  
As a Multi-Tenant Operator, I want the SSE Bridge to route requests based on the `X-Vault-Repo` header, so that multiple projects can use the same Brain instance.

**Description:**  
The SSE server parses the X-Vault-Repo header, validates the vault identifier, and instructs downstream components to use the correct submodule mount.

**Acceptance Criteria:**

```gherkin
Given an SSE request with header X-Vault-Repo: web-dev-vault
When the Bridge receives the request
Then it extracts the vault identifier and caches it in the request context

Given a request without the X-Vault-Repo header
When the Bridge receives it
Then it defaults to the primary vault (memory/)

Given an invalid vault identifier
When the Bridge processes the request
Then it returns a 400 error with "Vault not found"

Given concurrent requests for different vaults
When they are processed
Then each request uses the correct vault path without interference
```

**Story Points:** 5  
**Priority:** Medium  
**Labels:** `multi-tenant`, `sse-bridge`, `routing`

---

### US-8: Dynamic Git Submodule Mounting in GitManager (EP-4, F-8)

**Title:**  
As the Git Manager, I want to dynamically mount submodules based on vault identifier, so that each vault maintains its own species registry and evolution state.

**Description:**  
GitManager extends its initialization to accept a vault identifier and mount the correct submodule path. Concurrent vault access is safe due to path isolation.

**Acceptance Criteria:**

```gherkin
Given vault identifiers "web-dev-vault" and "data-science-vault"
When GitManager is initialized with vault="web-dev-vault"
Then it mounts memory/submodules/web-dev-vault as the vault root

Given two concurrent mutations for different vaults
When both use GitManager operations (commit, fetch)
Then commits are isolated and do not interfere with each other

Given a vault submodule path that doesn't exist
When GitManager is initialized
Then it clones the submodule and caches the path

Given the cache has stale entries
When the cache is refreshed
Then submodule paths are re-validated and updated
```

**Story Points:** 8  
**Priority:** Medium  
**Labels:** `git`, `multi-tenant`, `submodules`

---

### US-9: Implement System Vitals Metrics Collection (EP-5, F-9)

**Title:**  
As an Observability Engineer, I want to collect CPU, RAM, disk, and process-level metrics from the Droplet, so that the Host LLM can assess system health.

**Description:**  
A vitals module uses psutil (or equivalent) to gather metrics synchronously with minimal latency. Metrics include host-level stats and Brain process details.

**Acceptance Criteria:**

```gherkin
Given the vitals module is imported
When metrics are collected
Then it returns in < 100ms and includes:
  - CPU usage (%)
  - Memory (used/total, %)
  - Disk (used/total, %, by mount point)
  - Process PID, CPU %, RSS, open files

Given the system is under load
When vitals are collected
Then metrics accurately reflect the current state

Given the system has multiple disks
When vitals are collected
Then disk metrics include all mounted partitions (/, /tmp, etc.)
```

**Story Points:** 5  
**Priority:** Medium  
**Labels:** `observability`, `metrics`, `infrastructure`

---

### US-10: Register Vitals Tool as Native MCP Tool (EP-5, F-10)

**Title:**  
As the Host LLM, I want to call a "get_droplet_vitals" MCP tool, so that I can query Droplet health and see the last 10 evolution log lines.

**Description:**  
The vitals collector is registered in registry.json as a native tool. The SSE bridge exposes it via standard MCP protocol. Tool invocation triggers `vitals.collect()` and formats output.

**Acceptance Criteria:**

```gherkin
Given the vitals tool is registered in the registry
When the Host LLM calls "get_droplet_vitals"
Then the tool returns:
  - CPU usage (%)
  - RAM (used/total, %)
  - Disk (used/total, %)
  - Last 10 lines of evolution.log
  - Timestamp

Given the tool is invoked
When it executes
Then the response is well-formed JSON with proper schema

Given the evolution.log has 5 lines
When the tool retrieves the last 10 lines
Then it returns all 5 lines (no padding)
```

**Story Points:** 5  
**Priority:** Medium  
**Labels:** `observability`, `mcp-tool`, `registry`

---

## Sprint Plan

### Sprint 1: Immune System Foundation (EP-1)
**Goal:** Harden the Brain against resource exhaustion via sandbox isolation and cgroup guards.

| Story | Points | Status |
|-------|--------|--------|
| US-1 | 8 | Ready |
| US-2 | 5 | Ready |
| **Total** | **13** | — |

---

### Sprint 2: Immune System Hardening & Scavenger Discovery (EP-1, EP-2)
**Goal:** Complete sandbox integration and build the MCP Registry discovery engine.

| Story | Points | Status |
|-------|--------|--------|
| US-3 | 5 | Ready |
| US-4 | 8 | Depends on US-3 |
| **Total** | **13** | — |

---

### Sprint 3: Scavenger Completion & Senescence Setup (EP-2, EP-3)
**Goal:** Finalize external MCP integration and establish skill tracking foundation.

| Story | Points | Status |
|-------|--------|--------|
| US-5 | 3 | Ready |
| US-6 | 5 | Depends on US-5 |
| **Total** | **8** | — |

---

### Sprint 4: Multi-Tenant & Observability Foundation (EP-4, EP-5)
**Goal:** Enable vault switching and begin health monitoring.

| Story | Points | Status |
|-------|--------|--------|
| US-7 | 5 | Ready |
| US-8 | 8 | Depends on US-7 |
| **Total** | **13** | — |

---

### Sprint 5: Observability Completion (EP-5)
**Goal:** Complete vitals tool and health reporting.

| Story | Points | Status |
|-------|--------|--------|
| US-9 | 5 | Ready |
| US-10 | 5 | Depends on US-9 |
| **Total** | **10** | — |

---

## Definition of Done

- [ ] All acceptance criteria (Given/When/Then) pass with automated pytest
- [ ] Code review approved and merged to `main`
- [ ] New species or tools registered in `registry.json` with metadata
- [ ] Mutation pipeline runs end-to-end in sandbox environment
- [ ] Systemd service (`darwin.service`) restarts cleanly after deployment
- [ ] Integration test covers the feature with Host LLM invocation
- [ ] Changes documented in `docs/how-to/common-tasks.md` if user-facing
- [ ] No increase in baseline resource usage (measured before/after)

---

## Dependencies & Risks

| Risk | Mitigation |
|------|-----------|
| nsjail/Docker overhead on $5 Droplet | Benchmark with simple mutations; may need resource tuning |
| MCP Registry URL changes or downtime | Graceful fallback; document expected API contract |
| Multi-vault concurrent access conflicts | Use path isolation + lock-free git operations where possible |
| Vitals metrics accuracy under high load | Validate metrics against system monitoring tools (top, free, etc.) |

---

## Success Metrics (KPIs)

| Metric | Target |
|--------|--------|
| Toxic mutation killed within 2s | ✓ 100% |
| Infinite-loop mutation doesn't crash Brain | ✓ 100% |
| Skill senescence pruning removes < 5% false positives | ✓ > 95% |
| Multi-tenant vault switching latency | < 50ms |
| Vitals collection latency | < 100ms |
| Registry size after pruning (for 200+ original skills) | < 100 active skills |

---

## Total Story Points: 58 points across 5 sprints

