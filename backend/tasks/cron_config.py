"""The schedule `rq cron` runs, registered when that process starts.

A task is registered only when it is enabled and has a cron string, so nothing
in Redis has to be unscheduled when a deployment turns one off: the next start
simply leaves it out.
"""

from rq import cron

from endpoints.responses import TaskType
from handler.redis_handler import SCAN_QUEUE_NAME, QueuePrio
from logger.logger import log
from tasks.registry import SCHEDULED_TASKS
from tasks.tasks import run_task_by_name

for name, task in SCHEDULED_TASKS.items():
    if not task.enabled or not task.cron_string:
        continue

    # The scheduled rescan belongs on the queue the scan worker consumes, so it
    # neither holds up the other tasks nor overlaps another scan.
    queue_name = (
        SCAN_QUEUE_NAME if task.task_type is TaskType.SCAN else QueuePrio.LOW.value
    )

    cron.register(
        run_task_by_name,
        queue_name,
        kwargs={"name": name},
        cron=task.cron_string,
        job_timeout=task.timeout,
        meta={
            "task_name": task.title,
            "task_type": task.task_type.value,
        },
    )
    log.info(f"Scheduled '{name}' at '{task.cron_string}'")
