#!/usr/bin/env bash
# brain/scripts/sanity_check.sh
# Darwin-MCP Self-Healing Sanity Check — runs hourly via crontab.
#
# Three checks:
#   1. Port 8000 responsiveness — restarts darwin.service if dead.
#   2. Stale .git/index.lock files in brain/ and memory/ — removed silently.
#   3. Git submodule sync — pulls latest vault commits from remote.
#
# Exit codes: 0 = all checks passed, 1 = one or more issues found (but fixed).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
LOG_FILE="${REPO_ROOT}/brain/sanity_check.log"
SSE_PORT=8000

log() {
    echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] $*" | tee -a "${LOG_FILE}"
}

ISSUES=0

# ---------------------------------------------------------------------------
# 1. Port check — is the SSE server responding on port 8000?
# ---------------------------------------------------------------------------
log "Checking SSE port ${SSE_PORT}..."
if curl --silent --max-time 5 "http://localhost:${SSE_PORT}/sse" \
   -H "Authorization: Bearer ${MCP_BEARER_TOKEN:-}" \
   -o /dev/null 2>&1; then
    log "Port ${SSE_PORT}: OK"
else
    log "Port ${SSE_PORT}: UNRESPONSIVE — restarting darwin.service"
    systemctl restart darwin.service || true
    ISSUES=$((ISSUES + 1))
fi

# ---------------------------------------------------------------------------
# 2. Stale .git/index.lock files — left by a crashed mid-mutation process
# ---------------------------------------------------------------------------
log "Scanning for stale .git/index.lock files..."
for LOCK_FILE in \
    "${REPO_ROOT}/brain/.git/index.lock" \
    "${REPO_ROOT}/memory/.git/index.lock" \
    "${REPO_ROOT}/.git/index.lock"; do
    if [ -f "${LOCK_FILE}" ]; then
        log "Removing stale lock: ${LOCK_FILE}"
        rm -f "${LOCK_FILE}"
        ISSUES=$((ISSUES + 1))
    fi
done
log "Lock file scan: done"

# ---------------------------------------------------------------------------
# 3. Git submodule sync — ensure Brain hasn't fallen behind the Vault
# ---------------------------------------------------------------------------
log "Syncing git submodules..."
cd "${REPO_ROOT}"
git submodule update --remote --merge 2>&1 | tee -a "${LOG_FILE}" || {
    log "WARNING: git submodule update --remote failed (non-fatal)"
}
log "Submodule sync: done"

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
if [ "${ISSUES}" -gt 0 ]; then
    log "Sanity check completed with ${ISSUES} issue(s) fixed."
    exit 1
else
    log "Sanity check: all clear."
    exit 0
fi
