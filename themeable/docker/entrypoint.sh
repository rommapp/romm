#!/bin/sh
# Compiles the theme packs, then hands over to RomM's own entrypoint unchanged.
# A failure here never blocks RomM: without a build the loader is missing and
# the browser simply shows RomM's default look.
if ! node /themeable/scripts/runtime.mjs >/dev/null; then
	echo "themeable: theme packs could not be compiled; RomM starts with its default look (details in ${THEMEABLE_RUNTIME_DIR:-/tmp/themeable}/status.json)" >&2
fi
exec /docker-entrypoint.sh "$@"
