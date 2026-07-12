#!/usr/bin/env bash
# =============================================================================
# Script:  clean_journal_logs.sh
# Purpose: Clean up journald logs older than 7 days to reclaim disk space.
# Supports: Linux (systemd with journald)
# Requires: root (sudo), journalctl available
# Estimate: 10-30 seconds
# Rollback: N/A (destructive); journal logs older than 7 days are removed.
# =============================================================================

set -euo pipefail

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
err() { log "ERROR: $*" >&2; }
die() { err "$*"; exit 1; }

[[ $EUID -eq 0 ]] || die "This script must be run as root (use sudo)."
command -v journalctl &>/dev/null || die "journalctl is not available (not a systemd system)."

# ---------------------------------------------------------------------------
# 1. Show current journal disk usage
# ---------------------------------------------------------------------------
log "Current journal disk usage:"
journalctl --disk-usage || err "Unable to query journal disk usage."

# ---------------------------------------------------------------------------
# 2. Vacuum logs older than 7 days
# ---------------------------------------------------------------------------
log "Vacuuming journal logs older than 7 days..."
journalctl --vacuum-time=7d || die "journalctl --vacuum-time=7d failed."

# ---------------------------------------------------------------------------
# 3. Show reclaimed disk usage
# ---------------------------------------------------------------------------
log "Journal disk usage after cleanup:"
journalctl --disk-usage || true
exit 0
