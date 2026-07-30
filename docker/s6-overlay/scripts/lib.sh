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

# Fatal. A oneshot exiting non-zero fails the s6-rc transition, and
# S6_BEHAVIOUR_IF_STAGE2_FAILS=2 turns that into a container exit, so the
# restart policy can retry instead of leaving a half-started container up.
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

# Populate a caller-provided array with the opentelemetry-instrument wrapper
# argv tokens for service "$2", or leave it empty if OTEL is disabled or the
# wrapper binary is missing. Use "${arr[@]}" to exec directly, or
# "${arr[*]@Q}" to embed as a shell-quoted prefix string.
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

# s6-supervise starts each service in its own session, so the service pid
# doubles as its process group id. Record it while the cwd is still the
# servicedir, so ./finish can sweep the group once the service dies. Call this
# from a run script before it changes directory or execs.
record_process_group() {
	mkdir -p /run/romm
	echo "$$" >"/run/romm/$(basename "${PWD}").pgid"
}

# Leave this longrun down for the lifetime of the container. Used by services
# that configuration switches off: s6 has no conditional services, so they
# start, opt out, and tell the supervisor not to bring them back.
disable_service() {
	s6-svc -O .
	exit 0
}
