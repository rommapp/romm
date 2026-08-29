"""The schedule `rq cron` runs, registered when that process starts.

A task is registered only when it is enabled and has a cron string, so nothing
in Redis has to be unscheduled when a deployment turns one off: the next start
simply leaves it out.
"""

from typing import Any

from rq import cron

from config import TASK_RESULT_TTL, TASK_TIMEOUT
from endpoints.responses import TaskType
from handler.redis_handler import QueuePrio
from logger.logger import log
from tasks.registry import SCHEDULED_TASKS
from tasks.tasks import (
    SCAN_DISPATCH_META_KEY,
    enqueue_scheduled_scan,
    run_task_by_name,
)

for name, task in SCHEDULED_TASKS.items():
    if not task.enabled or not task.cron_string:
        continue

    # A scan is enqueued by a dispatch job rather than registered on the scan
    # queue, because cron can attach no callback to report a scan whose worker
    # died. The dispatch runs on the low queue so it fires on the tick instead
    # of waiting behind a scan, and only enqueues, so the scan timeout belongs
    # to the scan rather than to this.
    is_scan = task.task_type is TaskType.SCAN

    meta: dict[str, Any] = {
        "task_name": task.title,
        "task_type": task.task_type.value,
    }
    if is_scan:
        meta[SCAN_DISPATCH_META_KEY] = True

    cron.register(
        enqueue_scheduled_scan if is_scan else run_task_by_name,
        QueuePrio.LOW.value,
        kwargs={"name": name},
        cron=task.cron_string,
        job_timeout=TASK_TIMEOUT if is_scan else task.timeout,
        # `register()` defaults this to RQ's 500 seconds and always writes it
        # onto the job, so the worker's own result TTL can never apply and the
        # task history would empty minutes after each run.
        result_ttl=TASK_RESULT_TTL,
        meta=meta,
    )
    log.info(f"Scheduled '{name}' at '{task.cron_string}'")
