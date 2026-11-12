#!/bin/sh
# Remove a local installation completely: production, every preview, the factory stack and
# the observability stack, with all their data (databases, backups, the bare repository).
# The development stack (docker compose up) and this checkout are left alone.
# Usage: deploy/uninstall.sh --yes
set -eu
cd "$(dirname "$0")/.."

if [ "${1:-}" != "--yes" ]; then
    echo "This deletes production data, backups and the installation's git repository."
    echo "Run again with --yes to confirm."
    exit 1
fi

for project in $(docker compose ls -a --format json | grep -o '"evolve-\(production\|preview-cr-[0-9]*\|check-[0-9a-f]*\)"' | tr -d '"'); do
    echo "Removing $project"
    docker compose -p "$project" down -v --remove-orphans
done
docker compose -f docker-compose.observability.yml down -v --remove-orphans 2>/dev/null || true
FACTORY_KEY=unused docker compose -f docker-compose.factory.yml down -v --remove-orphans
echo "Uninstalled."
