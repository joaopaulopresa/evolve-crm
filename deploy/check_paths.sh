#!/bin/sh
# Fail when the commits between BASE and HEAD change a protected path.
# Usage: GIT_DIR=/path/to/repo.git deploy/check_paths.sh <base-sha> <head-sha> [patterns-file]
set -eu
base="$1"
head="$2"
patterns="${3:-$(dirname "$0")/protected-paths.txt}"

set --
while IFS= read -r line; do
    case "$line" in ''|'#'*) continue ;; esac
    set -- "$@" ":(glob)$line"
done < "$patterns"

changed=$(git diff --name-only "$base" "$head" -- "$@")
if [ -n "$changed" ]; then
    echo "Protected paths were changed:"
    echo "$changed" | sed 's/^/  /'
    exit 1
fi
echo "Protected paths: untouched."
