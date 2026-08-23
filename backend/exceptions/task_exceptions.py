class SchedulerException(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)

    def __repr__(self):
        return self.message


class TaskNotFoundException(SchedulerException):
    def __init__(self, name: str):
        super().__init__(f"No task is registered under the name '{name}'")
