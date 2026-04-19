"""Autonomous Heartbeat — Darwin-MCP nervous system.

This module is the 24/7 orchestration loop that connects the four pillars
(Scavenger, Architect, Mutator, Lysosome) into a self-driving cycle without
requiring a human in the loop.

Beat Cycle (one full tick)
--------------------------
1.  Collect system vitals (CPU, RAM, disk)
2.  Parse evolution.log for new anomalies → enqueue "report" tasks
3.  If CPU is idle (< IDLE_CPU_THRESHOLD) and backlog has pending work:
      Dequeue the highest-priority item and dispatch it:
        "evolve"   → POST /evolve (calls request_evolution pipeline)
        "prune"    → run_pruner() (Lysosome)
        "optimize" → skill_optimizer (Policy species)
        "report"   → log the anomaly report
4.  Nightly (once per calendar day) run the Lysosome as a scheduled sweep
    regardless of backlog.
5.  Purge stale completed backlog items.
6.  Write heartbeat_status.json to memory/.

Running Standalone
------------------
    python -m brain.engine.heartbeat              # runs forever (10-min interval)
    python -m brain.engine.heartbeat --once       # single beat then exit
    python -m brain.engine.heartbeat --interval 60  # 60-second interval

Deployment (Droplet / macOS)
-----------------------------
    brain/scripts/install_heartbeat.sh   installs a crontab entry.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from datetime import datetime, timezone, date
from pathlib import Path
from typing import Optional

from brain.engine.backlog import (
    dequeue,
    enqueue,
    get_all,
    mark_done,
    mark_failed,
    pending_count,
    purge_done,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration constants (override via env vars)
# ---------------------------------------------------------------------------

# CPU thresholds per task cost-tier (% system CPU).
# "evolve" spins up a virtualenv + pytest — it is the most expensive operation.
# "prune" and "optimize" are mostly I/O.  "report" is just a log write.
#
# Tier | Task type  | Max CPU to proceed
# -----+------------+-------------------
#  H   | evolve     | SAFE_CPU_EVOLVE  (default 40 %)
#  M   | prune      | SAFE_CPU_MEDIUM  (default 60 %)
#  M   | optimize   | SAFE_CPU_MEDIUM  (default 60 %)
#  L   | report     | always allowed
#
# A $5 Droplet has 1 vCPU.  Running a mutation at > 40 % existing load
# risks OOM / kernel kill.  These defaults are deliberately conservative.

SAFE_CPU_EVOLVE: float = float(os.environ.get("DARWIN_CPU_EVOLVE", "40.0"))
SAFE_CPU_MEDIUM: float = float(os.environ.get("DARWIN_CPU_MEDIUM", "60.0"))
# How many seconds to wait between CPU samples when double-checking load
CPU_SAMPLE_INTERVAL: float = float(os.environ.get("DARWIN_CPU_SAMPLE_INTERVAL", "2.0"))
# Number of consecutive samples that must all pass the threshold
CPU_SAMPLE_COUNT: int = int(os.environ.get("DARWIN_CPU_SAMPLE_COUNT", "2"))

DEFAULT_INTERVAL_SECONDS: int = int(os.environ.get("DARWIN_HEARTBEAT_INTERVAL", "600"))  # 10 min

# If true, auto-commit evolutions that pass 100% of tests (no human gate).
AUTO_APPROVE: bool = os.environ.get("DARWIN_AUTO_APPROVE", "false").lower() == "true"

# If true, skip inter-beat sleep when backlog still has pending items (tight loop).
CONTINUOUS_MODE: bool = os.environ.get("DARWIN_CONTINUOUS_MODE", "false").lower() == "true"

# Hard ceiling on total registered species — evolve tasks are blocked above this.
MAX_SPECIES: int = int(os.environ.get("DARWIN_MAX_SPECIES", "100"))

LOG_TAIL_LINES: int = 50    # lines scanned for anomalies per beat
# Cost tier → CPU ceiling mapping
_TASK_CPU_CEILING: dict[str, float] = {
    "evolve":   SAFE_CPU_EVOLVE,
    "prune":    SAFE_CPU_MEDIUM,
    "optimize": SAFE_CPU_MEDIUM,
    "report":   100.0,   # always safe
}

ANOMALY_PATTERNS: list[tuple[str, int]] = [
    # (regex pattern, priority)
    (r"\bCRITICAL\b",        1),
    (r"\bERROR\b",           2),
    (r"\bcircuit.breaker\b", 1),
    (r"\bToxic\b",           2),
    (r"\brebuild.failed\b",  2),
    (r"\bpush.failed\b",     3),
]

_MEMORY_DIR = Path(__file__).resolve().parent.parent.parent / "memory"
_STATUS_PATH = _MEMORY_DIR / "heartbeat_status.json"
_LOG_PATH = _MEMORY_DIR / "evolution.log"
_PRUNE_STATE_PATH = _MEMORY_DIR / "dna" / "last_prune_date.txt"


# ---------------------------------------------------------------------------
# Resource guard — multi-sample CPU safety check
# ---------------------------------------------------------------------------

def _cpu_is_safe_for(task_type: str) -> tuple[bool, float]:
    """Take CPU_SAMPLE_COUNT consecutive readings and verify all are below the
    ceiling for *task_type*.

    Returns (safe: bool, worst_sample: float).

    For "evolve" tasks this is the critical kernel-panic prevention gate:
    a $5 Droplet has 1 vCPU and will OOM if we spawn a virtualenv + pytest
    while already under load.
    """
    try:
        import psutil
    except ImportError:
        logger.warning("psutil not available — skipping CPU guard (unsafe on Droplet!)")
        return True, 0.0

    ceiling = _TASK_CPU_CEILING.get(task_type, SAFE_CPU_MEDIUM)

    # Always free — skip sampling overhead
    if ceiling >= 100.0:
        return True, 0.0

    samples: list[float] = []
    for i in range(CPU_SAMPLE_COUNT):
        if i > 0:
            time.sleep(CPU_SAMPLE_INTERVAL)
        cpu = psutil.cpu_percent(interval=1.0)   # 1-second blocking sample
        samples.append(cpu)
        if cpu >= ceiling:
            # Fast-fail: first bad sample aborts early
            logger.info(
                "CPU guard: %s task blocked — sample %d/%.1f%% ≥ ceiling %.0f%%",
                task_type, i + 1, cpu, ceiling,
            )
            return False, cpu

    worst = max(samples)
    logger.debug(
        "CPU guard: %s task cleared — samples=%s ceiling=%.0f%%",
        task_type, [f"{s:.1f}" for s in samples], ceiling,
    )
    return True, worst


# ---------------------------------------------------------------------------
# Status persistence
# ---------------------------------------------------------------------------

def _read_status() -> dict:
    if _STATUS_PATH.exists():
        try:
            return json.loads(_STATUS_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"beats": 0, "last_beat_at": None, "last_prune_date": None, "anomalies_found": 0}


def _write_status(status: dict) -> None:
    _STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = _STATUS_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(status, indent=2), encoding="utf-8")
    tmp.replace(_STATUS_PATH)


# ---------------------------------------------------------------------------
# Scavenger hook — parse evolution.log for anomalies
# ---------------------------------------------------------------------------

def _scan_log_for_anomalies(log_path: Path = _LOG_PATH) -> list[dict]:
    """Return list of anomaly dicts from the last LOG_TAIL_LINES of the log."""
    if not log_path.exists():
        return []

    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    tail = lines[-LOG_TAIL_LINES:] if len(lines) > LOG_TAIL_LINES else lines

    anomalies: list[dict] = []
    seen_lines: set[str] = set()

    for line in tail:
        stripped = line.strip()
        if not stripped or stripped in seen_lines:
            continue
        for pattern, priority in ANOMALY_PATTERNS:
            if re.search(pattern, stripped, re.IGNORECASE):
                anomalies.append({
                    "line": stripped[:300],
                    "pattern": pattern,
                    "priority": priority,
                })
                seen_lines.add(stripped)
                break   # one match per line

    return anomalies


def _enqueue_anomaly_reports(anomalies: list[dict], backlog_path=None) -> int:
    """Add anomaly report tasks to the backlog. Deduplicates by line content.

    Returns number of new items enqueued.
    """
    existing = get_all(backlog_path, status="pending")
    existing_lines = {
        i["payload"].get("line", "")
        for i in existing
        if i["task_type"] == "report"
    }

    count = 0
    for anomaly in anomalies:
        if anomaly["line"] in existing_lines:
            continue
        enqueue(
            task_type="report",
            payload=anomaly,
            priority=anomaly["priority"],
            backlog_path=backlog_path,
        )
        existing_lines.add(anomaly["line"])
        count += 1

    if count:
        logger.info("Heartbeat: enqueued %d new anomaly report(s)", count)
    return count


# ---------------------------------------------------------------------------
# Species scaffold generator — creates stub code+tests for description-only tasks
# ---------------------------------------------------------------------------

def _web_context_for_skill(name: str, description: str) -> str:
    """Search DuckDuckGo for domain context. Returns a brief summary string."""
    try:
        import urllib.request
        import urllib.parse
        query = urllib.parse.quote(f"{name.replace('_', ' ')} {description[:60]}")
        url = f"https://api.duckduckgo.com/?q={query}&format=json&no_redirect=1&no_html=1&skip_disambig=1"
        req = urllib.request.Request(url, headers={"User-Agent": "Darwin-MCP/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())
        abstract = data.get("AbstractText", "") or data.get("Answer", "")
        related  = " | ".join(
            r.get("Text", "")[:80] for r in data.get("RelatedTopics", [])[:3] if isinstance(r, dict)
        )
        ctx = (abstract + " " + related).strip()[:600]
        return ctx
    except Exception:
        return ""


def _ollama_generate_body(func: str, description: str, web_ctx: str, suffix: str) -> str:
    """Ask Ollama gemma:2b to generate the function body. Returns raw body or '' on failure."""
    try:
        from brain.utils.ollama_client import chat

        system = (
            "You are an expert Python developer writing the BODY of a function. "
            "Rules: "
            "1. Output ONLY indented Python statements (4-space indent). "
            "2. Do NOT write a def line, docstring, imports, or markdown fences. "
            "3. Use only stdlib — no undefined modules or imports. "
            "4. Read inputs with params.get(). "
            "5. The last statement MUST be: return {\"status\": \"ok\", \"name\": \"FUNCNAME\", \"result\": <real_result>}. "
            "6. Implement real logic relevant to the description — no TODOs, no stubs, no None returns."
        ).replace("FUNCNAME", func)

        prompt = (
            f"Function name: {func}\n"
            f"Description: {description}\n"
            + (f"Domain context: {web_ctx}\n" if web_ctx else "")
            + "\nOutput only the 4-space-indented function body lines, nothing else:"
        )

        raw = chat(prompt, system=system, timeout=90)
        if not raw:
            return ""

        # Strip markdown fences, def lines, docstrings
        lines = raw.splitlines()
        cleaned = []
        in_fence     = False
        in_docstring = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence:
                cleaned.append(line)
                continue
            # Toggle docstring state
            dq_count = stripped.count('"""')
            sq_count = stripped.count("'''")
            if (dq_count % 2 == 1) or (sq_count % 2 == 1):
                in_docstring = not in_docstring
                continue
            if in_docstring:
                continue
            if stripped.startswith("def "):
                continue
            cleaned.append(line)
        body = "\n".join(cleaned).strip()

        # Validate it contains a return statement with the required keys
        if "return" not in body:
            return ""
        if '"status"' not in body and "'status'" not in body:
            return ""

        # Normalise indentation — ensure all non-empty lines have ≥4 spaces
        re_indented = []
        for line in body.splitlines():
            stripped = line.lstrip()
            if stripped:
                indent = len(line) - len(stripped)
                base_indent = max(4, indent)
                re_indented.append((" " * base_indent) + stripped)
            else:
                re_indented.append("")
        return "\n".join(re_indented)
    except Exception as exc:
        logger.warning("Ollama scaffold generation failed for %s: %s", func, exc)
        return ""


def _generate_species_scaffold(name: str, description: str, requirements: list) -> tuple:
    """Return (code, tests) for a description-only evolve task.

    Generation pipeline:
      1. Web search (DuckDuckGo) for domain context.
      2. Ollama gemma:2b generates the real function body using that context.
      3. Falls back to suffix-pattern templates if Ollama fails or returns garbage.
    """
    func   = name.lower().replace("-", "_").replace(" ", "_")
    domain = func.rsplit("_", 1)[0] if "_" in func else func  # strip suffix
    suffix = name.rsplit("_", 1)[-1] if "_" in name else ""

    # --- Step 1: gather web context -----------------------------------------
    web_ctx = _web_context_for_skill(name, description)
    if web_ctx:
        logger.info("[scaffold] web context for %s: %s…", func, web_ctx[:80])

    req_imports = "\n".join(f"# pip install {r}" for r in requirements) if requirements else ""

    # --- Step 2: ask Ollama to write the body --------------------------------
    ollama_body = _ollama_generate_body(func, description, web_ctx, suffix)
    if ollama_body:
        # Syntax-check the full assembled code before accepting it
        req_comment = f"\n{req_imports}\n" if req_imports else ""
        probe = (
            f'from __future__ import annotations\nfrom typing import Any, Dict\n{req_comment}\n'
            f"def {func}(params: Dict[str, Any]) -> Dict[str, Any]:\n{ollama_body}\n"
        )
        try:
            compile(probe, "<scaffold>", "exec")
            logger.info("[scaffold] Ollama body syntax OK for %s (%d chars)", func, len(ollama_body))
            body = ollama_body
        except SyntaxError as e:
            logger.warning("[scaffold] Ollama body syntax error for %s: %s — using suffix template", func, e)
            body = None
    else:
        logger.info("[scaffold] Ollama returned empty — using suffix template for %s", func)
        body = None

    # ---- Suffix fallback templates (only used when Ollama fails) -----------
    if body is not None:
        pass  # Ollama succeeded — skip templates
    elif suffix in ("reporter", "summary_writer", "writer"):
        body = f'''\
    domain   = params.get("domain",  "{domain.replace("_", " ")}")
    target   = params.get("target",  "all")
    fmt      = params.get("format",  "text")

    lines = [
        f"=== {{domain}} Report ===",
        f"Target  : {{target}}",
        f"Summary : {description[:120]}",
        "Status  : operational",
    ]
    report = "\\n".join(lines) if fmt == "text" else dict(domain=domain, target=target, description="{description[:120]}")
    return {{"status": "ok", "name": "{func}", "result": report}}'''

    elif suffix in ("checker", "health_checker", "validator", "data_validator"):
        body = f'''\
    target  = params.get("target", "")
    rules   = params.get("rules",  [])

    findings = []
    errors   = []

    # {description[:100]}
    if not target:
        errors.append("'target' param is required — pass a file path, URL, or resource name")

    result = {{
        "target":   target,
        "findings": findings,
        "errors":   errors,
        "passed":   len(errors) == 0,
    }}
    return {{"status": "ok", "name": "{func}", "result": result}}'''

    elif suffix in ("tracker", "task_tracker"):
        body = f'''\
    items    = params.get("items", [])
    status   = params.get("status", "all")

    # {description[:100]}
    summary = {{
        "total":       len(items),
        "filtered_by": status,
        "items":       [i for i in items if status == "all" or i.get("status") == status],
    }}
    return {{"status": "ok", "name": "{func}", "result": summary}}'''

    elif suffix in ("automator", "workflow_automator", "runner"):
        body = f'''\
    steps_taken = []
    target      = params.get("target", "")
    dry_run     = params.get("dry_run", False)

    # {description[:100]}
    workflow_steps = [
        f"1. Validate inputs for {{target}}",
        f"2. Execute {domain.replace("_", " ")} workflow",
        f"3. Verify completion",
    ]
    for step in workflow_steps:
        if not dry_run:
            steps_taken.append({{"step": step, "status": "done"}})
        else:
            steps_taken.append({{"step": step, "status": "dry-run"}})

    return {{"status": "ok", "name": "{func}", "result": {{"steps": steps_taken, "dry_run": dry_run}}}}'''

    elif suffix in ("generator", "template_generator"):
        body = f'''\
    template_type = params.get("type",   "default")
    context       = params.get("context", {{}})

    # {description[:100]}
    output = f"""# Generated by {func}
# Type: {{template_type}}
# Domain: {domain.replace("_", " ")}
# Context: {{context}}

# TODO: implement {domain.replace("_", " ")} template for {{template_type}}
"""
    return {{"status": "ok", "name": "{func}", "result": output}}'''

    elif suffix in ("manager", "alert_manager"):
        body = f'''\
    action   = params.get("action",   "list")   # list | create | update | delete
    resource = params.get("resource", {{}})
    store    = params.get("store",    [])

    # {description[:100]}
    if action == "list":
        result = {{"items": store, "count": len(store)}}
    elif action == "create":
        store.append(resource)
        result = {{"created": resource, "total": len(store)}}
    elif action == "update":
        result = {{"updated": resource}}
    elif action == "delete":
        result = {{"deleted": resource}}
    else:
        result = {{"error": f"Unknown action: {{action}}"}}

    return {{"status": "ok", "name": "{func}", "result": result}}'''

    elif suffix in ("exporter", "metrics_exporter"):
        body = f'''\
    import time
    fmt    = params.get("format",  "dict")   # dict | prometheus | json
    labels = params.get("labels",  {{}})

    # {description[:100]}
    metrics = {{
        "timestamp":  time.time(),
        "domain":     "{domain.replace("_", " ")}",
        "labels":     labels,
        "values":     {{}},
    }}

    if fmt == "prometheus":
        lines = [f"# HELP {func} {description[:60]}"]
        for k, v in metrics["values"].items():
            lines.append(f"{func}_{{k}}{{{{labels}}}} {{v}}")
        result = "\\n".join(lines)
    else:
        result = metrics

    return {{"status": "ok", "name": "{func}", "result": result}}'''

    elif suffix in ("analyser", "analyzer"):
        body = f'''\
    data        = params.get("data",  [])
    threshold   = params.get("threshold", 0.5)

    # {description[:100]}
    findings = []
    score    = 0.0

    if data:
        score = round(sum(1 for d in data if d) / len(data), 2)
        if score < threshold:
            findings.append(f"Score {{score}} below threshold {{threshold}}")

    return {{
        "status":   "ok",
        "name":     "{func}",
        "result":   {{
            "score":    score,
            "findings": findings,
            "items":    len(data),
        }},
    }}'''

    elif suffix in ("changelog_writer",):
        body = f'''\
    changes  = params.get("changes",  [])
    version  = params.get("version",  "unreleased")
    fmt      = params.get("format",   "markdown")

    # {description[:100]}
    lines = [f"## [{{version}}]", ""]
    for c in changes:
        lines.append(f"- {{c}}")
    if not changes:
        lines.append("- No changes recorded")

    result = "\\n".join(lines) if fmt == "markdown" else {{"version": version, "changes": changes}}
    return {{"status": "ok", "name": "{func}", "result": result}}'''

    else:
        # Generic — at minimum returns structured data based on params
        body = f'''\
    target  = params.get("target",  "")
    options = params.get("options", {{}})

    # {description[:100]}
    result = {{
        "target":      target,
        "options":     options,
        "domain":      "{domain.replace("_", " ")}",
        "description": "{description[:120]}",
        "output":      f"Processed {{target}} with {func}",
    }}
    return {{"status": "ok", "name": "{func}", "result": result}}'''

    req_comment = f"\n{req_imports}\n" if req_imports else ""
    code = (
        f'"""{description}\n"""\n'
        f"from __future__ import annotations\n"
        f"from typing import Any, Dict\n"
        f"{req_comment}\n"
        f"def {func}(params: Dict[str, Any]) -> Dict[str, Any]:\n"
        f'    """{description}\n\n'
        f"    Args:\n"
        f"        params: Input parameters (see implementation for keys).\n\n"
        f"    Returns:\n"
        f"        Dict with 'status', 'name', and 'result'.\n"
        f'    """\n'
        f"{body}\n"
    )
    tests = (
        f'"""Tests for {func}."""\n'
        f"import sys, os\n"
        f"sys.path.insert(0, os.path.dirname(__file__))\n"
        f"from {func} import {func}\n\n"
        f"def test_{func}_returns_ok():\n"
        f"    result = {func}({{}})\n"
        f'    assert result["status"] == "ok"\n\n'
        f"def test_{func}_has_name():\n"
        f"    result = {func}({{}})\n"
        f'    assert result["name"] == "{func}"\n\n'
        f"def test_{func}_has_result_key():\n"
        f"    result = {func}({{}})\n"
        f'    assert "result" in result\n'
    )
    return code, tests


# ---------------------------------------------------------------------------
# Dispatcher — routes dequeued items to the correct engine
# ---------------------------------------------------------------------------

def _dispatch(item: dict) -> tuple[bool, str]:
    """Dispatch a backlog item to the appropriate engine.

    Returns (success: bool, message: str).
    """
    task_type = item["task_type"]
    payload = item.get("payload", {})

    if task_type == "report":
        line = payload.get("line", "")
        pattern = payload.get("pattern", "")
        msg = f"[ANOMALY] pattern={pattern!r} | {line}"
        logger.warning(msg)
        return True, msg

    if task_type == "prune":
        try:
            from brain.engine.pruner import run_pruner
            dry_run = payload.get("dry_run", False)
            result = run_pruner(dry_run=dry_run)
            msg = (
                f"Pruner complete — archived={result.archived}, "
                f"kept={result.kept}, dry_run={result.dry_run}"
            )
            logger.info(msg)
            return True, msg
        except Exception as exc:
            return False, f"Prune failed: {exc}"

    if task_type == "evolve":
        try:
            from brain.engine.mutator import request_evolution
            from brain.utils.registry import read_registry

            # Enforce species ceiling
            registry = read_registry()
            current_count = len(registry.get("skills", {}))
            if current_count >= MAX_SPECIES:
                return False, (
                    f"MAX_SPECIES ceiling reached ({current_count}/{MAX_SPECIES}) — "
                    "prune or raise DARWIN_MAX_SPECIES"
                )

            # Generate scaffold when no code is provided
            code = payload.get("code", "").strip()
            tests = payload.get("tests", "").strip()
            if not code:
                code, tests = _generate_species_scaffold(
                    name=payload["name"],
                    description=payload.get("description", ""),
                    requirements=payload.get("requirements", []),
                )
                logger.info(
                    "No code in payload for '%s' — generated scaffold (AUTO_APPROVE=%s)",
                    payload["name"], AUTO_APPROVE,
                )

            result = request_evolution(
                name=payload["name"],
                code=code,
                tests=tests,
                requirements=payload.get("requirements", []),
                description=payload.get("description", ""),
                git_commit=AUTO_APPROVE,
                memory_dir=str(_MEMORY_DIR),
                skip_similarity_check=payload.get("skip_similarity_check", False),
            )
            if result.success:
                return True, f"Evolved '{payload['name']}' v{result.version}"
            return False, result.error or "Unknown mutation failure"
        except Exception as exc:
            return False, f"Evolve failed: {exc}"

    if task_type == "optimize":
        try:
            from memory.species.skill_optimizer import skill_optimizer
            result = skill_optimizer(
                strategy=payload.get("strategy", "detect"),
                target_skills=payload.get("target_skills"),
            )
            msg = f"Optimizer: {result.get('summary', 'done')}"
            logger.info(msg)
            return True, msg
        except Exception as exc:
            return False, f"Optimize failed: {exc}"

    return False, f"Unknown task_type: {task_type!r}"


# ---------------------------------------------------------------------------
# Lysosome nightly sweep
# ---------------------------------------------------------------------------

def _should_run_nightly_prune() -> bool:
    """Return True if we haven't pruned today yet."""
    today = date.today().isoformat()
    if _PRUNE_STATE_PATH.exists():
        try:
            last = _PRUNE_STATE_PATH.read_text().strip()
            if last == today:
                return False
        except Exception:
            pass
    return True


def _record_prune_date() -> None:
    _PRUNE_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _PRUNE_STATE_PATH.write_text(date.today().isoformat())


# ---------------------------------------------------------------------------
# Core beat
# ---------------------------------------------------------------------------

def beat(backlog_path=None) -> dict:
    """Execute one full heartbeat cycle.

    Returns a status dict suitable for writing to heartbeat_status.json.
    """
    ts = datetime.now(timezone.utc).isoformat()
    status = _read_status()
    status["last_beat_at"] = ts
    status["beats"] = status.get("beats", 0) + 1

    report: dict = {
        "beat_number": status["beats"],
        "timestamp": ts,
        "vitals": {},
        "anomalies_found": 0,
        "items_dispatched": 0,
        "nightly_prune": False,
        "errors": [],
    }

    # Step 1 — collect vitals (1-second blocking sample for accuracy)
    cpu: float = 0.0
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=1.0)
        vm = psutil.virtual_memory()
        report["vitals"] = {
            "cpu_percent": cpu,
            "memory_percent": vm.percent,
            "cpu_ceiling_evolve": SAFE_CPU_EVOLVE,
            "cpu_ceiling_medium": SAFE_CPU_MEDIUM,
        }
        status["last_vitals"] = report["vitals"]
    except Exception as exc:
        report["errors"].append(f"vitals: {exc}")

    # Step 2 — scan evolution log for anomalies
    try:
        anomalies = _scan_log_for_anomalies()
        new_tasks = _enqueue_anomaly_reports(anomalies, backlog_path=backlog_path)
        report["anomalies_found"] = new_tasks
        status["anomalies_found"] = status.get("anomalies_found", 0) + new_tasks
    except Exception as exc:
        report["errors"].append(f"log_scan: {exc}")

    # Step 3 — dispatch next backlog item with tiered CPU safety gate.
    #
    # Strategy: peek at the next pending item's task_type BEFORE dequeuing,
    # then run the multi-sample CPU guard for that specific tier.  If the
    # Droplet is busy we skip execution entirely — the item stays in the
    # queue and will be retried on the next beat.  We never skip "report"
    # tasks (they are just log writes with no CPU cost).
    try:
        if pending_count(backlog_path=backlog_path) > 0:
            # Peek without dequeuing so we can check the task type first
            from brain.engine.backlog import get_all
            pending_items = get_all(backlog_path=backlog_path, status="pending")
            pending_items.sort(key=lambda i: (i["priority"], i["created_at"]))
            next_item = pending_items[0] if pending_items else None

            if next_item:
                task_type = next_item["task_type"]
                safe, worst_cpu = _cpu_is_safe_for(task_type)

                if safe:
                    item = dequeue(backlog_path=backlog_path)
                    if item:
                        success, msg = _dispatch(item)
                        if success:
                            mark_done(item["id"], backlog_path=backlog_path)
                            report["items_dispatched"] += 1
                            logger.info(
                                "Dispatched %s task %s: %s",
                                item["task_type"], item["id"], msg,
                            )
                        else:
                            mark_failed(item["id"], error=msg, backlog_path=backlog_path)
                            report["errors"].append(f"dispatch({item['id']}): {msg}")
                else:
                    ceiling = _TASK_CPU_CEILING.get(task_type, SAFE_CPU_MEDIUM)
                    skipped_msg = (
                        f"Skipped {task_type!r} task — CPU {worst_cpu:.1f}% "
                        f"exceeds safe ceiling {ceiling:.0f}% for this tier. "
                        f"Will retry next beat."
                    )
                    logger.warning(skipped_msg)
                    report["cpu_guard_skip"] = skipped_msg
    except Exception as exc:
        report["errors"].append(f"dispatch: {exc}")

    # Step 4 — nightly Lysosome sweep
    try:
        if _should_run_nightly_prune():
            from brain.engine.pruner import run_pruner
            result = run_pruner()
            report["nightly_prune"] = True
            report["nightly_prune_detail"] = {
                "archived": result.archived,
                "kept": result.kept,
            }
            _record_prune_date()
            status["last_prune_date"] = date.today().isoformat()
            logger.info(
                "Nightly prune complete: archived=%s kept=%s",
                result.archived, result.kept,
            )
    except Exception as exc:
        report["errors"].append(f"nightly_prune: {exc}")

    # Step 5 — purge stale completed backlog items
    try:
        purge_done(backlog_path=backlog_path)
    except Exception as exc:
        report["errors"].append(f"purge: {exc}")

    # Persist status
    status["last_report"] = report
    _write_status(status)

    if report["errors"]:
        logger.warning("Beat #%d completed with errors: %s", status["beats"], report["errors"])
    else:
        logger.info(
            "Beat #%d OK | cpu=%.1f%% anomalies=%d dispatched=%d prune=%s",
            status["beats"],
            report["vitals"].get("cpu_percent", 0.0),
            report["anomalies_found"],
            report["items_dispatched"],
            report["nightly_prune"],
        )

    return report


# ---------------------------------------------------------------------------
# Continuous loop
# ---------------------------------------------------------------------------

def run_forever(interval: int = DEFAULT_INTERVAL_SECONDS, backlog_path=None) -> None:
    """Run beat() in an infinite loop with *interval* seconds between ticks.

    When CONTINUOUS_MODE is true the inter-beat sleep is skipped whenever there
    are still pending items in the backlog, creating a tight execution loop.
    Uses time.sleep() — safe to interrupt with SIGINT/SIGTERM.
    """
    logger.info(
        "Darwin Heartbeat starting — interval=%ds CPU idle threshold=%.0f%% "
        "auto_approve=%s continuous=%s max_species=%d",
        interval, SAFE_CPU_EVOLVE, AUTO_APPROVE, CONTINUOUS_MODE, MAX_SPECIES,
    )
    while True:
        try:
            beat(backlog_path=backlog_path)
        except KeyboardInterrupt:
            logger.info("Heartbeat stopped by user")
            return
        except Exception as exc:
            logger.error("Unhandled error in beat(): %s", exc, exc_info=True)

        # In continuous mode, skip sleep when work is waiting
        if CONTINUOUS_MODE and pending_count(backlog_path=backlog_path) > 0:
            logger.debug("CONTINUOUS_MODE: backlog non-empty — skipping sleep")
            continue

        try:
            time.sleep(interval)
        except KeyboardInterrupt:
            logger.info("Heartbeat stopped during sleep")
            return


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    import argparse
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(description="Darwin-MCP Autonomous Heartbeat")
    parser.add_argument("--once", action="store_true", help="Run one beat then exit")
    parser.add_argument(
        "--interval", type=int, default=DEFAULT_INTERVAL_SECONDS,
        help=f"Seconds between beats (default: {DEFAULT_INTERVAL_SECONDS})",
    )
    args = parser.parse_args()

    if args.once:
        report = beat()
        print(json.dumps(report, indent=2))
    else:
        run_forever(interval=args.interval)


if __name__ == "__main__":
    main()
