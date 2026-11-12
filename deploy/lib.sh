# Shared by the deploy scripts. Source it: . "$(dirname "$0")/lib.sh"

STATE_DIR="${STATE_DIR:-/state}"
PRODUCTION_PORT="${PRODUCTION_PORT:-8100}"
PREVIEW_PORT_BASE="${PREVIEW_PORT_BASE:-8200}"

log() { echo "[$(date +%H:%M:%S)] $*"; }

project_name() { # <environment>
    echo "evolve-$1"
}

# Wait until the stack answers through its web proxy and reports the expected release.
wait_for_release() { # <compose project> <sha> [seconds]
    project="$1"; sha="$2"; deadline=$(( $(date +%s) + ${3:-120} ))
    while [ "$(date +%s)" -lt "$deadline" ]; do
        health=$(docker compose -p "$project" exec -T web wget -qO- http://localhost/api/health 2>/dev/null || true)
        case "$health" in
            *'"status":"ok"'*"\"release\":\"$sha\""*) return 0 ;;
        esac
        sleep 2
    done
    echo "Timed out waiting for release $sha in $project. Last answer: ${health:-none}"
    return 1
}
