#!/usr/bin/env bash
# brain/scripts/install_heartbeat.sh
#
# Installs the Darwin-MCP Autonomous Heartbeat as a persistent background
# process on either:
#   a) A Linux Droplet  → systemd user service  (preferred)
#   b) macOS dev machine → launchd plist         (preferred)
#   c) Any POSIX system  → crontab fallback
#
# Usage:
#   bash brain/scripts/install_heartbeat.sh [--interval SECONDS] [--uninstall]
#
# Environment variables respected by the heartbeat itself (set in .env or
# export before running):
#   DARWIN_HEARTBEAT_INTERVAL   Seconds between beats     (default 600)
#   DARWIN_CPU_EVOLVE           CPU% ceiling for evolve   (default 40)
#   DARWIN_CPU_MEDIUM           CPU% ceiling for prune    (default 60)
#   DARWIN_CPU_SAMPLE_COUNT     Multi-sample count        (default 2)
#   MCP_BEARER_TOKEN            Auth token for /evolve    (required)

set -euo pipefail

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
PYTHON="${PYTHON:-$(command -v python3)}"
INTERVAL="${DARWIN_HEARTBEAT_INTERVAL:-600}"
SERVICE_NAME="darwin-heartbeat"
LOG_FILE="/var/log/darwin_heartbeat.log"

# ── Flags ─────────────────────────────────────────────────────────────────────
UNINSTALL=false
for arg in "$@"; do
  case "$arg" in
    --uninstall) UNINSTALL=true ;;
    --interval)  shift; INTERVAL="${1:-600}" ;;
  esac
done

# ── Helpers ───────────────────────────────────────────────────────────────────
log()  { echo "[darwin-heartbeat] $*"; }
warn() { echo "[darwin-heartbeat] WARNING: $*" >&2; }

# ── Uninstall ─────────────────────────────────────────────────────────────────
if [[ "${UNINSTALL}" == "true" ]]; then
  log "Uninstalling heartbeat..."

  if command -v systemctl &>/dev/null && systemctl --user is-enabled "${SERVICE_NAME}" &>/dev/null; then
    systemctl --user stop    "${SERVICE_NAME}" || true
    systemctl --user disable "${SERVICE_NAME}" || true
    rm -f "${HOME}/.config/systemd/user/${SERVICE_NAME}.service"
    systemctl --user daemon-reload
    log "Removed systemd user service."
  fi

  PLIST="${HOME}/Library/LaunchAgents/com.darwin.heartbeat.plist"
  if [[ -f "${PLIST}" ]]; then
    launchctl unload "${PLIST}" 2>/dev/null || true
    rm -f "${PLIST}"
    log "Removed launchd plist."
  fi

  # Remove crontab entry if present
  ( crontab -l 2>/dev/null | grep -v "brain.engine.heartbeat" ) | crontab - || true
  log "Removed crontab entry (if any)."
  log "Uninstall complete."
  exit 0
fi

# ── Validate Python ───────────────────────────────────────────────────────────
log "Using Python: ${PYTHON} ($(${PYTHON} --version 2>&1))"
if ! "${PYTHON}" -c "import brain.engine.heartbeat" 2>/dev/null; then
  warn "Cannot import brain.engine.heartbeat — ensure you run from the repo root"
  warn "and that dependencies are installed (pip install -r memory/requirements.txt)"
  exit 1
fi

# ── systemd (Linux Droplet) ───────────────────────────────────────────────────
if command -v systemctl &>/dev/null && [[ "$(uname -s)" == "Linux" ]]; then
  UNIT_DIR="${HOME}/.config/systemd/user"
  mkdir -p "${UNIT_DIR}"
  UNIT_FILE="${UNIT_DIR}/${SERVICE_NAME}.service"

  cat > "${UNIT_FILE}" << EOF
[Unit]
Description=Darwin-MCP Autonomous Heartbeat
After=network.target

[Service]
Type=simple
WorkingDirectory=${REPO_ROOT}
ExecStart=${PYTHON} -m brain.engine.heartbeat --interval ${INTERVAL}
Restart=on-failure
RestartSec=30
StandardOutput=append:${LOG_FILE}
StandardError=append:${LOG_FILE}
Environment=DARWIN_HEARTBEAT_INTERVAL=${INTERVAL}
Environment=DARWIN_CPU_EVOLVE=${DARWIN_CPU_EVOLVE:-40}
Environment=DARWIN_CPU_MEDIUM=${DARWIN_CPU_MEDIUM:-60}

[Install]
WantedBy=default.target
EOF

  systemctl --user daemon-reload
  systemctl --user enable  "${SERVICE_NAME}"
  systemctl --user restart "${SERVICE_NAME}"
  log "Installed and started systemd user service '${SERVICE_NAME}'."
  log "Logs: journalctl --user -u ${SERVICE_NAME} -f"
  log "      or: tail -f ${LOG_FILE}"
  exit 0
fi

# ── launchd (macOS) ───────────────────────────────────────────────────────────
if [[ "$(uname -s)" == "Darwin" ]]; then
  PLIST_DIR="${HOME}/Library/LaunchAgents"
  mkdir -p "${PLIST_DIR}"
  PLIST="${PLIST_DIR}/com.darwin.heartbeat.plist"

  cat > "${PLIST}" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>             <string>com.darwin.heartbeat</string>
  <key>ProgramArguments</key>
  <array>
    <string>${PYTHON}</string>
    <string>-m</string>
    <string>brain.engine.heartbeat</string>
    <string>--interval</string>
    <string>${INTERVAL}</string>
  </array>
  <key>WorkingDirectory</key>  <string>${REPO_ROOT}</string>
  <key>RunAtLoad</key>         <true/>
  <key>KeepAlive</key>         <true/>
  <key>StandardOutPath</key>   <string>${HOME}/Library/Logs/darwin_heartbeat.log</string>
  <key>StandardErrorPath</key> <string>${HOME}/Library/Logs/darwin_heartbeat.log</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>DARWIN_HEARTBEAT_INTERVAL</key> <string>${INTERVAL}</string>
    <key>DARWIN_CPU_EVOLVE</key>         <string>${DARWIN_CPU_EVOLVE:-40}</string>
    <key>DARWIN_CPU_MEDIUM</key>         <string>${DARWIN_CPU_MEDIUM:-60}</string>
  </dict>
</dict>
</plist>
EOF

  launchctl unload "${PLIST}" 2>/dev/null || true
  launchctl load   "${PLIST}"
  log "Installed launchd agent: com.darwin.heartbeat"
  log "Logs: tail -f ~/Library/Logs/darwin_heartbeat.log"
  exit 0
fi

# ── Crontab fallback (any POSIX) ──────────────────────────────────────────────
CMD="cd ${REPO_ROOT} && ${PYTHON} -m brain.engine.heartbeat --once >> /tmp/darwin_heartbeat.log 2>&1"

( crontab -l 2>/dev/null | grep -qF "brain.engine.heartbeat" ) && {
  log "Crontab entry already installed — skipping."
  exit 0
}

CRON_INTERVAL_MIN=$(( INTERVAL / 60 ))
CRON_INTERVAL_MIN=$(( CRON_INTERVAL_MIN < 1 ? 1 : CRON_INTERVAL_MIN ))
CRON_ENTRY="*/${CRON_INTERVAL_MIN} * * * * ${CMD}"

( crontab -l 2>/dev/null; echo "${CRON_ENTRY}" ) | crontab -
log "Installed crontab entry: runs every ${CRON_INTERVAL_MIN} min."
log "Log: tail -f /tmp/darwin_heartbeat.log"
