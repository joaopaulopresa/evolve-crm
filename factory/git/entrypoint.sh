#!/bin/sh
set -eu
repo=/srv/git/repo.git

if [ ! -d "$repo" ]; then
    git init -q --bare -b main "$repo"
fi
git config --system --add safe.directory '*'
git -C "$repo" config core.hooksPath /hooks
git -C "$repo" config receive.advertisePushOptions true
git -C "$repo" config receive.denyDeleteCurrent true

exec git daemon --reuseaddr --base-path=/srv/git --export-all --enable=receive-pack \
    --informative-errors /srv/git
