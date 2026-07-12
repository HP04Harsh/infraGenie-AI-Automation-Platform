#!/usr/bin/env bash
# =============================================================================
# Script:  test_connectivity.sh
# Purpose: Test network connectivity to common Azure endpoints
#          (management, storage, SQL, service bus, etc.)
# Supports: Linux, macOS (with bash, curl, nc)
# Requires: curl, nc (netcat), openssl
# Estimate: 10-30 seconds
# Rollback: N/A (read-only diagnostic).
# =============================================================================

set -euo pipefail

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
err() { log "ERROR: $*" >&2; }
die() { err "$*"; exit 1; }

# ---------------------------------------------------------------------------
# Azure endpoints to test
# ---------------------------------------------------------------------------
ENDPOINTS=(
    "management.azure.com:443"
    "login.microsoftonline.com:443"
    "storage.azure.com:443"
    "*.blob.core.windows.net:443"
    "*.queue.core.windows.net:443"
    "*.table.core.windows.net:443"
    "database.windows.net:443"
    "*.servicebus.windows.net:443"
    "*.azureedge.net:443"
    "aka.ms:443"
)

PASS=0
FAIL=0
TOTAL=${#ENDPOINTS[@]}

log "Connectivity test to Azure endpoints started."
echo "--------------------------------------------------------"

for entry in "${ENDPOINTS[@]}"; do
    host="${entry%%:*}"
    port="${entry##*:}"

    # Resolve hostname first
    if host "$host" &>/dev/null; then
        :
    elif nslookup "$host" &>/dev/null; then
        :
    else
        err "DNS resolution failed for $host"
        ((FAIL++)) || true
        continue
    fi

    # TCP connectivity check (5 second timeout)
    if timeout 5 bash -c "echo > /dev/tcp/$host/$port" 2>/dev/null; then
        log "OK    $host:$port"
        ((PASS++)) || true
    elif nc -zvw5 "$host" "$port" 2>/dev/null; then
        log "OK    $host:$port (via nc)"
        ((PASS++)) || true
    else
        err "FAIL  $host:$port — unreachable"
        ((FAIL++)) || true
    fi
done

echo "--------------------------------------------------------"
log "Results: ${PASS}/${TOTAL} passed, ${FAIL}/${TOTAL} failed."

[[ $FAIL -eq 0 ]] || die "Some connectivity checks failed."
exit 0
