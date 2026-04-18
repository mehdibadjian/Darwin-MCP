# Darwin-MCP — Agile Backlog

Generated from: [technical-manifesto.md](technical-manifesto.md)  
Generated at: 2026-04-18T00:00:00Z  
Total story points: **127**  
Sprints: **5** (2-week cadence, 25–28 pts/sprint)

---

## System Components (Step 0)

| Component | File | Description |
|-----------|------|-------------|
| SSE Bridge | `brain/bridge/sse_server.py` | Stateless MCP SSE server; Bearer Token auth; remote entry point for the Host LLM |
| Mutation Engine | `brain/engine/mutator.py` | Receives `request_evolution`; orchestrates sandboxed test execution and species promotion |
| Sandbox | `/tmp/mutation_{timestamp}` | Temporary restricted virtualenv for safe dependency install and pytest execution |
| Git Manager | `brain/utils/git_manager.py` | Git state machine scoped to `/memory`; commit, push, and pull-rebase on conflict |
| Genome Registry | `memory/dna/registry.json` | Single source of truth for all registered skills; read on every startup |
| Circuit Breaker | `brain/engine/guard.py` | BSL-2 guard: recursion depth limit, CPU/RAM kill switch, Toxic flag |
| Dependency Isolation | `memory/requirements.txt` | BSL-1: append-on-mutation, triggers env rebuild |
| Error Reporter | (inline) | BSL-3: file + line + assertion detail in every failure response |
| Hot Reload | `watchdog` / MCP `list_changed` | File watcher on `/memory/species`; emits `list_changed` on registry update |
| Systemd Service | `darwin.service` | Keeps the Brain alive across reboots and crashes on the $5 Droplet |

---

## Epics (Step 1)

```json
[
  {
    "id": "EP-1",
    "title": "SSE Bridge — Remote MCP Transport",
    "description": "Deliver a stateless, authenticated SSE server that exposes registered tools to the Host LLM over a persistent connection.",
    "components_covered": ["SSE Bridge"]
  },
  {
    "id": "EP-2",
    "title": "Mutation Engine — Viral Synthesis",
    "description": "Implement the request_evolution pipeline that accepts code, validates it in a sandbox, and promotes passing species to the Genome.",
    "components_covered": ["Mutation Engine", "Sandbox"]
  },
  {
    "id": "EP-3",
    "title": "Git Manager — Reproductive System",
    "description": "Provide a robust Git state machine that commits and pushes evolved species to the remote vault and resolves merge conflicts automatically.",
    "components_covered": ["Git Manager"]
  },
  {
    "id": "EP-4",
    "title": "Genome Registry — Single Source of Truth",
    "description": "Maintain a validated, atomically-written registry.json that is the authoritative index of all skills the Brain can invoke.",
    "components_covered": ["Genome Registry"]
  },
  {
    "id": "EP-5",
    "title": "Biosafety — Circuit Breaker & Guardrails",
    "description": "Enforce BSL-1 dependency isolation, BSL-2 recursion and resource limits, and BSL-3 contextualized error reporting across the mutation pipeline.",
    "components_covered": ["Circuit Breaker", "Dependency Isolation", "Error Reporter"]
  },
  {
    "id": "EP-6",
    "title": "Hot Reload — Tool Discovery Without Restart",
    "description": "Ensure the Host LLM sees newly evolved tools immediately after mutation without requiring an SSE server restart.",
    "components_covered": ["Hot Reload"]
  },
  {
    "id": "EP-7",
    "title": "Deployment — Systemd Service",
    "description": "Package the Brain as a systemd service so the organism self-resurrects on crash or reboot on the $5 Droplet.",
    "components_covered": ["Systemd Service"]
  }
]
```

---

## Features (Step 2)

```json
[
  { "id": "F-1",  "epic_id": "EP-1", "name": "Bearer Token Authentication",          "description": "Validate Bearer Token on every incoming SSE connection and reject unauthorized clients with HTTP 401." },
  { "id": "F-2",  "epic_id": "EP-1", "name": "Species Directory Discovery on Startup","description": "Walk /memory/species at server startup and register every .py file into registry.json before accepting connections." },
  { "id": "F-3",  "epic_id": "EP-1", "name": "Tool List Serving over SSE",            "description": "Serve the complete list of registered tools to the Host LLM upon SSE connection establishment." },
  { "id": "F-4",  "epic_id": "EP-2", "name": "request_evolution API Endpoint",        "description": "Accept name, code, tests, and requirements fields and orchestrate the full mutation pipeline." },
  { "id": "F-5",  "epic_id": "EP-2", "name": "Sandboxed Virtualenv and pip Install",  "description": "Create a temporary /tmp/mutation_{timestamp} directory with a restricted virtualenv and install declared requirements inside it." },
  { "id": "F-6",  "epic_id": "EP-2", "name": "pytest Execution and Result Evaluation","description": "Run the provided test suite inside the sandbox virtualenv and branch on exit code to promote or reject the mutation." },
  { "id": "F-7",  "epic_id": "EP-2", "name": "Species File Promotion to /memory",     "description": "Write validated code to /memory/species/{name}.py only after all tests pass." },
  { "id": "F-8",  "epic_id": "EP-3", "name": "Git Commit and Push for Evolved Species","description": "Execute git add, commit with a structured message, and push to origin main after a successful mutation." },
  { "id": "F-9",  "epic_id": "EP-3", "name": "Merge Conflict Resolution via Pull-Rebase","description": "Detect push rejection, run git pull --rebase, and retry the push once before surfacing an error." },
  { "id": "F-10", "epic_id": "EP-4", "name": "Registry Initialization and Bootstrap",  "description": "Create a valid empty registry.json on first run if the file is absent, using the canonical schema." },
  { "id": "F-11", "epic_id": "EP-4", "name": "Atomic Skill Registration",              "description": "Write new skill entries to registry.json atomically (write-to-temp, then rename) to prevent corruption on crash." },
  { "id": "F-12", "epic_id": "EP-4", "name": "Skill Lookup and Tool Loading",          "description": "Load all tool definitions exclusively from registry.json on startup so no unregistered tool can be invoked." },
  { "id": "F-13", "epic_id": "EP-5", "name": "BSL-1 Dependency Isolation",             "description": "Append new pip requirements to memory/requirements.txt after each successful mutation and trigger a local env rebuild." },
  { "id": "F-14", "epic_id": "EP-5", "name": "BSL-2 Circuit Breaker",                  "description": "Track mutation recursion depth; SIGKILL runaway subprocesses; open a GitHub Issue and halt at depth > 3." },
  { "id": "F-15", "epic_id": "EP-5", "name": "BSL-3 Contextualized Error Reporting",   "description": "Emit error messages that include file name, line number, and assertion detail on every mutation failure." },
  { "id": "F-16", "epic_id": "EP-6", "name": "Watchdog File Watcher on /memory/species","description": "Use watchdog to detect new or modified .py files in /memory/species and trigger registry re-registration." },
  { "id": "F-17", "epic_id": "EP-6", "name": "MCP list_changed Notification",          "description": "Emit an MCP list_changed notification to the Host LLM whenever the tool registry is updated." },
  { "id": "F-18", "epic_id": "EP-7", "name": "Systemd Unit File",                      "description": "Provide a darwin.service unit file that starts the Brain from its virtualenv with Restart=on-failure." },
  { "id": "F-19", "epic_id": "EP-7", "name": "Stateless Restart Resilience",           "description": "Ensure all Brain state is derived from registry.json on startup so a service restart loses no data." }
]
```

---

## User Stories (Step 3)

```json
[
  {
    "id": "US-1",
    "feature_id": "F-1",
    "title": "As a Host LLM, I want to authenticate via Bearer Token, so that only authorized clients can invoke tools.",
    "acceptance_criteria": [
      "Given a request with a valid Bearer Token When the SSE Bridge receives it Then the connection is accepted and the tool list is returned",
      "Given a request with an invalid Bearer Token When the SSE Bridge receives it Then the connection is rejected with HTTP 401",
      "Given a request with no Authorization header When the SSE Bridge receives it Then the connection is rejected with HTTP 401"
    ],
    "story_points": 5,
    "priority": "High",
    "labels": ["backend", "security"]
  },
  {
    "id": "US-2",
    "feature_id": "F-1",
    "title": "As a DevOps engineer, I want Bearer Token validation to use constant-time comparison, so that the Brain is not vulnerable to timing attacks.",
    "acceptance_criteria": [
      "Given token comparison logic When implemented Then it uses hmac.compare_digest or equivalent constant-time function",
      "Given an invalid token of any length When compared Then no timing difference is observable between valid and invalid comparisons",
      "Given the token source When configured Then it is read from an environment variable, never hardcoded"
    ],
    "story_points": 3,
    "priority": "High",
    "labels": ["backend", "security"]
  },
  {
    "id": "US-3",
    "feature_id": "F-2",
    "title": "As the Brain, I want to walk /memory/species on startup and register all .py files into registry.json, so that the Host sees all available tools immediately.",
    "acceptance_criteria": [
      "Given /memory/species contains 3 .py files When the SSE server starts Then all 3 are present in registry.json before the first connection is accepted",
      "Given a .py file that is already registered When the discovery scan runs Then its entry is not duplicated in registry.json",
      "Given /memory/species is empty When the SSE server starts Then the server starts successfully with an empty skills object in registry.json"
    ],
    "story_points": 5,
    "priority": "High",
    "labels": ["backend", "discovery"]
  },
  {
    "id": "US-4",
    "feature_id": "F-2",
    "title": "As a developer, I want the species discovery scan to be idempotent, so that repeated server restarts never produce duplicate registry entries.",
    "acceptance_criteria": [
      "Given registry.json already contains a skill entry When the discovery scan runs again for the same file Then the entry count for that skill remains 1",
      "Given a .py file whose content has changed When the discovery scan runs Then the existing registry entry is updated, not appended",
      "Given registry.json does not exist When the discovery scan runs Then it is created with the correct schema before entries are written"
    ],
    "story_points": 3,
    "priority": "Medium",
    "labels": ["backend", "discovery"]
  },
  {
    "id": "US-5",
    "feature_id": "F-3",
    "title": "As a Host LLM, I want to receive the full list of registered tools over SSE upon connection, so that I can invoke the correct tools by name.",
    "acceptance_criteria": [
      "Given a successful SSE connection When the Bridge sends the tool list Then all entries from registry.json are present in the response",
      "Given registry.json contains a skill marked as Toxic When the tool list is sent Then that skill is excluded from the response",
      "Given the SSE connection is established Then the tool list response is delivered within 2 seconds of connection"
    ],
    "story_points": 3,
    "priority": "High",
    "labels": ["backend", "api"]
  },
  {
    "id": "US-6",
    "feature_id": "F-4",
    "title": "As a Host LLM, I want to call request_evolution with name, code, tests, and requirements, so that I can create new skills at runtime.",
    "acceptance_criteria": [
      "Given a valid request_evolution payload When submitted Then the mutation pipeline executes and returns a success or failure result",
      "Given a payload with all required fields (name, code, tests, requirements) When processed Then no field defaults are assumed",
      "Given a successful mutation When complete Then a confirmation message with the skill name and version is returned to the Host"
    ],
    "story_points": 5,
    "priority": "Highest",
    "labels": ["backend", "api", "mutation"]
  },
  {
    "id": "US-7",
    "feature_id": "F-4",
    "title": "As a developer, I want request_evolution to validate all required fields before processing, so that malformed requests fail fast with a descriptive error.",
    "acceptance_criteria": [
      "Given a payload missing the 'name' field When request_evolution is called Then an error specifying 'name is required' is returned immediately",
      "Given a payload where 'code' is an empty string When request_evolution is called Then an error is returned before any file is written",
      "Given a payload where 'requirements' is not a list When request_evolution is called Then a type-validation error is returned"
    ],
    "story_points": 2,
    "priority": "High",
    "labels": ["backend", "validation"]
  },
  {
    "id": "US-8",
    "feature_id": "F-5",
    "title": "As the Mutation Engine, I want to create a temporary /tmp/mutation_{timestamp} directory with a restricted virtualenv, so that new dependencies cannot affect the host environment.",
    "acceptance_criteria": [
      "Given a new mutation request When the sandbox is created Then the directory is /tmp/mutation_{unix_timestamp} and contains an isolated virtualenv",
      "Given pip install runs in the sandbox When it completes Then the host system Python site-packages directory is unmodified",
      "Given a mutation that fails Then the /tmp/mutation_{timestamp} directory is cleaned up before the error is returned"
    ],
    "story_points": 8,
    "priority": "High",
    "labels": ["backend", "sandbox", "security"]
  },
  {
    "id": "US-9",
    "feature_id": "F-5",
    "title": "As a developer, I want pip install to run only within the restricted virtualenv, so that the Brain's system Python is never modified.",
    "acceptance_criteria": [
      "Given requirements are declared When pip install runs Then it targets the sandbox virtualenv's pip binary, not the system pip",
      "Given a requirement that fails to install When pip exits non-zero Then the mutation is aborted and the error is returned to the Host",
      "Given empty requirements list When the sandbox is created Then pip install is skipped entirely"
    ],
    "story_points": 3,
    "priority": "High",
    "labels": ["backend", "sandbox"]
  },
  {
    "id": "US-10",
    "feature_id": "F-6",
    "title": "As the Mutation Engine, I want to execute pytest on the provided tests and capture stdout/stderr, so that only passing code is promoted to /memory.",
    "acceptance_criteria": [
      "Given tests that pass When pytest runs in the sandbox Then exit code is 0 and promotion to /memory is triggered",
      "Given tests that fail When pytest runs in the sandbox Then exit code is non-zero, promotion is aborted, and stderr is captured",
      "Given a test file that contains a syntax error When pytest runs Then the error is returned without crashing the Mutation Engine"
    ],
    "story_points": 5,
    "priority": "Highest",
    "labels": ["backend", "testing", "mutation"]
  },
  {
    "id": "US-11",
    "feature_id": "F-6",
    "title": "As a Host LLM, I want to receive the full pytest stderr when tests fail, so that I can diagnose and fix the code.",
    "acceptance_criteria": [
      "Given tests fail When the result is returned Then the full pytest stderr output is included verbatim in the response payload",
      "Given pytest stderr exceeds 10,000 characters When truncated Then the last 10,000 characters are returned and truncation is indicated",
      "Given a test failure When the error is formatted Then it conforms to BSL-3: includes file, line number, and assertion detail"
    ],
    "story_points": 3,
    "priority": "High",
    "labels": ["backend", "error-reporting"]
  },
  {
    "id": "US-12",
    "feature_id": "F-7",
    "title": "As the Mutation Engine, I want to write validated code to /memory/species/{name}.py only after all tests pass, so that failing code never enters the Genome.",
    "acceptance_criteria": [
      "Given tests pass When promotion runs Then /memory/species/{name}.py is created with the exact code from the request payload",
      "Given tests fail When promotion is evaluated Then no file is written to /memory/species/",
      "Given a species file already exists with the same name When promotion runs Then the file is overwritten with the new version"
    ],
    "story_points": 3,
    "priority": "High",
    "labels": ["backend", "mutation"]
  },
  {
    "id": "US-13",
    "feature_id": "F-8",
    "title": "As the Git Manager, I want to execute git add, commit, and push after successful mutation, so that new species are persisted to the remote vault.",
    "acceptance_criteria": [
      "Given a species file has been written to /memory/species/ When the Git Manager runs Then git add . is executed from within the /memory directory",
      "Given git add succeeds When commit runs Then the commit message matches 'evolution: [name] v[version]'",
      "Given git commit succeeds When push runs Then git push origin main is attempted"
    ],
    "story_points": 5,
    "priority": "High",
    "labels": ["backend", "git"]
  },
  {
    "id": "US-14",
    "feature_id": "F-8",
    "title": "As a developer, I want commit messages to follow the format 'evolution: [name] v[version]', so that the vault's git history is self-documenting.",
    "acceptance_criteria": [
      "Given a skill named 'pdf_parser' at version 1 When committed Then the message is exactly 'evolution: pdf_parser v1'",
      "Given a skill is re-evolved with updated code When committed Then the version number is incremented in the commit message",
      "Given the commit message is constructed Then it uses only the skill name and version — no additional text"
    ],
    "story_points": 2,
    "priority": "Medium",
    "labels": ["backend", "git"]
  },
  {
    "id": "US-15",
    "feature_id": "F-9",
    "title": "As the Git Manager, I want to automatically git pull --rebase and retry push on rejection, so that concurrent mutations do not permanently block the pipeline.",
    "acceptance_criteria": [
      "Given git push is rejected by the remote When the Git Manager handles the rejection Then git pull --rebase is executed",
      "Given git pull --rebase succeeds When the retry push runs Then git push origin main is attempted a second time",
      "Given the retry push also fails When the error is handled Then the mutation is marked as failed and the error is surfaced to the Host LLM"
    ],
    "story_points": 5,
    "priority": "High",
    "labels": ["backend", "git", "resilience"]
  },
  {
    "id": "US-16",
    "feature_id": "F-9",
    "title": "As a developer, I want the Git Manager to surface a structured error when rebase fails, so that the Host LLM can understand the blockage and act.",
    "acceptance_criteria": [
      "Given git pull --rebase exits non-zero When the error is returned Then it includes the git stderr output",
      "Given a rebase failure When the state is restored Then git rebase --abort is called to leave /memory in a clean state",
      "Given a rebase failure is reported Then the message includes the word 'rebase' and the affected file names from git output"
    ],
    "story_points": 3,
    "priority": "Medium",
    "labels": ["backend", "git", "error-reporting"]
  },
  {
    "id": "US-17",
    "feature_id": "F-10",
    "title": "As the Brain, I want registry.json to be initialized with a valid schema on first run if absent, so that the system bootstraps cleanly.",
    "acceptance_criteria": [
      "Given registry.json does not exist When the SSE server starts Then it creates registry.json with organism_version, last_mutation, and an empty skills object",
      "Given registry.json exists and is valid When the SSE server starts Then the existing file is not overwritten",
      "Given the initialization path uses pathlib When written Then no hardcoded absolute paths appear in the code"
    ],
    "story_points": 3,
    "priority": "High",
    "labels": ["backend", "registry"]
  },
  {
    "id": "US-18",
    "feature_id": "F-10",
    "title": "As a developer, I want registry.json to be schema-validated on every read, so that corrupt files are caught before tool loading fails silently.",
    "acceptance_criteria": [
      "Given registry.json is missing the 'skills' key When read Then a descriptive SchemaError is raised before any tool loading proceeds",
      "Given registry.json contains valid JSON but invalid schema When read Then a descriptive error identifying the missing/invalid field is raised",
      "Given registry.json is valid When read Then no error is raised and skills are loaded normally"
    ],
    "story_points": 3,
    "priority": "Medium",
    "labels": ["backend", "registry", "validation"]
  },
  {
    "id": "US-19",
    "feature_id": "F-11",
    "title": "As the Mutation Engine, I want to write a complete skill entry to registry.json on successful mutation, so that the registry is always the single source of truth.",
    "acceptance_criteria": [
      "Given a mutation succeeds When the registry is updated Then the new entry contains path, entry_point, runtime, dependencies, evolved_at, and parent_request fields",
      "Given the entry is written When validated Then all required fields from the registry schema are present and non-null",
      "Given the same skill name is evolved again When the registry is updated Then the existing entry is replaced, not duplicated"
    ],
    "story_points": 5,
    "priority": "Highest",
    "labels": ["backend", "registry", "mutation"]
  },
  {
    "id": "US-20",
    "feature_id": "F-11",
    "title": "As a developer, I want registry.json writes to be atomic, so that a crash mid-write cannot leave the registry in a corrupt state.",
    "acceptance_criteria": [
      "Given a registry write is in progress When the process is killed mid-write Then registry.json is either fully updated or fully intact at the previous state",
      "Given the atomic write uses a temp file When complete Then the pattern is: write to registry.json.tmp, then os.replace() to registry.json",
      "Given os.replace() is used When executed Then it is a single atomic operation on POSIX systems"
    ],
    "story_points": 3,
    "priority": "High",
    "labels": ["backend", "registry", "reliability"]
  },
  {
    "id": "US-21",
    "feature_id": "F-12",
    "title": "As the SSE Bridge, I want to load tool definitions exclusively from registry.json, so that no tool can be invoked unless it is explicitly registered.",
    "acceptance_criteria": [
      "Given a .py file exists in /memory/species/ but has no registry entry When the Host requests the tool list Then that tool is absent from the list",
      "Given registry.json is the only source of tool definitions When the Bridge starts Then it does not scan the filesystem independently of the registry",
      "Given a tool is requested by name When the Bridge looks it up Then it reads the entry_point from registry.json to resolve the callable"
    ],
    "story_points": 3,
    "priority": "High",
    "labels": ["backend", "registry", "security"]
  },
  {
    "id": "US-22",
    "feature_id": "F-13",
    "title": "As the Mutation Engine, I want to append new pip requirements to memory/requirements.txt after a successful mutation, so that the full dependency set is always reproducible.",
    "acceptance_criteria": [
      "Given a mutation introduces ['pypdf2'] When it succeeds Then 'pypdf2' is appended to memory/requirements.txt if not already present",
      "Given a requirement is already in requirements.txt When the mutation succeeds Then it is not duplicated",
      "Given requirements.txt does not exist When the first requirement is written Then the file is created"
    ],
    "story_points": 2,
    "priority": "Medium",
    "labels": ["backend", "dependencies"]
  },
  {
    "id": "US-23",
    "feature_id": "F-13",
    "title": "As a DevOps engineer, I want the Brain environment to rebuild automatically when requirements.txt changes, so that all declared dependencies are always installed.",
    "acceptance_criteria": [
      "Given requirements.txt is updated after a mutation When the Brain detects the change Then pip install -r requirements.txt is executed in the Brain virtualenv",
      "Given pip install -r fails When the rebuild runs Then the error is logged and the responsible skill is flagged in the registry",
      "Given no changes to requirements.txt When a mutation completes with no new dependencies Then no rebuild is triggered"
    ],
    "story_points": 5,
    "priority": "Medium",
    "labels": ["backend", "dependencies", "devops"]
  },
  {
    "id": "US-24",
    "feature_id": "F-14",
    "title": "As the Guard, I want to track mutation-to-fix-mutation recursion depth and halt the chain at depth > 3, so that runaway self-modification is prevented.",
    "acceptance_criteria": [
      "Given a mutation triggers a follow-up mutation to fix itself When the recursion depth reaches 4 Then the chain is halted and a GitHub Issue is opened",
      "Given the chain is halted When the error is returned Then it includes the recursion depth and the name of the skill that triggered the halt",
      "Given recursion depth ≤ 3 When a fix-mutation is requested Then it proceeds normally"
    ],
    "story_points": 8,
    "priority": "High",
    "labels": ["backend", "safety", "circuit-breaker"]
  },
  {
    "id": "US-25",
    "feature_id": "F-14",
    "title": "As the Guard, I want to monitor sandbox subprocess CPU and RAM usage and send SIGKILL when limits are exceeded, so that runaway processes cannot destabilize the Droplet.",
    "acceptance_criteria": [
      "Given a sandbox subprocess exceeds the defined CPU threshold When the Guard monitors it Then SIGKILL is sent to the subprocess",
      "Given a sandbox subprocess exceeds the defined RAM threshold When the Guard monitors it Then SIGKILL is sent to the subprocess",
      "Given SIGKILL is sent When the cleanup runs Then the responsible skill is marked as 'Toxic' in registry.json"
    ],
    "story_points": 8,
    "priority": "High",
    "labels": ["backend", "safety", "circuit-breaker"]
  },
  {
    "id": "US-26",
    "feature_id": "F-14",
    "title": "As the Guard, I want to mark a skill as 'Toxic' in registry.json when it triggers a resource limit, so that it cannot be loaded again without explicit manual review.",
    "acceptance_criteria": [
      "Given a skill triggers SIGKILL When the registry is updated Then the skill's entry contains a 'status': 'Toxic' field",
      "Given a skill is marked Toxic When the SSE Bridge builds the tool list Then that skill is excluded",
      "Given a Toxic skill is requested directly by the Host When the Bridge handles it Then it returns an error indicating the skill is quarantined"
    ],
    "story_points": 3,
    "priority": "High",
    "labels": ["backend", "safety", "registry"]
  },
  {
    "id": "US-27",
    "feature_id": "F-15",
    "title": "As a Host LLM, I want every error message to include file name, line number, and assertion detail, so that I can precisely diagnose and fix failed mutations without follow-up questions.",
    "acceptance_criteria": [
      "Given a pytest assertion fails When the error is returned Then the message includes the test file name, line number, and the full assertion expression",
      "Given a pip install fails When the error is returned Then the message includes the package name and the pip error output",
      "Given any mutation-stage error When formatted Then it never returns a bare 'Test failed.' message without context"
    ],
    "story_points": 3,
    "priority": "High",
    "labels": ["backend", "error-reporting"]
  },
  {
    "id": "US-28",
    "feature_id": "F-16",
    "title": "As the Brain, I want a watchdog file watcher on /memory/species, so that new .py files trigger automatic re-registration in registry.json without a server restart.",
    "acceptance_criteria": [
      "Given watchdog is monitoring /memory/species When a new .py file is created Then the file is registered in registry.json within 1 second",
      "Given a .py file is modified When watchdog detects the change Then the corresponding registry entry is updated",
      "Given the watchdog thread fails When the Brain is running Then the error is logged and the watcher restarts automatically"
    ],
    "story_points": 5,
    "priority": "High",
    "labels": ["backend", "hot-reload"]
  },
  {
    "id": "US-29",
    "feature_id": "F-17",
    "title": "As the Brain, I want to emit an MCP list_changed notification when the tool registry is updated, so that the Host LLM sees new tools without restarting the SSE session.",
    "acceptance_criteria": [
      "Given a new skill is registered in registry.json When the update is complete Then an MCP list_changed notification is sent over the active SSE connection",
      "Given no active SSE connection exists When the registry is updated Then the notification is queued and sent on the next connection",
      "Given list_changed is emitted When received by the Host Then the Host re-queries the tool list and the new skill appears"
    ],
    "story_points": 5,
    "priority": "High",
    "labels": ["backend", "hot-reload", "mcp"]
  },
  {
    "id": "US-30",
    "feature_id": "F-18",
    "title": "As a DevOps engineer, I want a darwin.service systemd unit file targeting the Brain's virtualenv, so that the organism starts automatically on boot.",
    "acceptance_criteria": [
      "Given darwin.service is installed When the Droplet boots Then the Brain starts automatically before any user logs in",
      "Given the unit file specifies WorkingDirectory=/opt/mcp-evolution-core When the service starts Then the working directory is set correctly before the process launches",
      "Given the ExecStart path When inspected Then it points to the virtualenv Python binary, not the system Python"
    ],
    "story_points": 3,
    "priority": "High",
    "labels": ["devops", "deployment"]
  },
  {
    "id": "US-31",
    "feature_id": "F-18",
    "title": "As a DevOps engineer, I want the service configured with Restart=on-failure and RestartSec=5, so that transient crashes result in recovery rather than a permanently dead Brain.",
    "acceptance_criteria": [
      "Given the Brain process crashes When systemd detects the exit Then it waits 5 seconds and restarts the service",
      "Given the Brain crashes repeatedly (>5 times in 60s) When systemd's start-limit-burst is reached Then it does not restart indefinitely",
      "Given Restart=on-failure When the Brain exits with code 0 Then systemd does not attempt a restart"
    ],
    "story_points": 2,
    "priority": "Medium",
    "labels": ["devops", "deployment", "resilience"]
  },
  {
    "id": "US-32",
    "feature_id": "F-19",
    "title": "As the Brain, I want all operational state to be derived from registry.json on startup, so that a service restart loses no tool registrations.",
    "acceptance_criteria": [
      "Given the Brain restarts When it reads registry.json Then all previously registered skills are available to the Host within 2 seconds",
      "Given registry.json is the sole state source When the Brain runs Then no in-memory-only state is used that would be lost on restart",
      "Given a restart occurs mid-mutation When the Brain comes back up Then the partial mutation's sandbox directory is cleaned up on startup"
    ],
    "story_points": 3,
    "priority": "High",
    "labels": ["backend", "resilience", "deployment"]
  }
]
```

---

## Sprint Plan (Step 4)

```json
[
  {
    "sprint_number": 1,
    "goal": "Lay the foundational infrastructure: registry bootstrap, SSE auth, tool serving, and deployment unit.",
    "story_ids": ["US-17", "US-18", "US-21", "US-1", "US-2", "US-5", "US-30", "US-31", "US-32"],
    "total_points": 28,
    "notes": "No mutation pipeline yet. Host can connect, authenticate, and see an empty or pre-seeded tool list. Systemd service is deployable from day 1."
  },
  {
    "sprint_number": 2,
    "goal": "Deliver species discovery and the core request_evolution endpoint with input validation and file promotion.",
    "story_ids": ["US-3", "US-4", "US-6", "US-7", "US-12", "US-19", "US-20"],
    "total_points": 26,
    "notes": "Sandbox and Git commit are excluded — mutations write files and registry entries but do not yet push to the vault."
  },
  {
    "sprint_number": 3,
    "goal": "Harden the mutation pipeline with isolated sandboxes, pytest execution, and dependency tracking.",
    "story_ids": ["US-8", "US-9", "US-10", "US-11", "US-22", "US-23"],
    "total_points": 26,
    "notes": "Depends on US-6 (Sprint 2). After this sprint the full code → test → promote path works end-to-end without Git."
  },
  {
    "sprint_number": 4,
    "goal": "Activate the Reproductive System: Git commit/push, conflict resolution, and circuit breaker core.",
    "story_ids": ["US-13", "US-14", "US-15", "US-16", "US-24"],
    "total_points": 23,
    "notes": "Depends on US-12 (Sprint 2). After this sprint the full evolution pipeline including vault persistence is operational."
  },
  {
    "sprint_number": 5,
    "goal": "Complete biosafety guardrails and hot reload so the system is self-protecting and self-updating.",
    "story_ids": ["US-25", "US-26", "US-27", "US-28", "US-29"],
    "total_points": 24,
    "notes": "Depends on US-24 (Sprint 4) and US-19 (Sprint 2). After this sprint the system is production-ready with full BSL enforcement."
  }
]
```

---

## Definition of Done (Step 5)

```json
{
  "definition_of_done": [
    "All acceptance criteria pass with automated pytest tests",
    "Code reviewed and merged to main with no unresolved comments",
    "registry.json updated with the new or modified skill entry",
    "Mutation pipeline runs end-to-end in the sandbox: code → pip install → pytest → git push",
    "Systemd darwin.service survives a manual sudo systemctl restart on the Droplet",
    "No Toxic skills present in registry.json at merge time"
  ]
}
```

---

## Story Point Summary

| Epic | Points |
|------|--------|
| EP-1: SSE Bridge | 16 |
| EP-2: Mutation Engine | 24 |
| EP-3: Git Manager | 15 |
| EP-4: Genome Registry | 14 |
| EP-5: Biosafety | 29 |
| EP-6: Hot Reload | 10 |
| EP-7: Deployment | 8 |
| **Total** | **127** |

| Sprint | Points |
|--------|--------|
| Sprint 1 — Foundation | 28 |
| Sprint 2 — Discovery & Mutation Core | 26 |
| Sprint 3 — Sandbox & Testing | 26 |
| Sprint 4 — Git & Circuit Breaker | 23 |
| Sprint 5 — Biosafety & Hot Reload | 24 |
| **Total** | **127** |
