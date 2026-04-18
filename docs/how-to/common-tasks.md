# How-To: Common Tasks

Practical guides for everyday Darwin-MCP workflows.

## Table of Contents

1. [Create a Skill with External Dependencies](#create-a-skill-with-external-dependencies)
2. [Debug a Failed Mutation](#debug-a-failed-mutation)
3. [Test Skills Locally Before Submission](#test-skills-locally-before-submission)
4. [View Skill Metadata in the Registry](#view-skill-metadata-in-the-registry)
5. [Rollback a Skill to a Previous Version](#rollback-a-skill-to-a-previous-version)
6. [Deploy the Brain to Production](#deploy-the-brain-to-production)
7. [Monitor Brain Health](#monitor-brain-health)
8. [Handle Merge Conflicts in Memory](#handle-merge-conflicts-in-memory)
9. [Add a New Test Case to an Existing Skill](#add-a-new-test-case-to-an-existing-skill)
10. [Troubleshoot Resource Limits](#troubleshoot-resource-limits)

---

## Create a Skill with External Dependencies

**Use this when**: Your skill needs `numpy`, `requests`, `pandas`, or other pip packages.

### Example: JSON Schema Validator

```python
from brain.engine.mutator import request_evolution

# Step 1: Define your code with imports
code = '''
import jsonschema

def validate_json(json_data: dict, schema: dict) -> dict:
    """Validate JSON against a schema. Return errors if validation fails."""
    try:
        jsonschema.validate(instance=json_data, schema=schema)
        return {"valid": True, "errors": []}
    except jsonschema.ValidationError as e:
        return {"valid": False, "errors": [str(e)]}
'''

# Step 2: Write tests that cover the external dependency
tests = '''
import json
from json_validator import validate_json

def test_valid_json():
    schema = {"type": "object", "properties": {"name": {"type": "string"}}}
    data = {"name": "Alice"}
    result = validate_json(data, schema)
    assert result["valid"] is True

def test_invalid_json():
    schema = {"type": "object", "properties": {"name": {"type": "string"}}}
    data = {"name": 123}  # Should fail: number, not string
    result = validate_json(data, schema)
    assert result["valid"] is False
    assert len(result["errors"]) > 0
'''

# Step 3: List external dependencies
requirements = ["jsonschema>=4.0.0"]

# Step 4: Submit
result = request_evolution(
    name="json_validator",
    code=code,
    tests=tests,
    requirements=requirements
)

print(f"Result: {result.to_dict()}")
```

### What Happens Inside

1. Brain creates `/tmp/mutation_<timestamp>/`
2. Creates isolated virtualenv in that directory
3. Runs `pip install jsonschema>=4.0.0` **only in that virtualenv**
4. Runs pytest to validate your tests
5. **Only if tests pass**: Writes `memory/species/json_validator.py`
6. Commits to git

**Benefits**:
- ✅ No dependency conflicts with other skills
- ✅ Each mutation is isolated
- ✅ Rollback is safe (old versions don't break)

### Version Pinning (Best Practice)

Always pin versions to avoid surprises:

```python
requirements = [
    "requests==2.31.0",
    "numpy>=1.24.0,<2.0.0",
    "pandas[parquet]>=2.0.0"
]
```

This ensures your skill behaves the same way every time.

---

## Debug a Failed Mutation

**Use this when**: `request_evolution` returns `success=False` and you need to understand why.

### Example: What Went Wrong?

```python
from brain.engine.mutator import request_evolution

result = request_evolution(
    name="my_broken_skill",
    code="def broken(): return 1/0",
    tests="def test(): broken()",
    requirements=[]
)

# Returns:
# {
#   "success": False,
#   "error": "AssertionError: assert 1 == 1",
#   "skill_name": None,
#   "version": None
# }
```

### Common Errors & Solutions

#### Error: "ValidationError: name is required"

```python
# ❌ Wrong
result = request_evolution(
    name="",  # Empty string
    code="...",
    tests="..."
)

# ✅ Correct
result = request_evolution(
    name="my_skill",  # Non-empty
    code="...",
    tests="..."
)
```

#### Error: "pytest FAILED: ImportError: No module named 'my_skill'"

```python
# ❌ Wrong: Test imports don't match code module name
code = '''
def process(x): return x * 2
'''
tests = '''
from my_skill import process  # This file name doesn't exist!
'''

# ✅ Correct: Import directly from code (pytest injects it)
tests = '''
from my_skill import process
def test(): assert process(5) == 10
'''

# OR write tests that define the function inline
tests = '''
def process(x): return x * 2
def test(): assert process(5) == 10
'''
```

#### Error: "CircuitBreakerError: Recursion depth limit (8) exceeded"

```python
# ❌ Wrong: Your skill calls itself recursively without base case
code = '''
def factorial(n):
    return n * factorial(n - 1)  # No base case!
'''

# ✅ Correct: Add base case
code = '''
def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)
'''
```

#### Error: "external dependency 'numpy' not found"

```python
# ❌ Wrong: Forgot to list dependency
code = '''
import numpy as np
def array_sum(arr):
    return np.sum(arr)
'''
requirements = []  # Missing numpy!

# ✅ Correct: Add to requirements
requirements = ["numpy>=1.24.0"]
```

### Enable Verbose Error Output

For more details, check the Brain's logs:

```bash
# Development (terminal where Brain is running)
# Look for traceback and pytest output

# Production (systemd)
sudo journalctl -u darwin -n 50 -f  # Last 50 lines, follow mode
```

### Test Locally First

Before submitting to Brain, test locally:

```bash
# Write your code to a file
cat > test_my_skill.py << 'EOF'
def my_skill(x):
    return x * 2

def test_my_skill():
    assert my_skill(5) == 10
EOF

# Run pytest locally
pytest test_my_skill.py -v
```

If it passes locally, it should pass on the Brain.

---

## Test Skills Locally Before Submission

**Use this when**: You want to validate your skill before burning a mutation.

### Quick Validation

```bash
# 1. Write code and tests to files
cat > my_skill.py << 'EOF'
def greet(name: str) -> str:
    return f"Hello, {name}!"
EOF

cat > test_my_skill.py << 'EOF'
from my_skill import greet

def test_greet():
    assert greet("Alice") == "Hello, Alice!"
    assert greet("Bob") == "Hello, Bob!"
EOF

# 2. Run pytest
pytest test_my_skill.py -v

# Expected output:
# test_my_skill.py::test_greet PASSED [100%]
```

### Validate with External Dependencies

```bash
# Create a virtual environment
python -m venv test_env
source test_env/bin/activate  # On Windows: test_env\Scripts\activate

# Install dependencies
pip install jsonschema

# Write and test
cat > test_schema_validator.py << 'EOF'
import jsonschema

def validate(data, schema):
    jsonschema.validate(instance=data, schema=schema)
    return True

def test_valid():
    schema = {"type": "string"}
    assert validate("hello", schema) is True
EOF

pytest test_schema_validator.py -v

# Clean up
deactivate
rm -rf test_env
```

### Full Simulation (Mirrors Brain Behavior)

```python
# Simulate what the Brain will do
import subprocess
import tempfile
from pathlib import Path

code = "def add(a, b): return a + b"
tests = "def test(): assert add(2, 3) == 5"
requirements = []

with tempfile.TemporaryDirectory() as tmpdir:
    tmpdir = Path(tmpdir)
    
    # Write files
    (tmpdir / "my_skill.py").write_text(code)
    (tmpdir / "test_my_skill.py").write_text(tests)
    
    # Run pytest
    result = subprocess.run(
        ["pytest", str(tmpdir / "test_my_skill.py"), "-v"],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        print("✅ Tests would pass on Brain")
    else:
        print("❌ Tests would fail:")
        print(result.stdout)
        print(result.stderr)
```

---

## View Skill Metadata in the Registry

**Use this when**: You want to inspect registered skills or verify metadata.

### List All Skills

```bash
cat memory/dna/registry.json | jq '.skills | keys'
```

Output:
```json
["leankg", "json_validator", "word_reverser"]
```

### View Details of a Single Skill

```bash
cat memory/dna/registry.json | jq '.skills.word_reverser'
```

Output:
```json
{
  "name": "word_reverser",
  "version": 2,
  "description": "Reverse the order of words in a sentence.",
  "schema": {
    "type": "object",
    "properties": {
      "text": {
        "type": "string",
        "description": "The text to reverse"
      }
    },
    "required": ["text"]
  }
}
```

### Check Registry File Size & Integrity

```bash
# File size
ls -lh memory/dna/registry.json

# Validate JSON syntax
jq empty memory/dna/registry.json && echo "✅ Valid JSON" || echo "❌ Invalid JSON"
```

### Count Registered Skills

```bash
cat memory/dna/registry.json | jq '.skills | length'
```

### Search for Skills by Name

```bash
cat memory/dna/registry.json | jq '.skills | keys[] | select(. | contains("json"))'
```

This finds all skills with "json" in the name.

---

## Rollback a Skill to a Previous Version

**Use this when**: A new skill version broke something; you need to restore the old one.

### Check Git History

```bash
cd memory
git log --oneline -- species/word_reverser.py

# Output:
# abc1234 evolution: word_reverser v2
# def5678 evolution: word_reverser v1
```

### Restore a Previous Version

```bash
cd memory

# Restore v1
git checkout def5678 -- species/word_reverser.py

# Update registry to point to v1
git checkout def5678 -- dna/registry.json

# Commit the rollback
git commit -m "rollback: word_reverser to v1 (fix regression)"
git push origin main
```

### Without Git (Direct File Replacement)

```bash
# If you know the exact content
cat > memory/species/word_reverser.py << 'EOF'
def word_reverser(text: str) -> str:
    """Reverse the order of words in a sentence."""
    return " ".join(reversed(text.split()))
EOF

# Update registry manually
# (This is not recommended; git-based rollback is safer)
```

### Rollback & Re-evolve

Instead of reverting, evolve with a fix:

```python
# Original broken code
broken_code = "def bug(): return 1 / 0"

# Fixed code
fixed_code = "def bug(): return 42"

# Resubmit with same skill name (will increment version)
result = request_evolution(
    name="buggy_skill",
    code=fixed_code,
    tests="def test(): assert bug() == 42",
    requirements=[]
)
# Creates v3 with the fix
```

---

## Deploy the Brain to Production

**Use this when**: You're ready to move the Brain from localhost to a $5 Droplet.

### Prerequisites

- DigitalOcean $5 Droplet (Ubuntu 22.04 LTS recommended)
- SSH access to the Droplet
- Domain name (optional; IP works too)

### Step 1: Provision the Droplet

```bash
# SSH into your new Droplet
ssh root@your-droplet-ip

# Update system packages
apt update && apt upgrade -y

# Install Python and dependencies
apt install -y python3 python3-pip python3-venv git

# Install systemd timer support (optional, for scheduled tasks)
apt install -y acl systemd-container
```

### Step 2: Clone the Repository

```bash
cd /opt

# Clone the Brain
git clone https://github.com/yourusername/mcp-evolution-core.git
cd mcp-evolution-core

# Initialize the Memory submodule
git submodule update --init --recursive
```

### Step 3: Set Up Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r brain/requirements.txt
```

### Step 4: Configure Environment

```bash
# Create a secure token
openssl rand -hex 32
# Output: abc123def456...

# Add to environment
echo 'export MCP_BEARER_TOKEN="abc123def456..."' >> /etc/environment
echo 'export GIT_SSH_COMMAND="ssh -i /root/.ssh/id_ed25519"' >> /etc/environment

# Reload
source /etc/environment
```

### Step 5: Set Up SSH for Git Submodule

```bash
# Generate SSH key on Droplet
ssh-keygen -t ed25519 -C "darwin@droplet" -N ""

# Display public key (add to GitHub deploy keys for private repo)
cat ~/.ssh/id_ed25519.pub

# Test connection
ssh -T git@github.com
```

### Step 6: Create Systemd Service

```bash
# Copy service file to systemd
sudo cp darwin.service /etc/systemd/system/

# Edit to match your paths (if needed)
sudo nano /etc/systemd/system/darwin.service

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable --now darwin
sudo systemctl status darwin
```

Expected output:
```
● darwin.service - Darwin-MCP Brain
   Loaded: loaded (/etc/systemd/system/darwin.service; enabled)
   Active: active (running)
```

### Step 7: Configure Firewall

```bash
# Allow SSH
sudo ufw allow ssh

# Allow port 8000 (or your chosen port)
sudo ufw allow 8000

# Enable firewall
sudo ufw enable
```

### Step 8: Test Connectivity

From your local machine:

```bash
curl -H "Authorization: Bearer $MCP_BEARER_TOKEN" \
  http://your-droplet-ip:8000/sse

# Or over HTTPS (if you set up a reverse proxy)
curl -H "Authorization: Bearer $MCP_BEARER_TOKEN" \
  https://your-domain.com/sse
```

### Optional: Set Up Nginx Reverse Proxy

For HTTPS and domain names:

```bash
# Install Nginx
sudo apt install -y nginx certbot python3-certbot-nginx

# Create Nginx config
sudo tee /etc/nginx/sites-available/darwin > /dev/null << 'EOF'
server {
    server_name your-domain.com;
    listen 80;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

# Enable site
sudo ln -s /etc/nginx/sites-available/darwin /etc/nginx/sites-enabled/

# Get SSL certificate
sudo certbot --nginx -d your-domain.com

# Restart Nginx
sudo systemctl restart nginx
```

### Monitor the Service

```bash
# Check status
sudo systemctl status darwin

# View logs (last 50 lines, follow)
sudo journalctl -u darwin -n 50 -f

# Restart if needed
sudo systemctl restart darwin
```

---

## Monitor Brain Health

**Use this when**: You want to ensure the Brain is running smoothly in production.

### Check Service Status

```bash
# Systemd service (production)
sudo systemctl status darwin

# Or get detailed status
sudo systemctl status --full darwin
```

### Monitor Logs in Real Time

```bash
# Watch logs as they appear
sudo journalctl -u darwin -f

# Or with grep filter (e.g., errors only)
sudo journalctl -u darwin -f | grep ERROR
```

### Check System Resources

```bash
# CPU and memory usage
top -p $(pgrep -f "uvicorn")

# Or use ps
ps aux | grep "uvicorn"
```

### Test Endpoints

```bash
# Health check
curl -H "Authorization: Bearer $MCP_BEARER_TOKEN" \
  http://localhost:8000/health

# Get tool list
curl -H "Authorization: Bearer $MCP_BEARER_TOKEN" \
  http://localhost:8000/sse \
  --max-time 5  # Timeout after 5s (SSE streams indefinitely)
```

### Monitor Registry for Staleness

```bash
# Check when registry was last updated
stat memory/dna/registry.json | grep Modify

# Check for orphaned species files (in disk but not in registry)
for file in memory/species/*.py; do
  name=$(basename "$file" .py)
  if ! grep -q "$name" memory/dna/registry.json; then
    echo "⚠️ Orphaned: $name"
  fi
done
```

### Set Up Alerts (Optional)

```bash
# Monitor service restarts
sudo journalctl -u darwin --no-pager | grep Restart

# Alert if service is down
systemctl is-active --quiet darwin || echo "ALERT: Brain is down!"
```

---

## Handle Merge Conflicts in Memory

**Use this when**: Multiple Brains push to the same memory vault simultaneously.

### Git Manager Auto-Handles Most Conflicts

The `GitManager` in `brain/utils/git_manager.py` automatically:
1. Detects push rejection (merge conflict)
2. Runs `git pull --rebase`
3. Retries the push

So in most cases, you won't see conflicts.

### Manual Conflict Resolution

If a conflict slips through:

```bash
cd memory

# Check status
git status

# See the conflict
git diff

# Resolve (e.g., keep incoming changes)
git checkout --theirs dna/registry.json

# Or manually edit
nano dna/registry.json  # Fix conflicts manually

# Stage and commit
git add .
git commit -m "resolve: merge conflict in registry"
git push origin main
```

### Prevent Conflicts

Use a **lock file** or **distributed registry**:

```python
# Option 1: Locking (simple but slow)
# Before writing registry, acquire a lock file
# After writing, release lock

# Option 2: CRDTs (complex but robust)
# Use a Conflict-free Replicated Data Type for registry

# Option 3: Central Coordinator
# Single Brain handles writes; others read-only
```

---

## Add a New Test Case to an Existing Skill

**Use this when**: A skill exists but needs more test coverage.

### Example: Add Tests to `word_reverser`

Current skill:

```python
def word_reverser(text: str) -> str:
    """Reverse the order of words in a sentence."""
    return " ".join(reversed(text.split()))
```

Current tests:

```python
def test_simple():
    assert word_reverser("hello world") == "world hello"
```

### Add More Test Cases

```python
from brain.engine.mutator import request_evolution

enhanced_code = '''
def word_reverser(text: str) -> str:
    """Reverse the order of words in a sentence."""
    return " ".join(reversed(text.split()))
'''

enhanced_tests = '''
def test_simple():
    assert word_reverser("hello world") == "world hello"

def test_empty():
    assert word_reverser("") == ""

def test_single_word():
    assert word_reverser("hello") == "hello"

def test_multiple_spaces():
    # Multiple spaces are collapsed by split()
    assert word_reverser("hello  world") == "world hello"

def test_punctuation():
    assert word_reverser("hello, world!") == "world! hello,"

def test_numbers():
    assert word_reverser("123 456 789") == "789 456 123"
'''

result = request_evolution(
    name="word_reverser",
    code=enhanced_code,
    tests=enhanced_tests,
    requirements=[]
)

if result.success:
    print(f"✅ Version {result.version}: Tests expanded")
else:
    print(f"❌ {result.error}")
```

### Run Tests Locally First

```bash
cat > test_word_reverser.py << 'EOF'
def word_reverser(text: str) -> str:
    return " ".join(reversed(text.split()))

def test_simple():
    assert word_reverser("hello world") == "world hello"

def test_empty():
    assert word_reverser("") == ""
EOF

pytest test_word_reverser.py -v
```

---

## Troubleshoot Resource Limits

**Use this when**: A skill is hitting the circuit breaker limits.

### Recursion Depth Limit Exceeded

```
CircuitBreakerError: Recursion depth limit (8) for skill 'recursive_skill'
```

**Root Cause**: Skill calls itself too deeply (e.g., recursive algorithm without base case).

**Solution**: Add a base case or increase depth limit.

```python
# ❌ Wrong: No base case
code = '''
def countdown(n):
    print(n)
    return countdown(n - 1)
'''

# ✅ Correct: Has base case
code = '''
def countdown(n):
    if n == 0:
        return
    print(n)
    return countdown(n - 1)
'''
```

To increase limit (in `brain/engine/guard.py`):

```python
MAX_RECURSION_DEPTH = 16  # Default is 8
```

### CPU Limit Exceeded

```
CircuitBreakerError: CPU usage 95% exceeds limit 80%
```

**Root Cause**: Skill is spinning or doing expensive computation.

**Solution**:
1. Optimize the algorithm
2. Add timeouts
3. Increase limit in `brain/engine/guard.py`:

```python
MAX_CPU_PERCENT = 90  # Default is 80
```

### Memory Limit Exceeded

```
CircuitBreakerError: Memory 650MB exceeds limit 512MB
```

**Root Cause**: Skill is loading large dataset or leaking memory.

**Solution**:
1. Stream data instead of loading all at once
2. Use generators instead of lists
3. Increase limit:

```python
MAX_MEMORY_MB = 1024  # Default is 512
```

### Check Current Limits

```python
from brain.engine.guard import MAX_RECURSION_DEPTH, MAX_CPU_PERCENT, MAX_MEMORY_MB

print(f"Recursion: {MAX_RECURSION_DEPTH}")
print(f"CPU: {MAX_CPU_PERCENT}%")
print(f"Memory: {MAX_MEMORY_MB}MB")
```

---

## Next Steps

- 📖 [Technical Manifesto](../reference/technical-manifesto.md) — API contracts and detailed specs
- 🚀 [Deployment Guide](../reference/technical-manifesto.md#system-integration-map) — Deep dive into production setup
- 🧪 [Test Best Practices](../how-to/common-tasks.md#testing-skills-locally-before-submission) — Write robust tests
- 📝 [Contributing Guide](../../README.md#contributing) — Submit skills and improvements

---

**Happy skill evolution!** 🧬
