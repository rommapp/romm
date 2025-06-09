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

# Install backend dependencies
cd /app/backend
poetry sync

# Create symlinks for frontend
mkdir -p /app/frontend/assets/romm
ln -sf /app/backend/romm_mock/resources /app/frontend/assets/romm/resources
ln -sf /app/backend/romm_mock/assets /app/frontend/assets/romm/assets

# Install frontend dependencies
cd /app/frontend
npm install

# Execute the command passed to docker run
exec "$@"
