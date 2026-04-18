# Getting Started with Darwin-MCP

This guide walks you through setting up the Brain locally and creating your first AI skill.

## Prerequisites

Ensure you have:
- **Python 3.9+** (`python --version`)
- **Git** with SSH key configured (`ssh -T git@github.com`)
- **pip** (usually bundled with Python)
- **10–15 minutes** ⏱️

## Step 1: Clone the Repository

```bash
git clone https://github.com/yourusername/mcp-evolution-core.git
cd mcp-evolution-core
```

This creates a local copy of the Brain code.

## Step 2: Initialize the Memory Submodule

The `memory/` folder is a **private Git submodule** that stores all evolved skills and the registry. You must initialize it:

```bash
git submodule update --init --recursive
```

This clones `mcp-evolution-vault` into the `memory/` directory. You'll see:

```
memory/
├── dna/
│   └── registry.json      ← Skill registry
├── species/
│   ├── leankg.py         ← Example skill
│   ├── nestjs_best_practices.py
│   └── fpga_best_practices.py
└── requirements.txt       ← Shared dependencies
```

**If this fails**, ensure:
- You have SSH access to the private repo (`mcp-evolution-vault`)
- Your SSH key is loaded: `ssh-add ~/.ssh/id_rsa`
- The remote URL is SSH, not HTTPS: `git remote -v`

## Step 3: Install Dependencies

```bash
pip install -r brain/requirements.txt
```

This installs:
- `fastapi` — HTTP framework for the SSE server
- `watchdog` — File system watcher
- `pytest` — Test runner for mutations
- `pydantic` — Data validation

**On macOS with M1/M2**, you might need:

```bash
pip install --upgrade cryptography PyYAML
```

## Step 4: Set Environment Variables

```bash
export MCP_BEARER_TOKEN="your-super-secret-token-here"
export GIT_SSH_COMMAND="ssh -i ~/.ssh/id_rsa"  # For private submodule access
```

Store these in `.env` (not committed) or `~/.bashrc`:

```bash
# ~/.bashrc or ~/.zshrc
export MCP_BEARER_TOKEN="your-super-secret-token-here"
export GIT_SSH_COMMAND="ssh -i ~/.ssh/id_rsa"
```

Then reload: `source ~/.bashrc` or `source ~/.zshrc`

**⚠️ IMPORTANT**: Never commit tokens to git. Add `.env` to `.gitignore` if you create one.

## Step 5: Start the Brain (Development Mode)

```bash
uvicorn brain.bridge.sse_server:app --reload --host 0.0.0.0 --port 8000
```

You should see:

```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete
INFO:     Watching directories for changes
```

The Brain is now **online and listening** on `http://localhost:8000`.

**What's happening:**
1. Registry is loaded from `memory/dna/registry.json`
2. Existing skills in `memory/species/` are discovered
3. File watcher starts, monitoring `/memory/species` for changes
4. SSE endpoint (`/sse`) is ready to accept connections

## Step 6: Test the Connection

In a **new terminal** (keep the Brain running), verify it's working:

```bash
curl -H "Authorization: Bearer $MCP_BEARER_TOKEN" \
  http://localhost:8000/sse
```

You should see the MCP tool list as JSON (or SSE stream headers).

If you get a **401 Unauthorized**, check your `MCP_BEARER_TOKEN`.

## Step 7: Run the Test Suite

Before creating your first skill, ensure the codebase is healthy:

```bash
pytest tests/ -v
```

Expected output:

```
tests/test_sse_server.py::test_startup PASSED
tests/test_mutator.py::test_request_evolution_success PASSED
tests/test_registry.py::test_read_registry PASSED
...
======================== X passed in 0.23s ========================
```

If any test fails, see [Troubleshooting](#troubleshooting) below.

## Step 8: Create Your First Skill

Let's create a simple skill called `word_reverser` that reverses text.

### Define the Skill

Create a Python string with your skill code:

```python
# In a new file or interactive Python session
skill_code = '''
def word_reverser(text: str) -> str:
    """Reverse the order of words in a sentence."""
    return " ".join(reversed(text.split()))
'''

skill_tests = '''
from word_reverser import word_reverser

def test_simple():
    assert word_reverser("hello world") == "world hello"

def test_empty():
    assert word_reverser("") == ""

def test_single():
    assert word_reverser("hello") == "hello"
'''

skill_requirements = []  # No external dependencies needed
```

### Submit to the Brain

```python
import os
import sys
from brain.engine.mutator import request_evolution

os.environ["MCP_BEARER_TOKEN"] = "your-super-secret-token-here"

result = request_evolution(
    name="word_reverser",
    code=skill_code,
    tests=skill_tests,
    requirements=skill_requirements
)

if result.success:
    print(f"✅ Skill created: {result.skill_name} v{result.version}")
else:
    print(f"❌ Error: {result.error}")
```

### What the Brain Does

1. **Validates** inputs (non-empty strings, list of requirements)
2. **Creates** `/tmp/mutation_<timestamp>/` sandbox
3. **Installs** requirements in isolated virtualenv
4. **Runs** pytest; if tests fail, aborts and returns error
5. **Writes** `memory/species/word_reverser.py` (only if tests pass)
6. **Commits** to git: `evolution: word_reverser v1`
7. **Updates** `memory/dna/registry.json` with new skill metadata
8. **Returns** `{"success": true, "skill_name": "word_reverser", "version": 1}`

### Verify in Registry

Check that your skill is registered:

```bash
cat memory/dna/registry.json | jq '.skills.word_reverser'
```

Output:

```json
{
  "name": "word_reverser",
  "version": 1,
  "description": "Reverse the order of words in a sentence.",
  "schema": { ... }
}
```

### Invoke the Skill

The Host LLM can now call `word_reverser` via MCP.

## Step 9: Evolve the Skill

Skills can evolve. Send improved code + tests:

```python
evolved_code = '''
def word_reverser(text: str, keep_punctuation: bool = True) -> str:
    """Reverse the order of words, optionally preserving punctuation position."""
    words = text.split()
    reversed_words = list(reversed(words))
    return " ".join(reversed_words)
'''

evolved_tests = '''
from word_reverser import word_reverser

def test_simple():
    assert word_reverser("hello world") == "world hello"

def test_with_punctuation():
    result = word_reverser("hello, world!")
    assert "hello" in result and "world" in result
'''

result = request_evolution(
    name="word_reverser",
    code=evolved_code,
    tests=evolved_tests,
    requirements=[]
)

if result.success:
    print(f"✅ Skill evolved: {result.skill_name} v{result.version}")
```

The Brain will:
- Increment version to `2`
- Run tests in a new sandbox
- Overwrite `memory/species/word_reverser.py`
- Commit: `evolution: word_reverser v2`
- Update registry

**No breaking changes.** The old version is in git history; you can roll back anytime.

## Step 10: Inspect & Debug

### View Skill Source

```bash
cat memory/species/word_reverser.py
```

### Check Registry

```bash
cat memory/dna/registry.json | jq .
```

### Read Brain Logs

```bash
# If running with uvicorn (development)
# Check terminal where you started the Brain

# If running as systemd service (production)
sudo journalctl -u darwin -f
```

### Test Locally Before Submitting

Always validate code before calling `request_evolution`:

```bash
pytest my_skill_tests.py -v
```

This catches errors locally, saving a sandbox mutation.

## Troubleshooting

### "ModuleNotFoundError" When Starting Brain

**Problem**: `ModuleNotFoundError: No module named 'brain'`

**Solution**:
```bash
export PYTHONPATH="${PYTHONPATH}:/path/to/mcp-evolution-core"
# Or ensure you're running from the project root
cd /path/to/mcp-evolution-core
```

### "401 Unauthorized" on Curl

**Problem**: `curl` returns 401 when querying `/sse`

**Solution**:
```bash
# Verify token is set
echo $MCP_BEARER_TOKEN  # Should not be empty

# Check if it matches what the server has
env | grep MCP_BEARER_TOKEN
```

### Git Submodule Not Initialized

**Problem**: `memory/` directory is empty or missing `registry.json`

**Solution**:
```bash
git submodule update --init --recursive
git submodule update --remote  # Also fetch latest changes
```

### SSH Key Not Found for Private Repo

**Problem**: `fatal: could not read Username`

**Solution**:
```bash
# Generate SSH key if you don't have one
ssh-keygen -t ed25519 -C "your-email@example.com"

# Add to SSH agent
ssh-add ~/.ssh/id_ed25519

# Test SSH connection
ssh -T git@github.com
```

### Pytest Hangs or Times Out

**Problem**: `pytest` seems frozen when running tests in mutation

**Solution**:
```bash
# Check if tests have infinite loops or blocking I/O
# Run with timeout:
pytest --timeout=10 tests/

# Or check for stray processes:
ps aux | grep python
```

### Registry Out of Sync

**Problem**: A skill was added to disk but not to `registry.json`

**Solution**: Re-discover species:
```python
from brain.utils.registry import discover_species
discover_species()
```

This re-scans `memory/species/` and updates the registry.

## Next Steps

- 📖 **[How-To: Common Tasks](../how-to/common-tasks.md)** — Create skills with external dependencies, debug mutations, deploy to production
- 📚 **[Technical Manifesto](../reference/technical-manifesto.md)** — Deep dive into API contracts and Git state machine
- 🏗️ **[Architecture Guide](../reference/technical-manifesto.md#system-integration-map)** — Understand the Triad, layers, and safety mechanisms
- 🧪 **[Testing Guide](../how-to/common-tasks.md#testing-skills)** — Write robust tests for skills

## Need Help?

- Check logs: `journalctl -u darwin -f` (production) or terminal output (development)
- Review error message in `request_evolution` result
- Search existing GitHub issues
- Open a new issue with error trace and reproduction steps

---

**Ready to train your first skill? Let's go!** 🚀
