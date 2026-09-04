"""Job stubs and Redis patching shared by the scan job discovery tests."""

from itertools import count
from unittest.mock import MagicMock

from rq.exceptions import NoSuchJobError
from rq.job import Job, JobStatus

import handler.scan_jobs as scan_jobs_module
from tasks.tasks import TaskType, run_task_by_name

TASK_RUNNER_FUNC = f"{run_task_by_name.__module__}.{run_task_by_name.__name__}"
NON_SCAN_FUNC = "tasks.tasks.not_a_scan"

_job_ids = count()


def make_job(
    func_name: str,
    *,
    status=JobStatus.QUEUED,
    task_name: str | None = None,
    task_type: TaskType | None = None,
):
    """An RQ job stub that scan job discovery will accept."""
    job = MagicMock(spec=Job)
    job.id = f"job-{next(_job_ids)}"
    job.func_name = func_name
    job.get_status.return_value = status
    job.kwargs = {}
    job.meta = {}
    if task_name:
        job.meta["task_name"] = task_name
    if task_type:
        job.meta["task_type"] = task_type
    return job


def make_task_job(**kwargs):
    """A scan that runs through the task runner, as the scheduled rescan does."""
    return make_job(TASK_RUNNER_FUNC, task_type=TaskType.SCAN, **kwargs)


def make_scoped_job():
    """A scan of named roms, which the metadata refresh dialog asks for."""
    job = make_job(scan_jobs_module.SCAN_PLATFORMS_FUNC)
    job.kwargs = {"platform_ids": [1], "roms_ids": [7]}
    return job


def patch_scan_jobs(
    mocker,
    *,
    running=None,
    scan_queued=(),
    high_queued=(),
    low_queued=(),
    scheduled=(),
    worker_lost=False,
) -> MagicMock:
    """Point every place scan discovery looks at a fixed set of jobs.

    Returns the patched scheduled-scan registry.
    """
    worker = MagicMock()
    if worker_lost:
        worker.get_current_job.side_effect = NoSuchJobError
    else:
        worker.get_current_job.return_value = running
    mocker.patch.object(scan_jobs_module.Worker, "all", return_value=[worker])

    queued_jobs = list(scan_queued) + list(high_queued) + list(low_queued)
    scheduled_jobs = list(scheduled)
    mocker.patch.object(
        scan_jobs_module.scan_queue,
        "get_job_ids",
        return_value=[job.id for job in scan_queued],
    )
    mocker.patch.object(
        scan_jobs_module.high_prio_queue,
        "get_job_ids",
        return_value=[job.id for job in high_queued],
    )
    mocker.patch.object(
        scan_jobs_module.low_prio_queue,
        "get_job_ids",
        return_value=[job.id for job in low_queued],
    )

    registry = MagicMock()
    registry.get_job_ids.return_value = [job.id for job in scheduled_jobs]
    registry.get_jobs_to_schedule.return_value = []
    mocker.patch.object(
        scan_jobs_module, "_scheduled_scan_registries", return_value=[registry]
    )

    # Both the queue and the registry lookups fetch by id, so the stub has to
    # answer for whichever ids it is handed.
    by_id = {job.id: job for job in queued_jobs + scheduled_jobs}
    mocker.patch.object(
        scan_jobs_module.Job,
        "fetch_many",
        side_effect=lambda job_ids, **kwargs: [by_id.get(i) for i in job_ids],
    )
    return registry
