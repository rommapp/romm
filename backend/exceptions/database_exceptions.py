class RomFileOwnerChangedError(Exception):
    def __init__(self, rom_file_id: int) -> None:
        self.message = (
            f"Rom file {rom_file_id} moved to another rom while it was being locked"
        )
        super().__init__(self.message)

    def __repr__(self) -> str:
        return self.message
