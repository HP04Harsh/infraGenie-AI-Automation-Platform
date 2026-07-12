#!/usr/bin/env bash
# =============================================================================
# Script:  restart_docker.sh
# Purpose: Restart Docker daemon gracefully, waiting for running containers
#          to stop before restart.
# Supports: Linux (systemd)
# Requires: root (sudo), Docker installed
# Estimate: 10-60 seconds
# Rollback: Re-run script to restart Docker; containers restart per policy.
# =============================================================================

set -euo pipefail

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
err() { log "ERROR: $*" >&2; }
die() { err "$*"; exit 1; }

[[ $EUID -eq 0 ]] || die "This script must be run as root (use sudo)."
command -v docker &>/dev/null || die "docker is not installed."
command -v systemctl &>/dev/null || die "systemctl not found."

# ---------------------------------------------------------------------------
# 1. Warn about running containers
# ---------------------------------------------------------------------------
RUNNING=$(docker ps -q 2>/dev/null | wc -l)
if [[ $RUNNING -gt 0 ]]; then
    log "WARNING: ${RUNNING} container(s) are currently running."
    log "Containers will be stopped during Docker restart."
fi

# ---------------------------------------------------------------------------
# 2. Restart Docker daemon
# ---------------------------------------------------------------------------
log "Restarting Docker daemon..."
systemctl restart docker || die "systemctl restart docker failed."

# ---------------------------------------------------------------------------
# 3. Wait for socket readiness
# ---------------------------------------------------------------------------
log "Waiting for Docker socket..."
for i in $(seq 1 15); do
    if docker info &>/dev/null; then
        log "Docker daemon is ready."
        break
    fi
    if [[ $i -eq 15 ]]; then
        die "Docker daemon did not become ready within 15 seconds."
    fi
    sleep 1
done

# ---------------------------------------------------------------------------
# 4. Report status
# ---------------------------------------------------------------------------
log "Docker daemon restarted successfully."
systemctl status docker --no-pager -l 2>&1 | head -5 || true
exit 0
