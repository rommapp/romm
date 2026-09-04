"""The schedule `rq cron` runs, registered when that process starts.

A task is registered only when it is enabled and has a cron string, so turning
one off is a restart rather than an unschedule.
"""

from rq import cron

from config import TASK_RESULT_TTL, TASK_TIMEOUT
from handler.redis_handler import QueuePrio
from logger.logger import log
from tasks.registry import SCHEDULED_TASKS, enqueue_scheduled_scan
from tasks.tasks import TaskType, run_task_by_name

for name, task in SCHEDULED_TASKS.items():
    if not task.enabled or not task.cron_string:
        continue

    # Cron attaches no failure callback, so a scan goes through a dispatch job
    # that can. It only enqueues, so it takes the ordinary task timeout.
    is_scan = task.task_type is TaskType.SCAN

    # Every entry runs the same function, so without an explicit name they all
    # share one cron identity and one job history.
    cron.register(
        enqueue_scheduled_scan if is_scan else run_task_by_name,
        QueuePrio.LOW.value,
        name=name,
        kwargs={"name": name},
        cron=task.cron_string,
        job_timeout=TASK_TIMEOUT if is_scan else task.timeout,
        # A spent dispatch carries the scan's own name, and RQ drops a job whose
        # result_ttl is 0, so one rescan is not listed as two runs.
        result_ttl=0 if is_scan else TASK_RESULT_TTL,
        meta=task.job_meta,
    )
    log.info(f"Scheduled '{name}' at '{task.cron_string}'")
