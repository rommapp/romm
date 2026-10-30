#!/bin/sh
# Compiles the theme packs, then hands over to RomM's own entrypoint unchanged.
# A failure never blocks RomM: without a build the browser shows RomM's default look.

# nginx's links are fixed at /tmp/themeable, so a custom THEMEABLE_RUNTIME_DIR is linked
# there (/tmp is writable by any user, unlike the web root).
WEB_RUNTIME_DIR=/tmp/themeable
runtime_dir=${THEMEABLE_RUNTIME_DIR:-$WEB_RUNTIME_DIR}
if [ "$runtime_dir" != "$WEB_RUNTIME_DIR" ]; then
	if mkdir -p "$runtime_dir" 2>/dev/null && runtime_dir=$(cd "$runtime_dir" && pwd -P) &&
		{ [ "$runtime_dir" = "$WEB_RUNTIME_DIR" ] || {
			{ [ ! -e "$WEB_RUNTIME_DIR" ] || [ -L "$WEB_RUNTIME_DIR" ] || rm -rf "$WEB_RUNTIME_DIR"; } &&
				ln -sfn "$runtime_dir" "$WEB_RUNTIME_DIR"
		}; } 2>/dev/null; then
		:
	else
		echo "themeable: THEMEABLE_RUNTIME_DIR=$THEMEABLE_RUNTIME_DIR can't be used, so $WEB_RUNTIME_DIR is used instead" >&2
		runtime_dir=$WEB_RUNTIME_DIR
	fi
fi
export THEMEABLE_RUNTIME_DIR="$runtime_dir"

if ! node /themeable/scripts/runtime.mjs >/dev/null; then
	echo "themeable: theme packs could not be compiled; RomM starts with its default look (details in $THEMEABLE_RUNTIME_DIR/status.json)" >&2
fi
exec /docker-entrypoint.sh "$@"
