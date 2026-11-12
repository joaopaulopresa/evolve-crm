#!/bin/sh
# Build the API and web images for one commit, tagged with its SHA.
# Usage: deploy/build.sh <source-dir> <sha>
set -eu
. "$(dirname "$0")/lib.sh"
src="$1"; sha="$2"

log "Building images for $sha"
docker build -q -t "evolve-crm-api:$sha" -f "$src/api/Dockerfile" "$src"
docker build -q -t "evolve-crm-web:$sha" "$src/web"
docker build -q -t "evolve-crm-backup:$sha" "$src/backup"
