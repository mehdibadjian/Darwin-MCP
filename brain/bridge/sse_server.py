"""SSE Bridge server — US-1, US-2, US-5, US-21, US-28, US-29, US-32.

Serves the MCP tool list over Server-Sent Events with Bearer token auth.
All operational state is derived exclusively from registry.json.
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
from brain.utils.registry import discover_species, init_registry, read_registry
from brain.utils.web_fetch import fetch_url, fetch_urls, search_web
from brain.watcher.hot_reload import (
    flush_queued_notifications,
    register_sse_callback,
    start_watcher,
    unregister_sse_callback,
)

# Token is always sourced from the environment — never hardcoded.
MCP_BEARER_TOKEN: str = os.environ.get("MCP_BEARER_TOKEN", "")


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


def _startup() -> None:
    init_registry()
    discover_species()
    cleanup_stale_sandboxes()
    start_watcher()


app = FastAPI(on_startup=[_startup])


@app.get("/sse")
async def sse_endpoint(request: Request) -> Response:
    """Stream tool list and list_changed notifications over SSE after auth check."""
    auth = request.headers.get("Authorization")
    if not verify_token(auth):
        return Response(status_code=401)

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
            registry = read_registry()
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

    registry = read_registry()
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
            # Merge snippet + fetched text
            for sr in search_results:
                match = next((p for p in pages if p["url"] == sr.get("url")), None)
                if match and match.get("status") == "ok":
                    sr["text"] = match["text"]

        return JSONResponse(status_code=200, content={
            "status": "ok",
            "mode": "search+fetch" if do_fetch else "search",
            "query": query,
            "results": search_results,
        })

    return JSONResponse(status_code=422, content={"status": "error", "message": "Provide 'urls' or 'query'"})
