from typing import TypedDict

from tasks.tasks import TaskType


class TaskInfo(TypedDict):
    name: str
    type: TaskType
    manual_run: bool
    title: str
    description: str
    enabled: bool
    destructive: bool
    cron_string: str


class GroupedTasksDict(TypedDict):
    scheduled: list[TaskInfo]
    manual: list[TaskInfo]
    watcher: list[TaskInfo]
