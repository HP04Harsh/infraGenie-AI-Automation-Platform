#!/usr/bin/env bash
# =============================================================================
# Script:  disk_cleanup.sh
# Purpose: Clean up disk space by removing apt cache, old logs, and
#          temporary files.
# Supports: Linux (Debian/Ubuntu, RHEL/CentOS)
# Requires: root (sudo), 100 MB free space for safe operation
# Estimate: 2-5 minutes
# Rollback: N/A (destructive); logs cleaned cannot be recovered.
# =============================================================================

set -euo pipefail

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
err() { log "ERROR: $*" >&2; }
die() { err "$*"; exit 1; }

# Must be root
[[ $EUID -eq 0 ]] || die "This script must be run as root (use sudo)."

# ---------------------------------------------------------------------------
# 1. APT / YUM / DNF cache clean
# ---------------------------------------------------------------------------
if command -v apt-get &>/dev/null; then
    log "Cleaning apt cache..."
    apt-get clean -y || err "apt-get clean failed"
    apt-get autoclean -y || err "apt-get autoclean failed"
    apt-get autoremove -y || err "apt-get autoremove failed"
elif command -v yum &>/dev/null; then
    log "Cleaning yum cache..."
    yum clean all || err "yum clean all failed"
elif command -v dnf &>/dev/null; then
    log "Cleaning dnf cache..."
    dnf clean all || err "dnf clean all failed"
fi

# ---------------------------------------------------------------------------
# 2. Old log files (/var/log — rotate / compress, remove .gz older than 30d)
# ---------------------------------------------------------------------------
log "Removing rotated log archives older than 30 days..."
find /var/log -type f \( -name '*.gz' -o -name '*.old' -o -name '*.1' \) -mtime +30 -delete 2>/dev/null || true

# ---------------------------------------------------------------------------
# 3. Temporary files
# ---------------------------------------------------------------------------
log "Cleaning /tmp..."
find /tmp -type f -atime +7 -delete 2>/dev/null || true
find /tmp -type d -empty -delete 2>/dev/null || true

log "Cleaning /var/tmp..."
find /var/tmp -type f -atime +7 -delete 2>/dev/null || true
find /var/tmp -type d -empty -delete 2>/dev/null || true

# ---------------------------------------------------------------------------
# 4. Journal logs older than 7 days (if journalctl available)
# ---------------------------------------------------------------------------
if command -v journalctl &>/dev/null; then
    log "Rotating journal logs older than 7 days..."
    journalctl --vacuum-time=7d 2>/dev/null || err "journalctl vacuum failed"
fi

# ---------------------------------------------------------------------------
# 5. Summary
# ---------------------------------------------------------------------------
log "Disk usage after cleanup:"
df -h / || true
exit 0
