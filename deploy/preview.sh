#!/bin/sh
# Start, update or remove the disposable copy of the app for one change request.
# Usage: deploy/preview.sh up <request-id> <source-dir> <sha>   (prints the URL on the last line)
#        deploy/preview.sh down <request-id>
set -eu
here="$(dirname "$0")"
. "$here/lib.sh"
action="$1"; id="$2"
project="evolve-preview-cr-$id"
port=$(( PREVIEW_PORT_BASE + id % 100 ))

case "$action" in
    up)
        src="$3"; sha="$4"
        log "Starting preview $project on port $port"
        IMAGE_TAG="$sha" WEB_PORT="$port" docker compose -p "$project" \
            -f "$src/docker-compose.yml" -f "$src/deploy/compose.preview.yml" \
            up -d --no-build --remove-orphans --wait
        "$here/smoke.sh" "$project" "$sha"
        echo "http://${PUBLIC_HOST:-localhost}:$port"
        ;;
    down)
        log "Removing preview $project"
        docker compose -p "$project" down -v --remove-orphans
        ;;
    *) echo "unknown action: $action"; exit 2 ;;
esac
