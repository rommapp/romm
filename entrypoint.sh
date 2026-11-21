#!/bin/bash

set -e

echo "Starting entrypoint script..."

# Create symlinks for frontend
if [[ -L /app/frontend/assets/romm/resources ]]; then
	target=$(readlink "/app/frontend/assets/romm/resources")

	# If the target is not the same as ${ROMM_BASE_PATH}/resources, recreate the symbolic link.
	if [[ ${target} != "${ROMM_BASE_PATH}/resources" ]]; then
		rm "/app/frontend/assets/romm/resources"
		ln -s "${ROMM_BASE_PATH}/resources" "/app/frontend/assets/romm/resources"
	fi
elif [[ ! -e /app/frontend/assets/romm/resources ]]; then
	# Ensure parent directory exists before creating symbolic link
	mkdir -p "/app/frontend/assets/romm"
	ln -s "${ROMM_BASE_PATH}/resources" "/app/frontend/assets/romm/resources"
fi

# The ./frontend bind mount hides whatever the build wrote under /app/frontend,
# so link the image's emulator runtimes into the tree the dev server serves.
if [[ -n ${EMULATOR_ASSETS_DIR-} && -d ${EMULATOR_ASSETS_DIR} ]]; then
	for runtime_dir in "${EMULATOR_ASSETS_DIR}"/*; do
		target="/app/frontend/assets/$(basename "${runtime_dir}")"
		mkdir -p "${target}"
		for entry in "${runtime_dir}"/*; do
			link="${target}/$(basename "${entry}")"
			# Never replace checked-in art that shares a name with a runtime file.
			if [[ -e ${link} && ! -L ${link} ]]; then
				continue
			fi
			ln -sfn "${entry}" "${link}"
		done
	done
fi

# The backend reads the free RTP where the full image keeps it.
if [[ -n ${EMULATOR_ASSETS_DIR-} && -d ${EMULATOR_ASSETS_DIR}/easyrpg/rtp ]]; then
	mkdir -p /var/www/html/assets/easyrpg
	ln -sfn "${EMULATOR_ASSETS_DIR}/easyrpg/rtp" /var/www/html/assets/easyrpg/rtp
fi

# Define a signal handler to propagate termination signals
function handle_termination() {
	echo "Terminating child processes..."
	# Kill all background jobs
	# trunk-ignore(shellcheck)
	kill -TERM $(jobs -p) 2>/dev/null
}

# Trap SIGTERM and SIGINT signals
trap handle_termination SIGTERM SIGINT

# Set ROMM_AUTH_SECRET_KEY if not already set
if [[ -z ${ROMM_AUTH_SECRET_KEY-} ]]; then
	ROMM_AUTH_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
	export ROMM_AUTH_SECRET_KEY
fi

# Mirrors otel_prefix in docker/init_scripts/init: instrument only when an
# OTEL_ variable is set and the SDK isn't disabled.
otel_enabled="false"
if printenv | grep -q '^OTEL_' && [[ ${OTEL_SDK_DISABLED:-false} != "true" ]]; then
	otel_enabled="true"
	# Same defaults as docker/init_scripts/init.
	export OTEL_PYTHON_SYSTEM_METRICS_EXCLUDED_METRICS="${OTEL_PYTHON_SYSTEM_METRICS_EXCLUDED_METRICS:-system.*,process.runtime.*}"
	export OTEL_EXPERIMENTAL_RESOURCE_DETECTORS="${OTEL_EXPERIMENTAL_RESOURCE_DETECTORS:-otel,process}"
fi

# Fill array "$1" with the opentelemetry-instrument argv for service "$2", or
# leave it empty when OTel is off.
otel_prefix() {
	local -n out_arr="$1"
	if [[ ${otel_enabled} != "true" ]]; then return 0; fi
	# shellcheck disable=SC2034  # nameref binds out_arr to caller variable
	out_arr=(opentelemetry-instrument --service_name "${OTEL_SERVICE_NAME_PREFIX-}$2")
}

# REDIS_SSL is a boolean to the app, so "false" and "0" mean plaintext.
build_redis_url() {
	local scheme="redis" userinfo=""
	case "${REDIS_SSL,,}" in
	1 | true | yes | on) scheme="rediss" ;;
	*) ;;
	esac
	if [[ -n ${REDIS_PASSWORD-} ]]; then
		userinfo="${REDIS_USERNAME-}:${REDIS_PASSWORD}@"
	elif [[ -n ${REDIS_USERNAME-} ]]; then
		userinfo="${REDIS_USERNAME}@"
	fi
	echo "${scheme}://${userinfo}${REDIS_HOST:-127.0.0.1}:${REDIS_PORT:-6379}/${REDIS_DB:-0}"
}

start_backend() {
	local -a wrap=()
	otel_prefix wrap api
	if [[ ${DEV_MODE:-false} == "true" ]]; then
		echo "Starting backend under debugpy on :5678..."
		# Add --wait-for-client after --listen to pause until VSCode attaches.
		uv run "${wrap[@]}" python -m debugpy --listen 0.0.0.0:5678 main.py &
	else
		echo "Starting backend..."
		uv run "${wrap[@]}" python main.py &
	fi
}

# The URL carries the password, so it goes through RQ_REDIS_URL rather than
# --url, which would put it on a world-readable command line.
start_rq_cron() {
	local -a wrap=()
	otel_prefix wrap rq_cron
	echo "Starting RQ cron scheduler..."
	PYTHONPATH="/app/backend:${PYTHONPATH-}" \
		RQ_REDIS_URL="${REDIS_URL}" \
		"${wrap[@]}" rq cron \
		--path /app/backend \
		--logging-level "${LOGLEVEL:-INFO}" \
		tasks.cron_config &
}

# Use a worker class that drops the noisy per-sweep "cleaning registries for
# queue" log line. The maintenance interval keeps its default (~10 min) so
# orphaned STARTED jobs and stale workers are still pruned promptly.
# --with-scheduler releases delayed jobs, which is how the watcher's rescans
# wait out their delay.
start_rq_worker() {
	local name="$1" worker_class="$2"
	shift 2
	local -a wrap=()
	otel_prefix wrap "${name}"
	echo "Starting ${name}..."
	PYTHONPATH="/app/backend:${PYTHONPATH-}" \
		RQ_REDIS_URL="${REDIS_URL}" \
		"${wrap[@]}" rq worker \
		--path /app/backend \
		--worker-class "handler.rq_worker.${worker_class}" \
		--pid "/tmp/${name}.pid" \
		--logging_level "${LOGLEVEL:-INFO}" \
		--with-scheduler \
		"$@" &
}

# Rerun backend script "$2" whenever directory "$3" changes, as service "$1".
start_watcher() {
	local service="$1" script="$2" dir="$3"
	local -a wrap=()
	otel_prefix wrap "${service}"
	echo "Starting ${service}..."
	watchfiles --target-type command "uv run ${wrap[*]@Q} python ${script}" "${dir}" &
}

# Read before the backend starts: its startup can rewrite config.yml.
streaming_worker_enabled="false"
if (cd /app/backend && uv run python -c "
import sys
from config.config_manager import config_manager
sys.exit(0 if config_manager.get_config().STREAMING_ENABLED else 1)
" >/dev/null 2>&1); then
	streaming_worker_enabled="true"
fi

REDIS_URL="$(build_redis_url)"

# Backend services run from /app/backend; the frontend from /app/frontend.
cd /app/backend
start_backend
start_rq_cron
start_rq_worker rq_worker RomMWorker high default low
# Scans get a worker of their own, see SCAN_QUEUE_NAME.
start_rq_worker rq_scan_worker RomMWorker scans
# Streaming teardowns get a worker of their own, see STREAMING_QUEUE_NAME. It
# preloads the reaper, which runs every minute when streaming is on.
if [[ ${streaming_worker_enabled} == "true" ]]; then
	start_rq_worker rq_streaming_worker PreloadingWorker streaming
fi

start_watcher watcher watcher.py /app/romm/library
if [[ ${ENABLE_SYNC_FOLDER_WATCHER:-false} == "true" ]]; then
	sync_base_path="${ROMM_BASE_PATH:-/romm}/sync"
	mkdir -p "${sync_base_path}"
	start_watcher sync_watcher sync_watcher.py "${sync_base_path}"
fi

echo "Starting frontend dev server..."
cd /app/frontend
npm run dev &

wait
