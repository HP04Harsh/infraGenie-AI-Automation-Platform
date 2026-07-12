#!/usr/bin/env bash
# =============================================================================
# Script:  update_packages.sh
# Purpose: Safely update all system packages. Performs a dry-run first,
#          then applies updates, and logs changes.
# Supports: Linux (Debian/Ubuntu with apt, RHEL/CentOS with yum/dnf)
# Requires: root (sudo)
# Estimate: 5-20 minutes (depends on number of packages)
# Rollback: Downgrade individual packages via apt/yum history if needed.
# =============================================================================

set -euo pipefail

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
err() { log "ERROR: $*" >&2; }
die() { err "$*"; exit 1; }

[[ $EUID -eq 0 ]] || die "This script must be run as root (use sudo)."

# ---------------------------------------------------------------------------
# 1. Determine package manager and update cache
# ---------------------------------------------------------------------------
if command -v apt-get &>/dev/null; then
    PM="apt-get"
    log "Updating package cache (apt update)..."
    apt-get update -y || die "apt update failed."
elif command -v dnf &>/dev/null; then
    PM="dnf"
    log "Updating package cache (dnf check-update)..."
    dnf check-update || true  # exit code 100 means updates available
elif command -v yum &>/dev/null; then
    PM="yum"
    log "Updating package cache (yum check-update)..."
    yum check-update || true
else
    die "No supported package manager found (apt-get, dnf, yum)."
fi

# ---------------------------------------------------------------------------
# 2. Dry-run to preview changes
# ---------------------------------------------------------------------------
log "Performing dry-run upgrade..."
case "$PM" in
    apt-get)
        apt-get upgrade --dry-run || err "apt-get dry-run failed."
        ;;
    dnf)
        dnf upgrade --assumeno || true
        ;;
    yum)
        yum update --assumeno || true
        ;;
esac

# ---------------------------------------------------------------------------
# 3. Prompt before applying
# ---------------------------------------------------------------------------
read -p "Apply updates now? [y/N] " answer
case "$answer" in
    [Yy]*) ;;
    *) log "Updates deferred by user."; exit 0 ;;
esac

# ---------------------------------------------------------------------------
# 4. Apply updates
# ---------------------------------------------------------------------------
log "Applying package updates..."
case "$PM" in
    apt-get)
        apt-get upgrade -y || die "apt-get upgrade failed."
        apt-get autoremove -y || err "apt-get autoremove failed."
        ;;
    dnf)
        dnf upgrade -y || die "dnf upgrade failed."
        ;;
    yum)
        yum update -y || die "yum update failed."
        ;;
esac

log "Package updates completed."
exit 0
