"""The schedule `rq cron` runs, registered when that process starts.

A task is registered only when it is enabled and has a cron string, so turning
one off is a restart rather than an unschedule.
"""

from rq import cron

from config import TASK_RESULT_TTL
from handler.redis_handler import QueuePrio
from logger.logger import log
from tasks.registry import SCHEDULED_TASKS
from tasks.tasks import run_task_by_name

for name, task in SCHEDULED_TASKS.items():
    if not task.enabled or not task.cron_string:
        continue

    # Every entry runs the same function, so without an explicit name they all
    # share one cron identity and one job history.
    cron.register(
        run_task_by_name,
        QueuePrio.LOW.value,
        name=name,
        kwargs={"name": name},
        cron=task.cron_string,
        job_timeout=task.timeout,
        result_ttl=TASK_RESULT_TTL,
        meta=task.job_meta,
    )
    log.info(f"Scheduled '{name}' at '{task.cron_string}'")
