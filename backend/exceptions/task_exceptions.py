class TaskNotFoundException(Exception):
    def __init__(self, name: str):
        self.message = f"No task is registered under the name '{name}'"
        super().__init__(self.message)

    def __repr__(self):
        return self.message
