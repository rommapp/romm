from logger.formatter import BLUE
from logger.formatter import highlight as hl

FOLDER_STRUCT_MSG = "Check RomM folder structure here: https://docs.romm.app/latest/Getting-Started/Folder-Structure/ for more details"


class FolderStructureNotMatchException(Exception):
    def __init__(self):
        self.message = f"Platforms not found. {FOLDER_STRUCT_MSG }"
        super().__init__(self.message)

    def __repr__(self) -> str:
        return self.message


class PlatformNotFoundException(Exception):
    def __init__(self, platform: str):
        self.message = f"Platform {platform} not found"
        super().__init__(self.message)

    def __repr__(self):
        return self.message


class PlatformAlreadyExistsException(Exception):
    def __init__(self, fs_slug: str):
        self.message = f"Platform {fs_slug} already exists"
        super().__init__(self.message)

    def __repr__(self):
        return self.message


class RomsNotFoundException(Exception):
    def __init__(self, platform: str):
        self.message = f"Roms not found for platform {hl(platform, color=BLUE)}. {FOLDER_STRUCT_MSG }"
        super().__init__(self.message)

    def __repr__(self):
        return self.message


class RomAlreadyExistsException(Exception):
    def __init__(self, rom_name: str):
        self.message = f"Can't rename: {hl(rom_name)} already exists"
        super().__init__(self.message)

    def __repr__(self):
        return self.message


class FirmwareNotFoundException(Exception):
    def __init__(self, platform: str):
        self.message = f"Firmware not found for platform {hl(platform, color=BLUE)}. {FOLDER_STRUCT_MSG }"
        super().__init__(self.message)

    def __repr__(self):
        return self.message
