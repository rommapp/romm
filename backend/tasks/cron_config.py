"""The schedule `rq cron` runs, registered when that process starts.

A task is registered only when it is enabled and has a cron string, so turning
one off is a restart rather than an unschedule.
"""

from rq import cron

from config import TASK_RESULT_TTL, TASK_TIMEOUT
from handler.redis_handler import QueuePrio
from logger.logger import log
from tasks.registry import SCHEDULED_TASKS, enqueue_scheduled_scan
from tasks.tasks import SCAN_DISPATCH_META_KEY, TaskType, run_task_by_name

for name, task in SCHEDULED_TASKS.items():
    if not task.enabled or not task.cron_string:
        continue

    # A scan is enqueued by a dispatch job rather than registered on the scan
    # queue, because cron can attach no callback to report a scan whose worker
    # died. The dispatch runs on the low queue so it fires on the tick instead
    # of waiting behind a scan, and only enqueues, so the scan timeout belongs
    # to the scan rather than to this.
    is_scan = task.task_type is TaskType.SCAN
    meta = {**task.job_meta, SCAN_DISPATCH_META_KEY: True} if is_scan else task.job_meta

    # Every entry runs the same function, so without an explicit name they all
    # share one cron identity and one job history.
    cron.register(
        enqueue_scheduled_scan if is_scan else run_task_by_name,
        QueuePrio.LOW.value,
        name=name,
        kwargs={"name": name},
        cron=task.cron_string,
        job_timeout=TASK_TIMEOUT if is_scan else task.timeout,
        result_ttl=TASK_RESULT_TTL,
        meta=meta,
    )
    log.info(f"Scheduled '{name}' at '{task.cron_string}'")
