import contextlib
import logging
from typing import Any, Final

import rq.scheduler
from rq import Worker
from rq.exceptions import AbandonedJobError
from rq.job import Job

from tasks.tasks import report_task_failure

# Fragments of the lines RQ logs on every tick. The maintenance sweep and the
# scheduler heartbeat still run; only their log records are dropped.
_PERIODIC_NOISE: Final[tuple[str, ...]] = (
    "cleaning registries for queue",
    "scheduler sending heartbeat to",
)


class _DropPeriodicNoiseFilter(logging.Filter):
    """Drops RQ's per-tick maintenance and scheduler-heartbeat log lines."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage().lower()
        return not any(fragment in message for fragment in _PERIODIC_NOISE)


def _silence_periodic_noise(logger: logging.Logger) -> None:
    if not any(isinstance(f, _DropPeriodicNoiseFilter) for f in logger.filters):
        logger.addFilter(_DropPeriodicNoiseFilter())


class RomMWorker(Worker):
    """RQ worker that reports failed tasks, silences RQ's periodic log lines,
    and, on the install queue, guarantees a stuck InstallSession gets marked
    FAILED.

    ``handler.install.runner.run_install`` already catches its own
    exceptions and fails the session itself, but that only covers failures
    once the job body is actually running. A failure before that (the job
    can't even be imported - a broken worker image, a bad deploy) never
    reaches that try/except, so without this the session sits in whatever
    state it was last polled at forever and the UI spins indefinitely.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        _silence_periodic_noise(self.log)
        # --with-scheduler forks the scheduler off this process, so a filter
        # added here is the only one that logger inherits.
        _silence_periodic_noise(logging.getLogger(rq.scheduler.__name__))
        self.push_exc_handler(report_task_failure)

    def handle_work_horse_killed(
        self, job: Job, retpid: int, ret_val: int, rusage: Any
    ) -> None:
        # mypy's untyped_calls_exclude cannot name the receiver of a super() call.
        super().handle_work_horse_killed(job, retpid, ret_val, rusage)  # type: ignore[no-untyped-call]
        # RQ runs neither the failure callback nor the exception handlers for a
        # killed horse, only for a job whose whole worker died.
        exc_info = (AbandonedJobError, AbandonedJobError(), None)
        # RQ logs a callback that raises.
        with contextlib.suppress(Exception):
            job.execute_failure_callback(self.death_penalty_class, *exc_info)
        self.handle_exception(job, *exc_info)

    def handle_exception(self, job: Job, *exc_info: Any) -> None:
        self._fail_install_session(job)
        super().handle_exception(job, *exc_info)

    @staticmethod
    def _fail_install_session(job: Job) -> None:
        # Lazy imports: this runs on any unhandled job exception, including
        # ones raised while importing application modules, so importing
        # these at module load time would risk the same failure mode.
        from handler.redis_handler import QueuePrio

        if job.origin != QueuePrio.INSTALL.value:
            return
        try:
            install_session_id = job.args[0]
        except Exception:  # noqa: BLE001 - malformed/undeserializable job
            return
        try:
            from handler.database import db_install_session_handler
            from models.install_session import InstallSessionState

            db_install_session_handler.update_session(
                install_session_id,
                {
                    "state": InstallSessionState.FAILED,
                    "error": "The install worker crashed before it could run this job",
                    "vnc_url": None,
                    "vnc_web_port": None,
                },
            )
        except Exception as e:  # noqa: BLE001 - safety net, never mask the real error
            logging.getLogger(__name__).error(
                f"Couldn't mark install session {install_session_id} failed "
                f"after a worker crash: {e}"
            )
