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

# Start all services in the background
cd /app/backend
uv run python main.py &
OBJC_DISABLE_INITIALIZE_FORK_SAFETY=1 uv run python worker.py &

# Start the frontend dev server
cd /app/frontend
npm run dev &

# Wait for all background processes
wait
