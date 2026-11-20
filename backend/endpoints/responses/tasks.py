from typing import TypedDict

from pydantic import with_config

from endpoints.responses.base import API_SCHEMA_CONFIG
from tasks.tasks import TaskType


@with_config(API_SCHEMA_CONFIG)
class TaskInfo(TypedDict):
    name: str
    type: TaskType
    manual_run: bool
    """Whether the task can be run manually."""
    title: str
    description: str
    enabled: bool
    destructive: bool
    cron_string: str


class GroupedTasksDict(TypedDict):
    scheduled: list[TaskInfo]
    manual: list[TaskInfo]
    watcher: list[TaskInfo]
