# Contributing to Darwin-MCP

> Darwin rewards the fit. Every contribution that enters the genome must survive the same selection pressure as any mutation: it must pass its tests, respect the Brain/Memory boundary, and leave the organism more capable than it found it.

---

## The Darwinian Contribution Model

Darwin-MCP has reached **Sovereign status** — the Brain (logic) and Memory (vault) are fully decoupled, the mutation pipeline is self-healing, and the genome is protected by three biosafety layers. Contributing to this project means contributing to a **living system**, not a static codebase.

The rules below are not bureaucracy. They are the immune system.

### Core Principles

| Principle | What it means in practice |
|-----------|--------------------------|
| **No gene without a test** | Every new function, class, and script must have a corresponding test. Red phase is mandatory. |
| **Brain stays stateless** | The Brain (`brain/`) must never store mutable state on disk. All persistence belongs in Memory (`memory/`). |
| **Memory stays decoupled** | The Memory vault is a git submodule. Species files and `registry.json` are never modified by CI — only by `request_evolution()`. |
| **Biosafety is non-negotiable** | New dependencies go through the sandbox. No direct `subprocess` calls that bypass the mutation pipeline. |
| **The registry is the truth** | `memory/dna/registry.json` is the single source of truth for all registered skills. Nothing else may be used to determine what tools are live. |

---

## Development Setup

```bash
# 1. Fork and clone
git clone https://github.com/<your-handle>/Darwin-MCP.git
cd Darwin-MCP
git submodule update --init --recursive

# 2. Install dependencies
pip install -r brain/requirements.txt
pip install -r brain/requirements-dev.txt  # if present

# 3. Set required environment variables
export MCP_BEARER_TOKEN="dev-token-for-local-testing"
export GIT_SSH_COMMAND="ssh -i ~/.ssh/id_rsa"

# 4. Verify the baseline
pytest tests/ -q
# All tests must pass before you begin. If they don't, open an issue.
```

---

## Branching Strategy

### Branch Naming

```
feat/US-N-short-description      ← new feature from backlog story
fix/US-N-short-description       ← bug fix tied to a story
docs/topic-name                  ← documentation-only change
chore/what-you-did               ← dependency bumps, submodule updates
```

### Feature-Branch-to-Main Workflow

```
main  ─────────────────────────────────────────────────────▶
            │                               │
            └──── feat/US-42-lysosome ──────┘
                   (tests → impl → PR)
```

1. **Always branch from `main`** — never from another feature branch
2. **Never commit directly to `main`** — open a Pull Request
3. **Squash or rebase** before merging — keep the commit graph linear

### The Memory Submodule Rule

If your change affects any species file or `registry.json`, you **must** bump the submodule pointer in the same PR:

```bash
# After your species/registry changes are committed inside memory/
cd memory && git add . && git commit -m "chore: bump species for <feature>"
cd ..
git add memory
git commit -m "chore: bump memory submodule — <feature>"
```

PRs that modify Brain logic which implicitly changes runtime behaviour must include a submodule bump even if no species file was directly edited (e.g., changes to `mutator.py` that alter `registry.json` schema).

---

## TDD: The Mandatory Red Phase

Darwin-MCP is built test-first. The red phase is not optional — it proves the test actually covers the behaviour you are adding.

### The Three Commits

```
1. test(scope): add failing tests for <feature>
   # pytest tests/ must show NEW failures here

2. feat(scope): implement <feature> to pass tests
   # pytest tests/ must be fully green here

3. refactor(scope): clean up <feature>  [optional]
   # pytest tests/ still fully green
```

### Test File Convention

| Source file | Test file |
|-------------|-----------|
| `brain/engine/sandbox.py` | `tests/test_sandbox.py` |
| `brain/engine/inquiry.py` | `tests/test_inquiry.py` |
| `brain/scripts/sanity_check.sh` | `tests/test_sanity_check.py` |
| `brain/bridge/sse_server.py` | `tests/test_sse_server.py` |

Every new module **requires** a corresponding test file. PRs without tests will not be merged.

### Test Quality Bar

```python
# ✅ Good — tests behaviour, not implementation
def test_purge_pip_cache_calls_pip_cache_purge(tmp_path):
    with patch("brain.engine.sandbox.subprocess.run", return_value=_ok_result()) as mock_run:
        s = Sandbox(base_dir=tmp_path)
        s.purge_pip_cache()
        assert any("cache" in str(c) and "purge" in str(c) for c in mock_run.call_args_list)

# ❌ Bad — tests internal state, brittle
def test_purge_pip_cache_sets_internal_flag():
    s = Sandbox()
    s.purge_pip_cache()
    assert s._purged is True  # nobody should care about this
```

---

## Mutation Standards

When contributing a new **skill** (species) to the genome via `request_evolution`, follow this contract:

### Required Structure

```python
# memory/species/my_skill.py
"""
One-line description of what this skill does.

Provenance: evolved via request_evolution()  |  version: 1
"""
import logging

logger = logging.getLogger(__name__)


def my_skill(input_data: dict) -> dict:
    """
    Args:
        input_data: dict with required keys documented here

    Returns:
        dict with result keys documented here
    """
    try:
        # implementation
        result = do_work(input_data)
        return {"status": "ok", "result": result}
    except Exception as exc:
        logger.error("my_skill failed: %s", exc)
        return {"status": "error", "message": str(exc)}
```

### Required Tests

```python
# Passed as the `tests` argument to request_evolution()
def test_my_skill_happy_path():
    result = my_skill({"key": "value"})
    assert result["status"] == "ok"
    assert "result" in result

def test_my_skill_handles_invalid_input():
    result = my_skill({})
    assert result["status"] == "error"
```

### Registry Entry

Every evolved skill must have a `short_description` field (≤10 words, action-verb first) for the Dynamic Tool Router:

```json
{
  "my_skill": {
    "status": "active",
    "short_description": "Processes input data and returns structured results.",
    "entry_point": "my_skill",
    "version": 1,
    "dependencies": []
  }
}
```

### Calling `request_evolution`

```python
from brain.engine.mutator import request_evolution

result = request_evolution(
    name="my_skill",
    code=open("my_skill.py").read(),
    tests=open("test_my_skill.py").read(),
    requirements=["httpx"],            # pip packages, empty list if none
    description="Processes input data and returns structured results.",
    git_commit=True,                   # commits to the vault
    memory_dir="memory",               # path to vault submodule
)

assert result.success, result.error
```

---

## Commit Message Format

```
type(scope): short imperative description (≤72 chars)

Optional body: explain WHY this change exists, not WHAT it does.
The diff shows what — the commit message explains the intent.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
```

### Types

| Type | When to use |
|------|-------------|
| `feat` | New capability added to the organism |
| `fix` | Bug correction — cite the symptom in the subject |
| `test` | Tests added or updated (red phase commit) |
| `refactor` | Code restructured without behaviour change |
| `docs` | Documentation only |
| `chore` | Maintenance: dependency bumps, submodule bumps, CI config |
| `perf` | Performance improvement with measurable evidence |

### Scopes

Use the biological/technical name of the component you touched:

`lysosome` · `mutator` · `sandbox` · `guard` · `inquiry` · `peer-review` · `hot-reload` · `registry` · `git-manager` · `sse-bridge` · `router` · `resurrection` · `leankg` · `council` · `hardening` · `US-N`

---

## Pull Request Checklist

Before opening a PR, verify every item:

```
□ pytest tests/ -q passes with no new failures
□ Every new source file has a matching tests/test_<file>.py
□ New skills include short_description in registry entry
□ No secrets, tokens, or API keys in source code
□ Memory submodule bumped if species/registry was touched
□ darwin.service restarts cleanly with the new code
□ Commit messages follow the format above (type(scope): ...)
□ PR description explains the biological role of the change
```

---

## What Not to Do

| ❌ Don't | Why |
|---------|-----|
| Commit directly to `main` | Bypasses review and breaks the linear history |
| Store mutable state in `brain/` | Violates Brain/Memory separation — Brain is stateless |
| Hardcode `MCP_BEARER_TOKEN` | Security breach — always use environment variables |
| Skip the red phase | Proves nothing — tests that were never red may not test what you think |
| Modify `memory/` directly | Mutations must go through `request_evolution()` — direct edits bypass biosafety |
| Add a new species without tests | Nothing enters the genome without passing its tests |
| Import `requests` / `httpx` at module level in species | Use lazy imports inside functions to avoid dependency bleed |

---

## Semantic Versioning for Skills

Skill versions are tracked automatically by `request_evolution()` — version `N+1` is assigned when a skill with name `N` already exists in the registry. You do not need to manage this manually.

To introduce a **breaking change** to a skill's interface:
1. Create a new skill with a new name (e.g., `my_skill_v2`)
2. Mark the old skill as deprecated in its `registry.json` entry (`"status": "deprecated"`)
3. Never delete a species file — the vault is append-only

---

## Security

- All authentication uses constant-time `hmac.compare_digest` — never `==`
- `MCP_BEARER_TOKEN` is sourced exclusively from the OS environment or `/opt/mcp-evolution-core/.env` with `chmod 600`
- No species file may call `os.system`, `eval`, or `exec` on untrusted input
- All external code runs inside `Sandbox` — never in the Brain's process
- Report security vulnerabilities privately via [GitHub Security Advisories](https://github.com/mehdibadjian/Darwin-MCP/security/advisories)

---

## Questions & Discussion

- **Feature ideas** — [GitHub Discussions](https://github.com/mehdibadjian/Darwin-MCP/discussions)
- **Bug reports** — [GitHub Issues](https://github.com/mehdibadjian/Darwin-MCP/issues)
- **Architecture questions** — open a Discussion with label `architecture`

---

*Contribute code that earns its place in the genome. The organism remembers everything.* 🧬
