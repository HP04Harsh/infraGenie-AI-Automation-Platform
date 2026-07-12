#!/usr/bin/env bash
# =============================================================================
# Script:  restart_nginx.sh
# Purpose: Test NGINX configuration and restart the service gracefully.
# Supports: Linux (systemd: Debian/Ubuntu, RHEL/CentOS)
# Requires: root (sudo), nginx installed
# Estimate: 10-30 seconds
# Rollback: Re-run script; NGINX reloads previous config on restart.
# =============================================================================

set -euo pipefail

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
err() { log "ERROR: $*" >&2; }
die() { err "$*"; exit 1; }

[[ $EUID -eq 0 ]] || die "This script must be run as root (use sudo)."
command -v nginx &>/dev/null || die "nginx is not installed."
command -v systemctl &>/dev/null || die "systemctl not found — not a systemd system."

# ---------------------------------------------------------------------------
# 1. Test configuration
# ---------------------------------------------------------------------------
log "Testing NGINX configuration..."
nginx -t || die "NGINX configuration test FAILED. Aborting restart."

# ---------------------------------------------------------------------------
# 2. Restart gracefully
# ---------------------------------------------------------------------------
log "Configuration test passed. Restarting NGINX..."
systemctl restart nginx || die "systemctl restart nginx failed."

# ---------------------------------------------------------------------------
# 3. Verify service status
# ---------------------------------------------------------------------------
sleep 2
if systemctl is-active --quiet nginx; then
    log "NGINX restarted and is active."
else
    die "NGINX failed to start after restart."
fi
exit 0
