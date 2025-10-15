from typing import Dict, List, TypedDict

from tasks.tasks import TaskType


class TaskInfo(TypedDict):
    name: str
    type: TaskType
    manual_run: bool
    title: str
    description: str
    enabled: bool
    cron_string: str


# Use a more flexible type for grouped tasks
GroupedTasksDict = Dict[str, List[TaskInfo]]
