from unittest.mock import MagicMock, PropertyMock

from rq.exceptions import DeserializationError, InvalidJobOperation
from rq.job import Job, JobStatus

from handler.redis_handler import get_job_func_name, get_job_kwargs, get_job_status


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
