class ConfigNotWritableException(Exception):
    def __init__(self):
        self.message = "Config file is not writable. Check config.yml permissions"
        super().__init__(self.message)

    def __repr__(self) -> str:
        return self.message
