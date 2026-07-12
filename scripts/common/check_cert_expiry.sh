#!/usr/bin/env bash
# =============================================================================
# Script:  check_cert_expiry.sh
# Purpose: Check SSL certificate expiry dates for given domains. Reports
#          days remaining and flags certificates expiring within 30 days.
# Supports: Linux, macOS (with openssl)
# Requires: openssl
# Estimate: 5-15 seconds per domain
# Rollback: N/A (read-only diagnostic).
# =============================================================================

set -euo pipefail

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
err() { log "ERROR: $*" >&2; }
die() { err "$*"; exit 1; }

WARN_DAYS=${WARN_DAYS:-30}

usage() {
    cat <<EOF
Usage: $0 [domain1 domain2 ...]
If no domains are provided, a default list is tested.

Environment:
  WARN_DAYS   Days threshold for warning (default: 30)
EOF
    exit 1
}

command -v openssl &>/dev/null || die "openssl is required but not installed."

# Default domains if none provided
if [[ $# -eq 0 ]]; then
    set -- "management.azure.com" "login.microsoftonline.com" \
           "storage.azure.com" "database.windows.net" \
           "github.com" "google.com"
fi

EXIT_CODE=0

check_cert() {
    local domain="$1"
    local port="${2:-443}"

    log "Checking $domain:$port ..."

    local cert_info
    cert_info=$(timeout 10 openssl s_client -connect "${domain}:${port}" \
        -servername "$domain" </dev/null 2>/dev/null) || {
        err "Failed to connect to $domain:$port"
        return 1
    }

    local expiry_date
    expiry_date=$(echo "$cert_info" | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2-) || {
        err "Failed to parse certificate for $domain"
        return 1
    }

    if [[ -z "$expiry_date" ]]; then
        err "No certificate returned for $domain"
        return 1
    fi

    local expiry_epoch
    expiry_epoch=$(date -d "$expiry_date" +%s 2>/dev/null) || {
        # macOS compatibility
        expiry_epoch=$(date -j -f "%b %d %T %Y %Z" "$expiry_date" +%s 2>/dev/null) || {
            err "Cannot parse expiry date: $expiry_date"
            return 1
        }
    }

    local now_epoch
    now_epoch=$(date +%s)
    local diff_days=$(( (expiry_epoch - now_epoch) / 86400 ))

    if [[ $diff_days -le 0 ]]; then
        err "EXPIRED  $domain — expired ${diff_days} days ago"
        EXIT_CODE=1
    elif [[ $diff_days -le $WARN_DAYS ]]; then
        err "WARNING  $domain — expires in ${diff_days} days (≤ ${WARN_DAYS})"
        EXIT_CODE=1
    else
        log "OK       $domain — expires in ${diff_days} days"
    fi
}

for domain in "$@"; do
    check_cert "$domain" || true
done

log "Certificate check complete."
exit $EXIT_CODE
