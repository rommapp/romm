from typing import TypedDict

from pydantic import with_config

from endpoints.responses.base import API_SCHEMA_CONFIG
from tasks.tasks import TaskType


@with_config(API_SCHEMA_CONFIG)
class TaskInfo(TypedDict):
    name: str
    """The name of the task."""
    type: TaskType
    manual_run: bool
    """Whether the task can be run manually."""
    title: str
    """The display title of the task."""
    description: str
    """What the task does."""
    enabled: bool
    """Whether the task is enabled."""
    destructive: bool
    """Whether the task is marked destructive."""
    cron_string: str
    """The cron schedule of the task. Empty when it has none."""


class GroupedTasksDict(TypedDict):
    scheduled: list[TaskInfo]
    manual: list[TaskInfo]
    watcher: list[TaskInfo]
