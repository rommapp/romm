#!/usr/bin/env bash
# Starts the bundled PostgreSQL, seeds a dummy library on first boot, then hands
# over to the regular entrypoint.

set -o errexit
set -o nounset
set -o pipefail

PGDATA="${PGDATA:-/var/lib/postgresql/data}"
PREVIEW_ROMS="${PREVIEW_ROMS:-500}"
PREVIEW_SEED="${PREVIEW_SEED:-1337}"
PREVIEW_PASSWORD="${PREVIEW_PASSWORD:-password}"
# Any password works over loopback trust auth, but the backend requires one.
export DB_PASSWD="${DB_PASSWD:-romm}"
# Migrations and the seed run before /init, which would otherwise generate this.
if [[ -z ${ROMM_AUTH_SECRET_KEY-} ]]; then
	ROMM_AUTH_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
	export ROMM_AUTH_SECRET_KEY
fi
seeded_marker="${PGDATA}/.romm-preview-seeded"

log() {
	local now
	now=$(date +"%Y-%m-%d %T")
	echo "INFO:     [RomM][preview][${now}] $*"
}

as_postgres() {
	su postgres -s /bin/sh -c "$1"
}

mkdir -p "${PGDATA}" /run/postgresql
chown postgres:postgres "${PGDATA}" /run/postgresql

if [[ ! -s "${PGDATA}/PG_VERSION" ]]; then
	log "Initialising PostgreSQL"
	# Trust auth is safe here: the server only listens on loopback.
	as_postgres "initdb --auth=trust --username=postgres --encoding=UTF8 -D '${PGDATA}'" >/dev/null
fi

log "Starting PostgreSQL"
as_postgres "pg_ctl -D '${PGDATA}' -o \"-c listen_addresses=127.0.0.1 -c shared_buffers=64MB\" -l /tmp/postgres.log -w start" >/dev/null

if [[ ! -f ${seeded_marker} ]]; then
	as_postgres "createuser '${DB_USER}'"
	as_postgres "createdb -O '${DB_USER}' '${DB_NAME}'"

	log "Running database migrations"
	(cd /backend && alembic upgrade head)

	log "Seeding ${PREVIEW_ROMS} dummy roms"
	mkdir -p "${ROMM_BASE_PATH:-/romm}/resources"
	# shellcheck disable=SC2086 # PREVIEW_SEED_ARGS is a list of extra flags
	(cd /backend && python3 tools/generate_test_data.py \
		--roms "${PREVIEW_ROMS}" \
		--seed "${PREVIEW_SEED}" \
		--password "${PREVIEW_PASSWORD}" \
		--users 4 \
		--collections 10 \
		--play-sessions 1000 \
		--image-fidelity 2 \
		--image-workers 2 \
		${PREVIEW_SEED_ARGS:-})
	touch "${seeded_marker}"
fi

exec /docker-entrypoint.sh "$@"
