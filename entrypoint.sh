#!/bin/bash
set -e

# Create mock directory structure if it doesn't exist
mkdir -p /app/romm_mock/library/roms/switch
touch /app/romm_mock/library/roms/switch/metroid.xci
mkdir -p /app/romm_mock/resources
mkdir -p /app/romm_mock/assets
mkdir -p /app/romm_mock/config
touch /app/romm_mock/config/config.yml

# Copy env template if .env doesn't exist
if [[ ! -f /app/.env ]]; then
	cp /app/env.template /app/.env
	echo "Created .env file from template. Please edit with your configuration."
fi

# Create symlinks for frontend
mkdir -p /app/frontend/assets/romm
ln -sf /app/backend/romm_mock/resources /app/frontend/assets/romm/resources
ln -sf /app/backend/romm_mock/assets /app/frontend/assets/romm/assets

# Start all services in the background
cd /app/backend
poetry run python main.py &
OBJC_DISABLE_INITIALIZE_FORK_SAFETY=1 poetry run python worker.py &

# Start the frontend dev server
cd /app/frontend
npm run dev &

# Wait for all background processes
wait
