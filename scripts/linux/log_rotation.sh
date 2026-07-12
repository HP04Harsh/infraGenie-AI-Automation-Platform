#!/usr/bin/env bash
# =============================================================================
# Script:  log_rotation.sh
# Purpose: Rotate and compress system logs under /var/log using logrotate
#          or manual fallback.
# Supports: Linux (Debian/Ubuntu, RHEL/CentOS)
# Requires: root (sudo)
# Estimate: 1-3 minutes
# Rollback: N/A (destructive); re-run after rotation cannot be undone.
# =============================================================================

set -euo pipefail

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
err() { log "ERROR: $*" >&2; }
die() { err "$*"; exit 1; }

[[ $EUID -eq 0 ]] || die "This script must be run as root (use sudo)."

# ---------------------------------------------------------------------------
# 1. Use logrotate if available
# ---------------------------------------------------------------------------
if command -v logrotate &>/dev/null; then
    log "Running logrotate (global)..."
    if [[ -f /etc/logrotate.conf ]]; then
        logrotate -f /etc/logrotate.conf || err "logrotate exited with non-zero status"
    else
        err "/etc/logrotate.conf not found"
    fi
else
    log "logrotate not installed; performing manual rotation..."
fi

# ---------------------------------------------------------------------------
# 2. Manual fallback: compress logs not yet compressed
# ---------------------------------------------------------------------------
log "Compressing uncompressed log files older than 1 day..."
find /var/log -type f -name '*.log' -mtime +1 ! -name '*.gz' -exec gzip -9 {} \; 2>/dev/null || true

# ---------------------------------------------------------------------------
# 3. Remove compressed logs older than 90 days
# ---------------------------------------------------------------------------
log "Removing compressed logs older than 90 days..."
find /var/log -type f -name '*.gz' -mtime +90 -delete 2>/dev/null || true

# ---------------------------------------------------------------------------
# 4. Report current disk usage for /var/log
# ---------------------------------------------------------------------------
log "Disk usage of /var/log:"
du -sh /var/log || true
exit 0
