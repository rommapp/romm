"""The schedule `rq cron` runs, registered when that process starts.

A task is registered only when it is enabled and has a cron string, so turning
one off is a restart rather than an unschedule.
"""

from rq import cron

from handler.redis_handler import QueuePrio
from logger.logger import log
from tasks.registry import SCHEDULED_TASKS
from tasks.tasks import run_task_by_name

for name, task in SCHEDULED_TASKS.items():
    if not task.enabled or not task.cron_string:
        continue

    cron.register(
        run_task_by_name,
        QueuePrio.LOW.value,
        kwargs={"name": name},
        cron=task.cron_string,
        job_timeout=task.timeout,
        meta=task.job_meta,
    )
    log.info(f"Scheduled '{name}' at '{task.cron_string}'")
