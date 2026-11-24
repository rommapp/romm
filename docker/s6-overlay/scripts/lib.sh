#!/usr/bin/env bash
# Shared helpers for the s6-rc service scripts. Sourced, never executed.
# Callers set ROMM_LOG_TAG before sourcing to label their log lines.

LOGLEVEL="${LOGLEVEL:="INFO"}"
ROMM_LOG_TAG="${ROMM_LOG_TAG:="init"}"

# logger colors
RED='\033[0;31m'
LIGHTMAGENTA='\033[0;95m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
RESET='\033[0;00m'

_log() {
	local level_color=$1 level_text=$2
	shift 2
	echo -e "${level_color}${level_text}${BLUE}[RomM]${LIGHTMAGENTA}[${ROMM_LOG_TAG}]${CYAN}[$(date +"%Y-%m-%d %T")]${RESET}" "${@}" || true
}

debug_log() {
	if [[ ${LOGLEVEL^^} == "DEBUG" ]]; then
		_log "${LIGHTMAGENTA}" "DEBUG:    " "${@}"
	fi
}

info_log() {
	_log "${GREEN}" "INFO:     " "${@}"
}

warn_log() {
	_log "${YELLOW}" "WARNING:  " "${@}"
}

# Fatal: S6_BEHAVIOUR_IF_STAGE2_FAILS=2 turns a failed oneshot into a container
# exit, so the restart policy retries instead of leaving it half-started.
error_log() {
	_log "${RED}" "ERROR:    " "${@}"
	exit 1
}

print_banner() {
	local version
	version=$(python3 -c "exec(open('/backend/__version__.py').read()); print(__version__)")
	info_log "               _____                 __  __ "
	info_log '              |  __ \               |  \/  |'
	info_log '              | |__) |___  _ __ ___ | \  / |'
	info_log "              |  _  // _ \\| '_ \` _ \\| |\\/| |"
	info_log '              | | \ \ (_) | | | | | | |  | |'
	info_log '              |_|  \_\___/|_| |_| |_|_|  |_|'
	info_log ""
	info_log "The beautiful, powerful, self-hosted Rom manager and player"
	info_log ""
	info_log "Version: ${version}"
	info_log ""
}

# Fill array "$1" with the opentelemetry-instrument prefix for service "$2", or
# leave it empty when OTEL is off. Embed it in a command string with "${arr[*]@Q}".
otel_prefix() {
	local -n out_arr="$1"
	if [[ ${OTEL_SDK_DISABLED:-false} == "true" ]]; then return 0; fi
	if ! command -v opentelemetry-instrument >/dev/null 2>&1; then
		warn_log "opentelemetry-instrument not found, starting $2 without OpenTelemetry instrumentation"
		return 0
	fi
	# shellcheck disable=SC2034  # nameref binds out_arr to caller variable
	out_arr=(opentelemetry-instrument --service_name "${OTEL_SERVICE_NAME_PREFIX-}$2")
}

# Poll a TCP port until it accepts a connection. Returns non-zero on timeout.
wait_for_tcp() {
	local host=$1 port=$2 timeout_seconds=$3
	local retries=$((timeout_seconds * 2))
	while ((retries > 0)); do
		if (echo >"/dev/tcp/${host}/${port}") 2>/dev/null; then
			return 0
		fi
		sleep 0.5
		retries=$((retries - 1))
	done
	return 1
}

# s6-supervise gives each service its own session, so its pid is the group id
# ./finish sweeps. Call before the run script changes directory or execs.
record_process_group() {
	mkdir -p /run/romm
	echo "$$" >"/run/romm/$(basename "${PWD}").pgid"
}

# s6-rc has no conditional services, so one that configuration switches off
# starts, then tells its supervisor not to bring it back.
disable_service() {
	s6-svc -O .
	exit 0
}

# The values the backend's safe_str_to_bool reads as true, matched lowercased.
is_truthy() {
	[[ ${1,,} =~ ^(1|true|yes|on)$ ]]
}

# The URL carries the password, so callers pass it through RQ_REDIS_URL rather
# than --url, which would put it on a world-readable command line.
build_redis_url() {
	local scheme="redis" userinfo=""

	if is_truthy "${REDIS_SSL-}"; then
		scheme="rediss"
	fi

	if [[ -n ${REDIS_PASSWORD-} ]]; then
		userinfo="${REDIS_USERNAME-}:${REDIS_PASSWORD}@"
	elif [[ -n ${REDIS_USERNAME-} ]]; then
		userinfo="${REDIS_USERNAME}@"
	fi

	echo "${scheme}://${userinfo}${REDIS_HOST:-127.0.0.1}:${REDIS_PORT:-6379}/${REDIS_DB:-0}"
}

# Exec an RQ worker of class "$1" on the queues that follow. --with-scheduler
# releases delayed jobs, which is how the watcher's rescans wait out their delay.
exec_rq_worker() {
	local worker_class="$1"
	shift

	RQ_REDIS_URL="$(build_redis_url)"
	export RQ_REDIS_URL
	export PYTHONPATH="/backend:${PYTHONPATH-}"

	exec rq worker \
		--path /backend \
		--worker-class "handler.rq_worker.${worker_class}" \
		--connection-class handler.redis_handler.RomMRedis \
		--results-ttl "${TASK_RESULT_TTL:-86400}" \
		--logging_level "${LOGLEVEL}" \
		--with-scheduler \
		"$@"
}
