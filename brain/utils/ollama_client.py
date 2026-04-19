"""Ollama local LLM client — Darwin-MCP.

Wraps the Ollama /api/chat endpoint using meshnet.json config.
Used by the scaffold generator and peer review council.
"""
from __future__ import annotations

import json
import logging
import urllib.request
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "meshnet.json"
_TIMEOUT = 120  # gemma:2b can be slow on first token


def _load_config() -> dict:
    if _CONFIG_PATH.exists():
        try:
            return json.loads(_CONFIG_PATH.read_text())
        except Exception:
            pass
    return {"base_url": "http://127.0.0.1:11434", "model": "gemma:2b"}


def chat(prompt: str, system: str = "", model: Optional[str] = None, timeout: int = _TIMEOUT) -> str:
    """Send a prompt to the local Ollama model. Returns the response text.

    Falls back gracefully to empty string on any error.
    """
    cfg = _load_config()
    base_url = cfg.get("base_url", "http://127.0.0.1:11434").rstrip("/")
    model    = model or cfg.get("model", "gemma:2b")

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = json.dumps({"model": model, "messages": messages, "stream": False}).encode()

    try:
        req = urllib.request.Request(
            f"{base_url}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
        return data["message"]["content"].strip()
    except Exception as exc:
        logger.warning("Ollama chat failed (%s): %s", model, exc)
        return ""
