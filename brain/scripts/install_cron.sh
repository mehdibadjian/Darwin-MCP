#!/usr/bin/env bash
# brain/scripts/install_cron.sh
# Installs the Darwin-MCP sanity_check.sh as an hourly crontab entry.
#
# Usage:  bash brain/scripts/install_cron.sh
# Safe to run multiple times — idempotent (won't add duplicate entries).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SANITY_SCRIPT="${SCRIPT_DIR}/sanity_check.sh"

# Ensure the script is executable
chmod +x "${SANITY_SCRIPT}"

CRON_ENTRY="0 * * * * ${SANITY_SCRIPT} >> /var/log/darwin_sanity.log 2>&1"

# Add only if not already present
( crontab -l 2>/dev/null | grep -qF "${SANITY_SCRIPT}" ) && {
    echo "Crontab entry already installed — skipping."
    exit 0
}

( crontab -l 2>/dev/null; echo "${CRON_ENTRY}" ) | crontab -
echo "Installed hourly cron: ${CRON_ENTRY}"
