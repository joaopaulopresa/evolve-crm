#!/bin/sh
# Usage:
#   backup.sh schedule         run "now" on BACKUP_CRON (the container's default command)
#   backup.sh now [label]      back up the database and the git history once. With a label
#                              (deploy.sh passes "before-<sha>") the files go under releases/
#                              and are kept; without it they expire after RETENTION_DAYS.
#   backup.sh list             list stored backups
#
# Objects in the bucket:
#   db/<environment>/<timestamp>.dump      pg_dump custom format
#   git/<timestamp>.bundle                 git bundle with every branch and tag
#   releases/<label>/db.dump, repo.bundle  taken before a production deploy, never expired
set -eu

bucket="s3/${S3_BUCKET:-evolve-backups}"
environment="${ENVIRONMENT:-development}"

connect() {
    mc alias set s3 "$S3_ENDPOINT" "$S3_ACCESS_KEY" "$S3_SECRET_KEY" >/dev/null
    mc mb --ignore-existing "$bucket" >/dev/null
}

apply_retention() {
    days="${RETENTION_DAYS:-30}"
    cat > /tmp/lifecycle.json <<JSON
{"Rules": [
  {"ID": "expire-db", "Status": "Enabled", "Filter": {"Prefix": "db/"}, "Expiration": {"Days": $days}},
  {"ID": "expire-git", "Status": "Enabled", "Filter": {"Prefix": "git/"}, "Expiration": {"Days": $days}}
]}
JSON
    mc ilm rule import "$bucket" < /tmp/lifecycle.json >/dev/null
}

backup_database() { # <object key>
    pg_dump --format=custom --no-owner "$PGURL" | mc pipe "$bucket/$1" >/dev/null
    echo "database -> $1"
}

backup_git() { # <object key>
    source="${GIT_SOURCE:-}"
    case "$source" in
        "") echo "git: GIT_SOURCE is not set, skipped"; return 0 ;;
        /*)
            if [ ! -d "$source" ] || [ -z "$(git --git-dir="$source" for-each-ref | head -1)" ]; then
                echo "git: no repository with commits at $source, skipped"; return 0
            fi
            repo="$source" ;;
        *)  # A remote (GitHub mode): bundle a fresh mirror clone.
            repo=/tmp/mirror.git
            rm -rf "$repo"
            git clone -q --mirror "$source" "$repo" ;;
    esac
    git --git-dir="$repo" bundle create -q /tmp/repo.bundle --all
    mc cp -q /tmp/repo.bundle "$bucket/$1" >/dev/null
    rm -f /tmp/repo.bundle
    echo "git -> $1"
}

now() {
    connect
    stamp="$(date -u +%Y%m%dT%H%M%SZ)"
    if [ -n "${1:-}" ]; then
        backup_database "releases/$1/db.dump"
        backup_git "releases/$1/repo.bundle"
    else
        backup_database "db/$environment/$stamp.dump"
        backup_git "git/$stamp.bundle"
    fi
    echo "Backup finished at $stamp"
}

case "${1:-schedule}" in
    schedule)
        connect
        apply_retention
        echo "${BACKUP_CRON:-0 */6 * * *} /usr/local/bin/backup.sh now" > /tmp/crontab
        echo "Backups scheduled: ${BACKUP_CRON:-0 */6 * * *} (retention ${RETENTION_DAYS:-30} days)"
        exec "$(command -v supercronic)" -quiet /tmp/crontab
        ;;
    now) now "${2:-}" ;;
    list) connect; mc ls --recursive "$bucket" ;;
    *) echo "unknown command: $1"; exit 2 ;;
esac
