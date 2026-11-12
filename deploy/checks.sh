#!/bin/sh
# Everything a change must pass before anyone looks at it: protected paths, migration safety,
# lint and tests for the API (against a throwaway PostgreSQL) and for the web app.
# Usage: GIT_DIR=/path/to/repo.git deploy/checks.sh <source-dir> <base-sha> <sha>
set -eu
here="$(dirname "$0")"
. "$here/lib.sh"
src="$1"; base="$2"; sha="$3"
project="evolve-check-$(echo "$sha" | cut -c1-10)"

"$here/check_paths.sh" "$base" "$sha"
"$here/check_migrations.py" "$base" "$sha"

"$here/build.sh" "$src" "$sha"

cleanup() { docker compose -p "$project" -f "$src/docker-compose.yml" down -v --remove-orphans >/dev/null 2>&1 || true; }
trap cleanup EXIT
export IMAGE_TAG="$sha" SEED_DEMO_DATA=false

log "API: lint and tests"
docker compose -p "$project" -f "$src/docker-compose.yml" up -d --wait db >/dev/null 2>&1
docker compose -p "$project" -f "$src/docker-compose.yml" run --rm --no-deps -T api \
    sh -c "ruff check . && ruff format --check . && pytest -q -p no:cacheprovider"

log "Web: type check and tests"
docker build -q --target test "$src/web" >/dev/null || {
    # Build again without -q so the failing test output is shown.
    docker build --progress=plain --target test "$src/web" 2>&1 | tail -60
    exit 1
}
log "All checks passed for $sha"
