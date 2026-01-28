import unittest
from unittest.mock import MagicMock, patch

from rq.job import Job

from tasks.tasks import PeriodicTask, TaskType


def dummy_task():
    pass


class TestTask(PeriodicTask):
    async def run(self, *args, **kwargs):
        pass


class TestPreventRequeue(unittest.TestCase):
    @patch("tasks.tasks.tasks_scheduler")
    @patch("tasks.tasks.low_prio_queue")
    def test_task_not_scheduled_if_in_queue(
        self, mock_low_prio_queue, mock_tasks_scheduler
    ):
        for method_name in ["init", "schedule"]:
            with self.subTest(method=method_name):
                task = TestTask(
                    title="Test Task",
                    description="A test task",
                    task_type=TaskType.GENERIC,
                    enabled=True,
                    manual_run=False,
                    cron_string="* * * * *",
                    func="backend.tests.tasks.test_prevent_requeue.dummy_task",
                )

                mock_job = MagicMock(spec=Job)
                mock_job.func_name = (
                    "backend.tests.tasks.test_prevent_requeue.dummy_task"
                )

                mock_low_prio_queue.get_jobs.return_value = [mock_job]
                mock_tasks_scheduler.get_jobs.return_value = []

                method_to_call = getattr(task, method_name)
                result = method_to_call()

                self.assertIsNone(result)
                mock_tasks_scheduler.cron.assert_not_called()
