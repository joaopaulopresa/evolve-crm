#!/bin/sh
# Install Evolve CRM in local delivery mode on this machine:
#   1. generate the factory key (first run only)
#   2. start the factory stack (git server and deployer)
#   3. push this checkout to the factory's repository; the deployer builds it and deploys
#      production
# Run it again after pulling a new version of Evolve CRM to update the installation.
set -eu
cd "$(dirname "$0")/.."

[ -f .env ] || cp .env.example .env
if ! grep -q '^FACTORY_KEY=' .env; then
    printf '\n# Shared secret between the CRM API, the deployer and the git hooks.\nFACTORY_KEY=%s\n' \
        "$(openssl rand -hex 24)" >> .env
fi
set -a; . ./.env; set +a

docker compose -f docker-compose.factory.yml up -d --build --wait

remote="git://127.0.0.1:${GIT_PORT:-9418}/repo.git"
echo "Pushing $(git rev-parse --short HEAD) to $remote"
git push -o "operator-key=$FACTORY_KEY" "$remote" HEAD:refs/heads/main

echo
echo "The deployer is now building and deploying production."
echo "  Follow it:   docker compose -f docker-compose.factory.yml logs -f deployer"
echo "  Production:  http://localhost:${PRODUCTION_PORT:-8100}"
