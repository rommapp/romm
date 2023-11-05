import requests
from rq_scheduler import Scheduler
from abc import ABC, abstractmethod

from utils.redis import low_prio_queue
from config import ENABLE_EXPERIMENTAL_REDIS
from logger.logger import log
from .exceptions import SchedulerException

tasks_scheduler = Scheduler(queue=low_prio_queue, connection=low_prio_queue.connection)


class PeriodicTask(ABC):
    def __init__(
        self,
        func: str,
        description,
        enabled: bool = False,
        cron_string: str = None,
    ):
        self.func = func
        self.description = description or func
        self.enabled = enabled
        self.cron_string = cron_string

    def _get_existing_job(self):
        existing_jobs = tasks_scheduler.get_jobs()
        for job in existing_jobs:
            if job.func_name == self.func:
                return job

        return None

    def init(self):
        job = self._get_existing_job()

        if self.enabled and not job:
            return self.schedule()
        elif job and not self.enabled:
            return self.unschedule()

    @abstractmethod
    async def run(self):
        pass

    def schedule(self):
        if not ENABLE_EXPERIMENTAL_REDIS:
            raise SchedulerException(
                f"Redis not connectable, {self.description} is not scheduled."
            )

        if not self.enabled:
            raise SchedulerException(f"Scheduled {self.description} is not enabled.")

        if self._get_existing_job():
            log.info(f"{self.description.capitalize()} is already scheduled.")
            return

        if self.cron_string:
            return tasks_scheduler.cron(
                self.cron_string,
                func=self.func,
                repeat=None,
            )

        return None

    def unschedule(self):
        job = self._get_existing_job()

        if not job:
            log.info(f"{self.description.capitalize()} is not scheduled.")
            return

        tasks_scheduler.cancel(job)
        log.info(f"{self.description.capitalize()} unscheduled.")


class RemoteFilePullTask(PeriodicTask):
    def __init__(self, *args, url: str, file_path: str, **kwargs):
        super().__init__(*args, **kwargs)

        self.url = url
        self.file_path = file_path

    async def run(self, force: bool = False) -> bytes | None:
        if not self.enabled and not force:
            log.info(f"Scheduled {self.description} not enabled, unscheduling...")
            self.unschedule()
            return None

        log.info(f"Scheduled {self.description} started...")

        try:
            response = requests.get(self.url)
            response.raise_for_status()

            with open(self.file_path, "wb") as fixture:
                fixture.write(response.content)

            log.info(f"Scheduled {self.description} done")
            return response.content
        except requests.exceptions.RequestException as e:
            log.error(f"Scheduled {self.description} failed", exc_info=True)
            log.error(e)
            return None
