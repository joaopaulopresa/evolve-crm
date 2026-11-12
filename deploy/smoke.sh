#!/bin/sh
# Smoke test a running stack: the web proxy answers, the API reaches its database, and the
# release it reports is the one that was deployed.
# Usage: deploy/smoke.sh <compose-project> <sha>
set -eu
. "$(dirname "$0")/lib.sh"
project="$1"; sha="$2"

wait_for_release "$project" "$sha" "${SMOKE_TIMEOUT:-120}"
docker compose -p "$project" exec -T web wget -qO- http://localhost/ | grep -q '<div id="root">'
log "Smoke test passed: $project serves release $sha"
