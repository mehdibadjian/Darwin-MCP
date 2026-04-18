"""SSE Bridge server — US-1, US-2, US-5, US-21, US-32.

Serves the MCP tool list over Server-Sent Events with Bearer token auth.
All operational state is derived exclusively from registry.json.
"""
import hmac
import json
import os
import shutil
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse

from brain.utils.registry import init_registry, read_registry

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
    cleanup_stale_sandboxes()


app = FastAPI(on_startup=[_startup])


@app.get("/sse")
async def sse_endpoint(request: Request) -> Response:
    """Stream the tool list as a single SSE event after auth check."""
    auth = request.headers.get("Authorization")
    if not verify_token(auth):
        return Response(status_code=401)

    registry = read_registry()
    tools = {
        name: entry
        for name, entry in registry["skills"].items()
        if entry.get("status") != "Toxic"
    }

    async def event_stream():
        data = json.dumps({"type": "tool_list", "tools": tools})
        yield f"data: {data}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
