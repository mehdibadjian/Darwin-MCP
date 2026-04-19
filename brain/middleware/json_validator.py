"""JSON Validator Middleware — Cloud-less AI plan, Phase 2a.

FastAPI middleware that intercepts malformed JSON request bodies before they
reach /evolve or /search, and returns a machine-readable retry_hint so that
Gemma 2b can self-correct without human intervention.
"""
from __future__ import annotations

import json
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


# Endpoints that must receive valid JSON bodies.
_JSON_REQUIRED_PATHS = {"/evolve", "/search"}


class JSONValidatorMiddleware(BaseHTTPMiddleware):
    """Catch invalid JSON on guarded POST endpoints.

    On a ``json.JSONDecodeError``:
    - Returns HTTP 422 immediately.
    - Includes ``retry_hint`` with the expected schema for the endpoint.
    - The upstream route handler is never called.

    On valid JSON the request passes through unchanged.
    """

    _SCHEMAS: dict[str, dict] = {
        "/evolve": {
            "name": "<skill_name>",
            "code": "<python source code string>",
            "tests": "<pytest source code string>",
            "requirements": ["<optional pip package>"],
        },
        "/search": {
            "query": "<search query string>",
            "fetch": False,
            "max_results": 5,
        },
    }

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.method == "POST" and request.url.path in _JSON_REQUIRED_PATHS:
            body = await request.body()

            if body:
                try:
                    json.loads(body)
                except json.JSONDecodeError as exc:
                    schema = self._SCHEMAS.get(request.url.path, {})
                    return JSONResponse(
                        status_code=422,
                        content={
                            "status": "error",
                            "message": f"Invalid JSON in request body: {exc.msg} (line {exc.lineno}, col {exc.colno}).",
                            "retry_hint": (
                                f"Retry using this exact schema for {request.url.path}: "
                                + json.dumps(schema)
                            ),
                        },
                    )

            # Re-attach the body so the route handler can read it.
            async def receive():
                return {"type": "http.request", "body": body, "more_body": False}

            request._receive = receive  # noqa: SLF001

        return await call_next(request)


def validate_json_body(body: bytes, path: str) -> tuple[bool, dict | None]:
    """Standalone validator for use outside middleware (e.g. tests).

    Returns (is_valid, error_response_dict).
    ``error_response_dict`` is None when the body is valid.
    """
    if not body:
        return True, None
    try:
        json.loads(body)
        return True, None
    except json.JSONDecodeError as exc:
        schema = JSONValidatorMiddleware._SCHEMAS.get(path, {})
        return False, {
            "status": "error",
            "message": f"Invalid JSON: {exc.msg} (line {exc.lineno}, col {exc.colno}).",
            "retry_hint": f"Retry using this exact schema for {path}: " + json.dumps(schema),
        }
