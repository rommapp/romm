#!/bin/bash
cd /app/backend || exit 1
uv run mypy --config-file /app/.trunk/configs/mypy.ini \
  models/download_event.py handler/database/downloads_handler.py \
  endpoints/downloads.py endpoints/responses/downloads.py \
  utils/downloads.py tasks/scheduled/cleanup_download_events.py 2>&1 > /tmp/out.txt
echo "=== errors grouped by file ==="
grep -oE "^[^:]+\.py" /tmp/out.txt | sort | uniq -c | sort -rn
echo
echo "=== errors in MY new files ==="
grep -E "^(models/download_event|handler/database/downloads_handler|endpoints/downloads|endpoints/responses/downloads|utils/downloads|tasks/scheduled/cleanup_download_events)\.py" /tmp/out.txt || echo "  NONE"
