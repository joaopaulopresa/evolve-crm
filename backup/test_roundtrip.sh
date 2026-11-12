#!/bin/sh
# Round-trip test of backup and restore, in a throwaway copy of the stack:
#   database: seed, dump, wipe, restore, compare row counts
#   git:      bundle a repository, restore it, compare HEAD
# Usage: backup/test_roundtrip.sh        (needs Docker; takes about a minute)
set -eu
cd "$(dirname "$0")/.."
project="evolve-backup-test"
compose="docker compose -p $project -f docker-compose.yml"
export IMAGE_TAG="${IMAGE_TAG:-dev}" SEED_DEMO_DATA=false

cleanup() { $compose down -v --remove-orphans >/dev/null 2>&1 || true; }
trap cleanup EXIT
cleanup

$compose build -q api backup
$compose up -d --wait db minio >/dev/null 2>&1
$compose run --rm -T --no-deps api sh -c "python -m app.migrate && python -m app.seed" >/dev/null 2>&1

$compose run --rm -T --no-deps --entrypoint sh backup -s <<'INNER'
set -eu
counts() {
    psql "$PGURL" -Atc "SELECT (SELECT count(*) FROM companies) || ' companies, ' ||
        (SELECT count(*) FROM contacts) || ' contacts, ' || (SELECT count(*) FROM deals) ||
        ' deals, ' || (SELECT count(*) FROM activities) || ' activities'"
}

git init -q --bare -b main /tmp/source.git
git init -q -b main /tmp/work && cd /tmp/work
git -c user.name=Test -c user.email=test@example.test commit -q --allow-empty -m "first"
git -c user.name=Test -c user.email=test@example.test commit -q --allow-empty -m "second"
git push -q /tmp/source.git main
git tag v1 && git push -q /tmp/source.git v1
cd /

before="$(counts)"
head_before="$(git --git-dir=/tmp/source.git rev-parse HEAD)"
echo "before:   $before, HEAD $head_before"

GIT_SOURCE=/tmp/source.git backup.sh now roundtrip

psql "$PGURL" -qc "DROP SCHEMA public CASCADE; CREATE SCHEMA public;" 2>/dev/null
wiped="$(psql "$PGURL" -Atc "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'")"
echo "wiped:    $wiped tables left"
[ "$wiped" = "0" ]

restore.sh db releases/roundtrip/db.dump
restore.sh git releases/roundtrip/repo.bundle /tmp/restored.git

after="$(counts)"
head_after="$(git --git-dir=/tmp/restored.git rev-parse HEAD)"
tag_after="$(git --git-dir=/tmp/restored.git tag)"
echo "restored: $after, HEAD $head_after, tag $tag_after"

[ "$before" = "$after" ] || { echo "FAIL: row counts differ"; exit 1; }
[ "$head_before" = "$head_after" ] || { echo "FAIL: HEAD differs"; exit 1; }
[ "$tag_after" = "v1" ] || { echo "FAIL: tag missing"; exit 1; }
echo "PASS: database and git history survive a backup and restore"
INNER
