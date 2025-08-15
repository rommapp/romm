#!/bin/bash

set -e

echo "Starting entrypoint script..."

# Create symlinks for frontend
for subfolder in assets resources; do
	if [[ -L /app/frontend/assets/romm/${subfolder} ]]; then
		target=$(readlink "/app/frontend/assets/romm/${subfolder}")

		# If the target is not the same as ${ROMM_BASE_PATH}/${subfolder}, recreate the symbolic link.
		if [[ ${target} != "${ROMM_BASE_PATH}/${subfolder}" ]]; then
			rm "/app/frontend/assets/romm/${subfolder}"
			ln -s "${ROMM_BASE_PATH}/${subfolder}" "/app/frontend/assets/romm/${subfolder}"
		fi
	elif [[ ! -e /app/frontend/assets/romm/${subfolder} ]]; then
		# Ensure parent directory exists before creating symbolic link
		mkdir -p "/app/frontend/assets/romm"
		ln -s "${ROMM_BASE_PATH}/${subfolder}" "/app/frontend/assets/romm/${subfolder}"
	fi
done

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
if [[ -z ${ROMM_AUTH_SECRET_KEY} ]]; then
	ROMM_AUTH_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
	export ROMM_AUTH_SECRET_KEY
fi

# Start all services in the background
echo "Starting backend..."
cd /app/backend
uv run python main.py &

echo "Starting RQ scheduler..."
RQ_REDIS_HOST=${REDIS_HOST:-127.0.0.1} \
	RQ_REDIS_PORT=${REDIS_PORT:-6379} \
	RQ_REDIS_USERNAME=${REDIS_USERNAME:-""} \
	RQ_REDIS_PASSWORD=${REDIS_PASSWORD:-""} \
	RQ_REDIS_DB=${REDIS_DB:-0} \
	RQ_REDIS_SSL=${REDIS_SSL:-0} \
	rqscheduler \
	--path /app/backend \
	--pid /tmp/rq_scheduler.pid &

echo "Starting RQ worker..."
# Build Redis URL properly
if [[ -n ${REDIS_PASSWORD-} ]]; then
	REDIS_URL="redis${REDIS_SSL:+s}://${REDIS_USERNAME-}:${REDIS_PASSWORD}@${REDIS_HOST:-127.0.0.1}:${REDIS_PORT:-6379}/${REDIS_DB:-0}"
elif [[ -n ${REDIS_USERNAME-} ]]; then
	REDIS_URL="redis${REDIS_SSL:+s}://${REDIS_USERNAME}@${REDIS_HOST:-127.0.0.1}:${REDIS_PORT:-6379}/${REDIS_DB:-0}"
else
	REDIS_URL="redis${REDIS_SSL:+s}://${REDIS_HOST:-127.0.0.1}:${REDIS_PORT:-6379}/${REDIS_DB:-0}"
fi

# Set PYTHONPATH so RQ can find the tasks module
PYTHONPATH="/app/backend:${PYTHONPATH-}" rq worker \
	--path /app/backend \
	--pid /tmp/rq_worker.pid \
	--url "${REDIS_URL}" \
	high default low &

echo "Starting watcher..."
watchfiles \
	--target-type command \
	'uv run python watcher.py' \
	/app/romm/library &

# Start the frontend dev server
cd /app/frontend
npm run dev &

# Wait for all background processes
wait
