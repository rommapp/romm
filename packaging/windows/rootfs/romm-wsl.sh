#!/usr/bin/env bash
# Foreground launcher for the RomM WSL distro: starts MariaDB, mounts the
# Windows library folder, then runs the image's entrypoint. RomM.ps1 keeps
# this process attached to wsl.exe so WSL doesn't idle the distro out.
#
# Usage: romm-wsl <path to romm.env, as a Windows or WSL path>

set -o errexit
set -o nounset
set -o pipefail

PID_FILE=/run/romm-wsl.pid

# Status and stop live here so RomM.ps1 never passes quoted shell to wsl.exe,
# which Windows PowerShell 5.1 mangles.
case "${1:-}" in
--running)
	[[ -f ${PID_FILE} ]] || exit 1
	pid=$(cat "${PID_FILE}")
	kill -0 "${pid}" 2>/dev/null
	exit
	;;
--stop)
	[[ -f ${PID_FILE} ]] || exit 0
	pid=$(cat "${PID_FILE}")
	kill -TERM "${pid}" 2>/dev/null || exit 0
	while kill -0 "${pid}" 2>/dev/null; do sleep 0.5; done
	exit 0
	;;
*) ;;
esac

SETTINGS_FILE="${1:-}"
SECRETS_FILE=/etc/romm/secrets.env
DB_DATA_DIR=/var/lib/mysql
LOG_DIR=/var/log/romm

mkdir -p "${LOG_DIR}"
# shellcheck disable=SC2312  # tee's exit status is irrelevant
exec > >(tee -a "${LOG_DIR}/romm.log") 2>&1

log() { printf '[romm-wsl][%(%Y-%m-%d %T)T] %s\n' -1 "$*"; }

# shellcheck source=/dev/null
source /etc/romm/image.env

if [[ -n ${SETTINGS_FILE} ]]; then
	[[ ${SETTINGS_FILE} == *:\\* ]] && SETTINGS_FILE=$(wslpath -u "${SETTINGS_FILE}")
	# romm.env is written on Windows, so strip CRLF before sourcing it.
	settings=$(tr -d '\r' <"${SETTINGS_FILE}")
	set -o allexport
	eval "${settings}"
	set +o allexport
fi

if [[ ! -f ${SECRETS_FILE} ]]; then
	log "First boot, generating secrets"
	auth_key=$(python3 -c 'import secrets; print(secrets.token_hex(32))')
	db_passwd=$(python3 -c 'import secrets; print(secrets.token_hex(24))')
	umask 077
	printf 'ROMM_AUTH_SECRET_KEY=%s\nDB_PASSWD=%s\n' "${auth_key}" "${db_passwd}" >"${SECRETS_FILE}"
	umask 022
fi
set -o allexport
# shellcheck source=/dev/null
source "${SECRETS_FILE}"
set +o allexport

export DB_HOST=127.0.0.1 DB_PORT=3306 DB_NAME=romm DB_USER=romm ROMM_DB_DRIVER=mariadb

mount_library() {
	local win_path="${ROMM_LIBRARY_PATH:-}"
	mkdir -p /romm/library
	# A previous run's mount makes wslpath resolve the drive path to /romm/library itself.
	while mountpoint -q /romm/library; do umount /romm/library; done
	if [[ -z ${win_path} ]]; then
		log "ROMM_LIBRARY_PATH is not set, using the empty library inside the distro"
		return
	fi
	local src
	src=$(wslpath -u "${win_path}")
	if [[ ! -d ${src} || ${src} == /romm/library* ]]; then
		log "Library folder ${win_path} (${src}) does not exist"
		exit 1
	fi
	mount --bind "${src}" /romm/library
	log "Mounted ${win_path} at /romm/library"
}

start_mariadb() {
	mkdir -p /run/mysqld
	chown mysql:mysql /run/mysqld
	if [[ ! -d ${DB_DATA_DIR}/mysql ]]; then
		log "Initializing MariaDB data directory"
		mariadb-install-db --user=mysql --datadir="${DB_DATA_DIR}" --skip-test-db </dev/null >/dev/null
	fi

	mariadbd --user=mysql --datadir="${DB_DATA_DIR}" \
		--skip-networking=0 --bind-address=127.0.0.1 --port=3306 \
		--socket=/run/mysqld/mysqld.sock &
	MARIADB_PID=$!

	for _ in $(seq 1 60); do
		mariadb-admin --socket=/run/mysqld/mysqld.sock ping >/dev/null 2>&1 && break
		sleep 0.5
	done
	mariadb-admin --socket=/run/mysqld/mysqld.sock ping >/dev/null 2>&1 || {
		log "MariaDB did not start"
		exit 1
	}

	# shellcheck disable=SC2153  # DB_PASSWD comes from the secrets file
	mariadb --socket=/run/mysqld/mysqld.sock <<-SQL
		CREATE DATABASE IF NOT EXISTS romm;
		CREATE USER IF NOT EXISTS 'romm'@'127.0.0.1' IDENTIFIED BY '${DB_PASSWD}';
		ALTER USER 'romm'@'127.0.0.1' IDENTIFIED BY '${DB_PASSWD}';
		GRANT ALL PRIVILEGES ON romm.* TO 'romm'@'127.0.0.1';
	SQL
}

stop_all() {
	log "Stopping RomM"
	[[ -n ${INIT_PID:-} ]] && kill -TERM "${INIT_PID}" 2>/dev/null && wait "${INIT_PID}" || true
	if [[ -n ${MARIADB_PID:-} ]]; then
		mariadb-admin --socket=/run/mysqld/mysqld.sock shutdown 2>/dev/null || kill -TERM "${MARIADB_PID}" || true
		wait "${MARIADB_PID}" || true
	fi
	log "Stopped"
}

echo $$ >"${PID_FILE}"
trap 'stop_all; exit 0' SIGINT SIGTERM

mount_library
start_mariadb

log "Starting RomM on port ${ROMM_PORT:-8080}"
/docker-entrypoint.sh /usr/local/bin/romm-init &
INIT_PID=$!
wait "${INIT_PID}" || true
stop_all
