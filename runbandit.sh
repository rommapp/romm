#!/bin/bash
cd /app/backend || exit 1
echo "=== bandit on my files after the suppressions ==="
python -m bandit --ini /app/.trunk/configs/.bandit -r \
  models/download_event.py handler/database/downloads_handler.py \
  endpoints/downloads.py endpoints/responses/downloads.py \
  utils/downloads.py tasks/scheduled/cleanup_download_events.py \
  handler/auth/constants.py handler/auth/hybrid_auth.py \
  endpoints/roms/files.py endpoints/roms/__init__.py \
  models/rom.py endpoints/responses/rom.py \
  main.py startup.py config/__init__.py alembic/versions/0108_download_statistics.py \
  2>&1 | grep -E "Issue:|Total issues|Low:|Medium:|High:|nosec" | head -15
