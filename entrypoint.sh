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

# Start all services in the background
echo "Starting backend..."
cd /app/backend
if [[ ${DEV_MODE:-false} == "true" ]]; then
	echo "Starting backend under debugpy on :5678..."
	# Add --wait-for-client after --listen to pause until VSCode attaches.
	uv run python -m debugpy --listen 0.0.0.0:5678 main.py &
else
	uv run python main.py &
fi

# REDIS_SSL is a boolean to the app, so "false" and "0" mean plaintext.
REDIS_USERINFO=""
REDIS_SSL_VALUE="${REDIS_SSL-}"
case "${REDIS_SSL_VALUE,,}" in
1 | true | yes | on) REDIS_SCHEME="rediss" ;;
*) REDIS_SCHEME="redis" ;;
esac
if [[ -n ${REDIS_PASSWORD-} ]]; then
	REDIS_USERINFO="${REDIS_USERNAME-}:${REDIS_PASSWORD}@"
elif [[ -n ${REDIS_USERNAME-} ]]; then
	REDIS_USERINFO="${REDIS_USERNAME}@"
fi
REDIS_URL="${REDIS_SCHEME}://${REDIS_USERINFO}${REDIS_HOST:-127.0.0.1}:${REDIS_PORT:-6379}/${REDIS_DB:-0}"

echo "Starting RQ cron scheduler..."
# The URL carries the password, so it goes through RQ_REDIS_URL rather than
# --url, which would put it on a world-readable command line.
PYTHONPATH="/app/backend:${PYTHONPATH-}" \
	RQ_REDIS_URL="${REDIS_URL}" \
	rq cron \
	--path /app/backend \
	--logging-level "${LOGLEVEL:-INFO}" \
	tasks.cron_config &

# Set PYTHONPATH so RQ can find the tasks module.
# Use a worker class that drops the noisy per-sweep "cleaning registries for
# queue" log line. The maintenance interval keeps its default (~10 min) so
# orphaned STARTED jobs and stale workers are still pruned promptly.
# --with-scheduler releases delayed jobs, which is how the watcher's rescans
# wait out their delay.
start_rq_worker() {
	local name="$1"
	shift

	PYTHONPATH="/app/backend:${PYTHONPATH-}" \
		RQ_REDIS_URL="${REDIS_URL}" \
		rq worker \
		--path /app/backend \
		--worker-class handler.rq_worker.RomMWorker \
		--pid "/tmp/${name}.pid" \
		--logging_level "${LOGLEVEL:-INFO}" \
		--with-scheduler \
		"$@" &
}

echo "Starting RQ worker..."
start_rq_worker rq_worker high default low

# Scans get a worker of their own, see SCAN_QUEUE_NAME.
echo "Starting RQ scan worker..."
start_rq_worker rq_scan_worker scans

echo "Starting watcher..."
watchfiles \
	--target-type command \
	'uv run python watcher.py' \
	/app/romm/library &

if [[ ${ENABLE_SYNC_FOLDER_WATCHER:-false} == "true" ]]; then
	echo "Starting sync folder watcher..."
	sync_base_path="${ROMM_BASE_PATH:-/romm}/sync"
	mkdir -p "${sync_base_path}"
	watchfiles \
		--target-type command \
		'uv run python sync_watcher.py' \
		"${sync_base_path}" &
fi

# Start the frontend dev server
cd /app/frontend
npm run dev &

# Wait for all background processes
wait
