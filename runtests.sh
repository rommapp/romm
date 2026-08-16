#!/bin/bash
(socat TCP-LISTEN:5432,fork,reuseaddr TCP:romm-postgres-dev:5432 &); sleep 2
cd /app/backend || exit 1
export ROMM_DB_DRIVER=postgresql DB_PORT=5432
uv run pytest tests/handler/database/test_downloads_handler.py tests/endpoints/test_downloads.py tests/endpoints/roms/test_rom.py -q 2>&1 | tail -5
