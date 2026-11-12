#!/bin/sh
# Deploy one commit to a persistent environment and smoke test it. The images must already
# exist (deploy/build.sh). The API container applies pending migrations when it starts.
# Usage: deploy/deploy.sh <environment> <source-dir> <sha>
set -eu
here="$(dirname "$0")"
. "$here/lib.sh"
environment="$1"; src="$2"; sha="$3"
project="$(project_name "$environment")"
env_file="$STATE_DIR/$environment.env"

if [ ! -f "$env_file" ]; then
    log "First deploy of $environment: generating its secrets in $env_file"
    umask 077
    {
        echo "POSTGRES_PASSWORD=$(openssl rand -hex 24)"
        echo "SECRET_KEY=$(openssl rand -hex 32)"
        echo "ADMIN_PASSWORD=${ADMIN_PASSWORD:-admin123}"
        echo "SEED_DEMO_DATA=${SEED_DEMO_DATA:-true}"
    } > "$env_file"
fi

case "$environment" in
    production) port="$PRODUCTION_PORT" ;;
    *) echo "unknown environment: $environment"; exit 2 ;;
esac

log "Deploying $sha to $environment (port $port)"
IMAGE_TAG="$sha" WEB_PORT="$port" docker compose -p "$project" --env-file "$env_file" \
    -f "$src/docker-compose.yml" -f "$src/deploy/compose.$environment.yml" \
    up -d --no-build --remove-orphans --wait

"$here/smoke.sh" "$project" "$sha"
