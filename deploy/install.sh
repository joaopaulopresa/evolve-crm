#!/bin/sh
# Install Evolve CRM in local delivery mode on this machine:
#   1. generate the factory key (first run only)
#   2. start the factory stack (git server and deployer)
#   3. push this checkout to the factory's repository; the deployer builds it and deploys
#      production
# Run it again after pulling a new version of Evolve CRM to update the installation. If the
# installation has changes of its own (merged change requests), merge them into this checkout
# first: git pull git://127.0.0.1:9418/repo.git main. FORCE=1 overwrites them instead.
set -eu
cd "$(dirname "$0")/.."

[ -f .env ] || cp .env.example .env
# Secrets shared between the CRM API, the deployer, the git hooks, the agents and crm-data.
[ -z "$(tail -c1 .env)" ] || echo >> .env
for name in FACTORY_KEY HERMES_BUILDER_KEY HERMES_ANALYST_KEY CRM_DATA_MCP_KEY CRM_DATA_CONTEXT_KEY; do
    grep -q "^$name=" .env || printf '%s=%s\n' "$name" "$(openssl rand -hex 24)" >> .env
done
set -a; . ./.env; set +a
if [ -z "${OPENROUTER_API_KEY:-}" ]; then
    echo "Note: OPENROUTER_API_KEY is empty in .env. The CRM will run, but the Implement and"
    echo "Ask pages need it. Add the key and run this script again."
fi

# The repository and the deployer first: the push below is what the deployer deploys.
docker compose -f docker-compose.factory.yml up -d --build --wait git deployer

remote="git://127.0.0.1:${GIT_PORT:-9418}/repo.git"
echo "Pushing $(git rev-parse --short HEAD) to $remote"
git push ${FORCE:+--force} -o "operator-key=$FACTORY_KEY" "$remote" HEAD:refs/heads/main

# The agents start after the push, so the builder finds a repository to clone.
docker compose -f docker-compose.factory.yml up -d --build --wait

echo
echo "The deployer is now building and deploying production."
echo "  Follow it:   docker compose -f docker-compose.factory.yml logs -f deployer"
echo "  Production:  http://localhost:${PRODUCTION_PORT:-8100}"
