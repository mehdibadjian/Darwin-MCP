"""SSE Bridge server — US-1, US-2, US-5, US-21, US-28, US-29, US-32, ENH-US7.

Serves the MCP tool list over Server-Sent Events with Bearer token auth.
All operational state is derived exclusively from registry.json.
Supports multi-tenant vault routing via the X-Vault-Repo header.
"""
import asyncio
import hmac
import json
import os
import shutil
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse

from brain.engine.mutator import request_evolution
from brain.middleware.json_validator import JSONValidatorMiddleware
from brain.utils.context_buffer import compress_search_results
from brain.utils.registry import discover_species, init_registry, read_registry, write_registry
from brain.utils.web_fetch import fetch_url, fetch_urls, search_web
from brain.bridge.router import get_routed_tools
from brain.watcher.hot_reload import (
    flush_queued_notifications,
    register_sse_callback,
    start_watcher,
    unregister_sse_callback,
)

# Token is always sourced from the environment — never hardcoded.
MCP_BEARER_TOKEN: str = os.environ.get("MCP_BEARER_TOKEN", "")

# ---------------------------------------------------------------------------
# Vault path resolution — ENH-US7
# ---------------------------------------------------------------------------

WORKSPACE_ROOT: Path = Path(__file__).resolve().parent.parent.parent
PRIMARY_VAULT: Path = WORKSPACE_ROOT / "memory"
SUBMODULES_DIR: Path = WORKSPACE_ROOT / "memory" / "submodules"


def resolve_vault_path(vault_id: Optional[str]) -> Path:
    """Resolve *vault_id* to a filesystem Path.

    Returns PRIMARY_VAULT when *vault_id* is None or empty.
    Returns SUBMODULES_DIR / vault_id when that directory exists.
    Raises ValueError("Vault not found") for non-empty ids whose path is absent.
    """
    if not vault_id:
        return PRIMARY_VAULT
    candidate = SUBMODULES_DIR / vault_id
    if not candidate.is_dir():
        raise ValueError("Vault not found")
    return candidate


def get_vault_registry_path(vault_path: Path) -> Path:
    """Return the registry.json path inside *vault_path*/dna/."""
    return vault_path / "dna" / "registry.json"


def verify_token(authorization: Optional[str]) -> bool:
    """Constant-time token comparison using hmac.compare_digest."""
    if not authorization or not authorization.startswith("Bearer "):
        return False
    token = authorization.removeprefix("Bearer ").strip()
    expected = os.environ.get("MCP_BEARER_TOKEN", "")
    if not expected:
        return False
    return hmac.compare_digest(token.encode(), expected.encode())


def cleanup_stale_sandboxes() -> None:
    """Remove any /tmp/mutation_* directories left from a crashed mutation."""
    for p in Path("/tmp").glob("mutation_*"):
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)


def _register_builtin_tools(registry_path=None) -> None:
    """Ensure built-in tools like get_droplet_vitals are in the registry."""
    init_registry(registry_path)
    registry = read_registry(registry_path)
    if "get_droplet_vitals" not in registry["skills"]:
        registry["skills"]["get_droplet_vitals"] = {
            "path": "brain/engine/vitals.py",
            "entry_point": "get_droplet_vitals",
            "runtime": "builtin",
            "dependencies": ["psutil"],
            "status": "active",
            "description": "Returns Droplet CPU, RAM, disk vitals and last 10 evolution log lines",
        }
        write_registry(registry, registry_path)


def _load_meshnet_config() -> None:
    """Log the active Meshnet base_url at startup if meshnet.json exists."""
    import logging
    config_path = WORKSPACE_ROOT / "brain" / "config" / "meshnet.json"
    if config_path.exists():
        try:
            import json as _json
            cfg = _json.loads(config_path.read_text())
            logging.getLogger(__name__).info(
                "Meshnet bridge configured: base_url=%s model=%s",
                cfg.get("base_url", "unset"),
                cfg.get("model", "unset"),
            )
        except Exception:
            pass


def _startup() -> None:
    init_registry()
    discover_species()
    _register_builtin_tools()
    cleanup_stale_sandboxes()
    start_watcher()
    _load_meshnet_config()


app = FastAPI(on_startup=[_startup])
app.add_middleware(JSONValidatorMiddleware)


@app.get("/sse")
async def sse_endpoint(request: Request) -> Response:
    """Stream tool list and list_changed notifications over SSE after auth check.

    Optional query parameter ``?query=<text>`` activates the Dynamic Tool Router,
    which exposes only the top-3 most relevant tools to small models like Gemma 2b.
    """
    auth = request.headers.get("Authorization")
    if not verify_token(auth):
        return Response(status_code=401)

    vault_id = request.headers.get("X-Vault-Repo")
    try:
        vault_path = resolve_vault_path(vault_id)
    except ValueError as exc:
        return Response(status_code=400, content=str(exc))

    registry_path = get_vault_registry_path(vault_path)
    query = request.query_params.get("query", "").strip()

    async def event_stream():
        queue: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_event_loop()

        def on_notification(notif: dict) -> None:
            try:
                loop.call_soon_threadsafe(queue.put_nowait, notif)
            except Exception:
                pass

        register_sse_callback(on_notification)
        flush_queued_notifications(on_notification)

        try:
            registry = read_registry(registry_path)
            if query:
                tools = get_routed_tools(query, registry, top_n=3)
            else:
                tools = {
                    name: entry
                    for name, entry in registry["skills"].items()
                    if entry.get("status") != "Toxic"
                }
            yield f"data: {json.dumps({'type': 'tool_list', 'tools': tools})}\n\n"

            while True:
                try:
                    notif = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {json.dumps(notif)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            pass  # client disconnected or test teardown — exit cleanly
        finally:
            unregister_sse_callback(on_notification)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/tools/{name}/invoke")
async def invoke_tool(name: str, request: Request) -> Response:
    """Return 403 if the requested skill is Toxic, 200 if active, 404 if unknown."""
    auth = request.headers.get("Authorization")
    if not verify_token(auth):
        return Response(status_code=401)

    vault_id = request.headers.get("X-Vault-Repo")
    try:
        vault_path = resolve_vault_path(vault_id)
    except ValueError as exc:
        return Response(status_code=400, content=str(exc))

    if name == "get_droplet_vitals":
        from brain.engine.vitals import collect, get_evolution_log_tail
        metrics = collect()
        log_lines = get_evolution_log_tail()
        payload = {**metrics, "evolution_log_tail": log_lines}
        return JSONResponse(status_code=200, content=payload)

    registry_path = get_vault_registry_path(vault_path)
    registry = read_registry(registry_path)
    skill = registry.get("skills", {}).get(name)
    if skill is None:
        return Response(status_code=404, content=f"Tool '{name}' not found")
    if skill.get("status") == "Toxic":
        return Response(
            status_code=403,
            content=f"Tool '{name}' is quarantined (Toxic). Manual review required.",
        )
    return Response(content=json.dumps({"name": name, "status": "ok"}), media_type="application/json")


@app.post("/evolve")
async def evolve_endpoint(request: Request) -> Response:
    """Receive a mutation payload and run the full request_evolution pipeline."""
    auth = request.headers.get("Authorization")
    if not verify_token(auth):
        return Response(status_code=401)

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"status": "error", "message": "Invalid JSON"})

    name = body.get("name", "").strip()
    code = body.get("code", "")
    tests = body.get("tests", "")
    requirements = body.get("requirements", [])

    if not name or not code or not tests:
        return JSONResponse(
            status_code=422,
            content={"status": "error", "message": "name, code, and tests are required"},
        )

    memory_dir = Path(__file__).resolve().parent.parent.parent / "memory"
    vault_id = request.headers.get("X-Vault-Repo")
    try:
        vault_path = resolve_vault_path(vault_id)
        memory_dir = vault_path
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"status": "error", "message": str(exc)})
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: request_evolution(
            name=name,
            code=code,
            tests=tests,
            requirements=requirements,
            git_commit=True,
            memory_dir=str(memory_dir),
        ),
    )
    if result.success:
        return JSONResponse(status_code=200, content={"status": "success", **result.to_dict()})
    return JSONResponse(status_code=422, content={"status": "error", **result.to_dict()})


@app.post("/search")
async def search_endpoint(request: Request) -> Response:
    """Fetch URLs or run a web search query.

    Modes:
      {"urls": ["https://..."]}          — fetch specific URLs, return stripped text
      {"query": "FPGA best practices"}   — DuckDuckGo search, return titles+snippets+urls
      {"query": "...", "fetch": true}    — search then fetch top results, return full text
    """
    auth = request.headers.get("Authorization")
    if not verify_token(auth):
        return Response(status_code=401)

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"status": "error", "message": "Invalid JSON"})

    loop = asyncio.get_event_loop()

    # Mode 1: fetch explicit URLs
    if "urls" in body:
        urls = body["urls"]
        if not isinstance(urls, list) or not urls:
            return JSONResponse(status_code=422, content={"status": "error", "message": "'urls' must be a non-empty list"})
        results = await loop.run_in_executor(None, lambda: fetch_urls(urls[:5]))
        return JSONResponse(status_code=200, content={"status": "ok", "mode": "fetch", "results": results})

    # Mode 2: web search (optionally followed by fetch)
    if "query" in body:
        query = body["query"].strip()
        if not query:
            return JSONResponse(status_code=422, content={"status": "error", "message": "'query' must not be empty"})
        do_fetch = body.get("fetch", False)
        max_results = min(int(body.get("max_results", 5)), 10)

        search_results = await loop.run_in_executor(
            None, lambda: search_web(query, max_results=max_results)
        )

        if do_fetch:
            urls = [r["url"] for r in search_results if r.get("url")][:3]
            pages = await loop.run_in_executor(None, lambda: fetch_urls(urls))
            # Merge snippet + fetched text, then compress to Flash Report.
            for sr in search_results:
                match = next((p for p in pages if p["url"] == sr.get("url")), None)
                if match and match.get("status") == "ok":
                    sr["text"] = match["text"]
            compress_search_results(search_results, query=query)

        return JSONResponse(status_code=200, content={
            "status": "ok",
            "mode": "search+fetch" if do_fetch else "search",
            "query": query,
            "results": search_results,
        })

    return JSONResponse(status_code=422, content={"status": "error", "message": "Provide 'urls' or 'query'"})


# ---------------------------------------------------------------------------
# Genetic Backlog endpoints
# ---------------------------------------------------------------------------

@app.get("/backlog")
async def backlog_list(request: Request) -> Response:
    """Return all backlog items, optionally filtered by ?status=pending|running|done|failed."""
    auth = request.headers.get("Authorization")
    if not verify_token(auth):
        return Response(status_code=401)

    from brain.engine.backlog import get_all
    status_filter = request.query_params.get("status", "").strip() or None
    items = get_all(status=status_filter)
    return JSONResponse(status_code=200, content={"status": "ok", "count": len(items), "items": items})


@app.post("/backlog")
async def backlog_enqueue(request: Request) -> Response:
    """Enqueue a new task into the Genetic Backlog.

    Body: {"task_type": str, "payload": dict, "priority": int (1-5, optional)}
    """
    auth = request.headers.get("Authorization")
    if not verify_token(auth):
        return Response(status_code=401)

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"status": "error", "message": "Invalid JSON"})

    task_type = body.get("task_type", "").strip()
    payload = body.get("payload", {})
    priority = int(body.get("priority", 3))

    if not task_type:
        return JSONResponse(status_code=422, content={"status": "error", "message": "task_type is required"})

    try:
        from brain.engine.backlog import enqueue
        item_id = enqueue(task_type=task_type, payload=payload, priority=priority)
        return JSONResponse(status_code=200, content={"status": "ok", "id": item_id})
    except ValueError as exc:
        return JSONResponse(status_code=422, content={"status": "error", "message": str(exc)})


@app.delete("/backlog/{item_id}")
async def backlog_cancel(item_id: str, request: Request) -> Response:
    """Mark a pending/running item as failed (cancels it)."""
    auth = request.headers.get("Authorization")
    if not verify_token(auth):
        return Response(status_code=401)

    from brain.engine.backlog import mark_failed
    found = mark_failed(item_id, error="Cancelled via API")
    if not found:
        return JSONResponse(status_code=404, content={"status": "error", "message": f"Item '{item_id}' not found"})
    return JSONResponse(status_code=200, content={"status": "ok", "id": item_id, "cancelled": True})


# ---------------------------------------------------------------------------
# Heartbeat status endpoint
# ---------------------------------------------------------------------------

@app.get("/heartbeat/status")
async def heartbeat_status(request: Request) -> Response:
    """Return the last heartbeat status report from memory/heartbeat_status.json."""
    auth = request.headers.get("Authorization")
    if not verify_token(auth):
        return Response(status_code=401)

    status_path = WORKSPACE_ROOT / "memory" / "heartbeat_status.json"
    if not status_path.exists():
        return JSONResponse(status_code=200, content={
            "status": "ok",
            "heartbeat": None,
            "message": "Heartbeat has not run yet. Start it with: python -m brain.engine.heartbeat",
        })

    try:
        data = json.loads(status_path.read_text(encoding="utf-8"))
        return JSONResponse(status_code=200, content={"status": "ok", "heartbeat": data})
    except Exception as exc:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(exc)})


@app.post("/heartbeat/beat")
async def heartbeat_beat(request: Request) -> Response:
    """Trigger one manual heartbeat beat immediately (for testing / First Light)."""
    auth = request.headers.get("Authorization")
    if not verify_token(auth):
        return Response(status_code=401)

    loop = asyncio.get_event_loop()
    try:
        from brain.engine.heartbeat import beat
        report = await loop.run_in_executor(None, beat)
        return JSONResponse(status_code=200, content={"status": "ok", "report": report})
    except Exception as exc:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(exc)})

