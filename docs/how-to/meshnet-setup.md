# How-To: Meshnet Setup (Gemma 2b on Phone ↔ Darwin-MCP on PC)

This guide walks through connecting Gemma 2b running on your phone to Darwin-MCP
on your PC over **NordVPN Meshnet** — no cloud, no API costs.

---

## Prerequisites

| Item | Details |
|------|---------|
| Phone | Android or iOS with [MLC-LLM](https://github.com/mlc-ai/mlc-llm) or [Layla](https://getlayla.app) installed |
| PC | Darwin-MCP running (`uvicorn brain.bridge.sse_server:app`) |
| NordVPN | Account with Meshnet enabled on both devices |
| Gemma 2b | Downloaded model weights (available via MLC-LLM model hub) |

---

## Step 1 — Enable NordVPN Meshnet

1. Open NordVPN on your **phone** → Settings → Meshnet → Enable
2. Open NordVPN on your **PC** → Settings → Meshnet → Enable
3. In the Meshnet device list, find your PC and **allow traffic routing**
4. Note your PC's Meshnet IP — it looks like `100.x.x.x`

---

## Step 2 — Run Darwin-MCP on Your PC

```bash
# In the mcp-evolution-core directory
export MCP_BEARER_TOKEN="your-secret-token"
uvicorn brain.bridge.sse_server:app --host 0.0.0.0 --port 8080
```

Verify it's reachable from the PC itself:
```bash
curl http://localhost:8080/sse -H "Authorization: Bearer your-secret-token"
```

---

## Step 3 — Configure the Meshnet Bridge

Edit `brain/config/meshnet.json` with your PC's Meshnet IP:

```json
{
  "base_url": "http://100.x.x.x:8080",
  "model": "gemma-2b",
  "bearer_token_env": "MCP_BEARER_TOKEN",
  "notes": "Replace 100.x.x.x with your PC's NordVPN Meshnet IP"
}
```

> **Security:** The bearer token is read from the `MCP_BEARER_TOKEN` environment
> variable on Darwin — never hardcode it in the config file.

---

## Step 4 — Start Gemma 2b on Your Phone

### Option A: MLC-LLM
1. Install the MLC-LLM app from the [releases page](https://github.com/mlc-ai/mlc-llm/releases)
2. Download the `gemma-2b-it-q4f16_1` model
3. Enable **Local API Server** in settings — default port `8080`
4. Set the system prompt by pasting the contents of `brain/prompts/system_prompt.txt`
   followed by `brain/prompts/golden_log.txt`

### Option B: Layla
1. Install Layla from the App Store / Play Store
2. Load Gemma 2b from the model library
3. In **MCP Settings**, set the server URL to `http://100.x.x.x:8080`
   (your PC's Meshnet IP) and paste your bearer token

---

## Step 5 — Verify the Connection

From your phone's browser or terminal app, test:

```
GET http://100.x.x.x:8080/sse
Authorization: Bearer your-secret-token
```

You should receive an SSE stream starting with a `tool_list` event.

---

## Step 6 — Inject the Golden Log

Before your first real query, prepend `brain/prompts/golden_log.txt` to the
conversation context. This is the **few-shot primer** that teaches Gemma 2b
the exact `<thought>/<call>/<answer>` pattern Darwin expects.

In MLC-LLM, paste it as the first **user** message before sending anything else.
In Layla, use the "System Prompt" field.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `Connection refused` on phone | Check Darwin is bound to `0.0.0.0`, not `127.0.0.1` |
| `401 Unauthorized` | Verify bearer token matches `MCP_BEARER_TOKEN` env var |
| Meshnet IP unreachable | Ensure both devices are on the same Meshnet and traffic routing is allowed |
| Gemma outputs raw JSON (no XML tags) | Re-inject `system_prompt.txt` — the model dropped its context |
| Tool call syntax errors | Gemma dropped its context. Re-inject `golden_log.txt` |
| Slow responses | Enable Flash Summarizer — large web pages may be saturating Gemma's context |

---

## Related Documents

- [Cloud-less AI Plan](../reference/cloudless-ai-plan.md) — Full architecture and design decisions
- [Common Tasks](common-tasks.md) — General Darwin-MCP operations
