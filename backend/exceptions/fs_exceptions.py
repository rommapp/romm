from logger.formatter import BLUE
from logger.formatter import highlight as hl

folder_struct_msg = "Check RomM folder structure here: https://github.com/rommapp/romm?tab=readme-ov-file#folder-structure"


class FolderStructureNotMatchException(Exception):
    def __init__(self):
        self.message = f"Platforms not found. {folder_struct_msg}"
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
        self.message = f"Roms not found for platform {hl(platform, color=BLUE)}. {folder_struct_msg}"
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
        self.message = f"Firmware not found for platform {hl(platform, color=BLUE)}. {folder_struct_msg}"
        super().__init__(self.message)

    def __repr__(self):
        return self.message


class FirmwareAlreadyExistsException(Exception):
    def __init__(self, firmware_name: str):
        self.message = f"Can't rename: {hl(firmware_name)} already exists"
        super().__init__(self.message)

    def __repr__(self):
        return self.message
