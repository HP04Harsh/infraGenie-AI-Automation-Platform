#!/usr/bin/env bash
# =============================================================================
# Script:  clear_docker_cache.sh
# Purpose: Clean Docker build cache, unused images, containers, networks,
#          and volumes.
# Supports: Linux (any with Docker Engine)
# Requires: root or docker group membership, Docker installed
# Estimate: 2-10 minutes (depends on amount of data)
# Rollback: N/A (destructive); re-pull images or rebuild as needed.
# =============================================================================

set -euo pipefail

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
err() { log "ERROR: $*" >&2; }
die() { err "$*"; exit 1; }

command -v docker &>/dev/null || die "docker is not installed or not in PATH."

# Verify access
docker info &>/dev/null || die "Cannot connect to Docker daemon. Check permissions."

# ---------------------------------------------------------------------------
# 1. Prune build cache
# ---------------------------------------------------------------------------
log "Pruning Docker build cache..."
docker builder prune -a -f || err "docker builder prune failed"

# ---------------------------------------------------------------------------
# 2. Remove unused images (dangling + unreferenced)
# ---------------------------------------------------------------------------
log "Removing unused Docker images..."
docker image prune -a -f || err "docker image prune failed"

# ---------------------------------------------------------------------------
# 3. Remove stopped containers
# ---------------------------------------------------------------------------
log "Removing stopped containers..."
docker container prune -f || err "docker container prune failed"

# ---------------------------------------------------------------------------
# 4. Remove unused networks
# ---------------------------------------------------------------------------
log "Removing unused networks..."
docker network prune -f || err "docker network prune failed"

# ---------------------------------------------------------------------------
# 5. Remove unused volumes (opt-in — caution)
# ---------------------------------------------------------------------------
log "Removing unused volumes..."
docker volume prune -f || err "docker volume prune failed"

# ---------------------------------------------------------------------------
# 6. Summary
# ---------------------------------------------------------------------------
log "Docker disk usage after cleanup:"
docker system df || true
exit 0
