#!/bin/bash
set -e

# Copy env template if .env doesn't exist
if [[ ! -f /app/.env ]]; then
	cp /app/env.template /app/.env
	echo "Created .env file from template. Please edit with your configuration."
fi

# Create symlinks for frontend
mkdir -p /app/frontend/assets/romm
ln -sf /app/romm_mock/resources /app/frontend/assets/romm/resources
ln -sf /app/romm_mock/assets /app/frontend/assets/romm/assets

# Define a signal handler to propagate termination signals
function handle_termination() {
	echo "Terminating child processes..."
	kill -TERM $(jobs -p) 2>/dev/null
}

# Trap SIGTERM and SIGINT signals
trap handle_termination SIGTERM SIGINT
# Start all services in the background
cd /app/backend
poetry run python main.py &
OBJC_DISABLE_INITIALIZE_FORK_SAFETY=1 poetry run python worker.py &

# Start the frontend dev server
cd /app/frontend
npm run dev &

# Wait for all background processes
wait
