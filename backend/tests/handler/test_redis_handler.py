from unittest.mock import MagicMock, PropertyMock

from rq import Worker
from rq.exceptions import DeserializationError, InvalidJobOperation, NoSuchJobError
from rq.job import Job, JobStatus

from handler.redis_handler import (
    cancel_job,
    get_job_func_name,
    get_job_kwargs,
    get_job_status,
    get_worker_current_job,
)


def make_job() -> MagicMock:
    job = MagicMock(spec=Job)
    job.id = "job-1"
    return job


def unreadable(attribute: str) -> MagicMock:
    """A job whose `attribute` fails the way an undeserializable payload does.

    Each mock gets its own type, so patching the property is instance-local.
    """
    job = make_job()
    setattr(type(job), attribute, PropertyMock(side_effect=DeserializationError))
    return job


class TestGetJobFuncName:
    def test_returns_the_recorded_name(self):
        job = make_job()
        job.func_name = "tasks.tasks.run_task_by_name"

        assert get_job_func_name(job) == "tasks.tasks.run_task_by_name"

    def test_falls_back_when_the_payload_cannot_be_read(self):
        assert get_job_func_name(unreadable("func_name")) == ""

    def test_returns_the_given_fallback(self):
        job = unreadable("func_name")

        assert get_job_func_name(job, fallback="unknown") == "unknown"


class TestGetJobKwargs:
    def test_returns_the_enqueued_keyword_arguments(self):
        job = make_job()
        job.kwargs = {"platform_ids": [1]}

        assert get_job_kwargs(job) == {"platform_ids": [1]}

    def test_returns_empty_for_a_job_enqueued_without_keywords(self):
        job = make_job()
        job.kwargs = {}

        assert get_job_kwargs(job) == {}

    def test_returns_none_when_the_payload_cannot_be_read(self):
        # None rather than empty: the caller has to tell "covers nothing" apart
        # from "cannot be known".
        assert get_job_kwargs(unreadable("kwargs")) is None


class TestGetJobStatus:
    def test_returns_the_recorded_status(self):
        job = make_job()
        job.get_status.return_value = JobStatus.QUEUED

        assert get_job_status(job) == JobStatus.QUEUED

    def test_returns_none_once_the_job_hash_has_expired(self):
        job = make_job()
        job.get_status.side_effect = InvalidJobOperation

        assert get_job_status(job) is None


class TestCancelJob:
    def test_cancels_a_live_job(self):
        job = make_job()

        assert cancel_job(job) is True
        job.cancel.assert_called_once()

    def test_tolerates_a_job_cancelled_by_an_earlier_call(self):
        # Stopping a scan twice reaches the running job again while it unwinds.
        job = make_job()
        job.cancel.side_effect = InvalidJobOperation

        assert cancel_job(job) is False


class TestGetWorkerCurrentJob:
    @staticmethod
    def _worker(**kwargs) -> MagicMock:
        worker = MagicMock(spec=Worker)
        worker.get_current_job.configure_mock(**kwargs)
        return worker

    def test_returns_the_job_the_worker_is_holding(self):
        job = make_job()

        assert get_worker_current_job(self._worker(return_value=job)) is job

    def test_returns_none_when_the_worker_is_idle(self):
        assert get_worker_current_job(self._worker(return_value=None)) is None

    def test_returns_none_when_the_job_outlived_by_its_worker_is_gone(self):
        worker = self._worker(side_effect=NoSuchJobError)

        assert get_worker_current_job(worker) is None
