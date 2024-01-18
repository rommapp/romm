class SchedulerException(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)

    def __repr__(self):
        return self.message
