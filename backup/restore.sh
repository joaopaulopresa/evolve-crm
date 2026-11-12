#!/bin/sh
# Usage (inside the backup container: docker compose run --rm --entrypoint restore.sh backup ...):
#   restore.sh db <object>               replace the database content with a dump, for example
#                                        restore.sh db releases/before-<sha>/db.dump
#   restore.sh git <object> <directory>  recreate a bare repository from a bundle
# List the available objects with: backup.sh list
set -eu
bucket="s3/${S3_BUCKET:-evolve-backups}"
mc alias set s3 "$S3_ENDPOINT" "$S3_ACCESS_KEY" "$S3_SECRET_KEY" >/dev/null

case "${1:-}" in
    db)
        mc cat "$bucket/$2" > /tmp/restore.dump
        pg_restore --clean --if-exists --no-owner --single-transaction --dbname "$PGURL" /tmp/restore.dump
        rm -f /tmp/restore.dump
        echo "Database restored from $2"
        ;;
    git)
        mc cp -q "$bucket/$2" /tmp/restore.bundle >/dev/null
        git clone -q --mirror /tmp/restore.bundle "$3"
        rm -f /tmp/restore.bundle
        echo "Repository restored from $2 into $3"
        ;;
    *) sed -n '2,7p' "$0"; exit 2 ;;
esac
