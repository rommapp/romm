from pydantic import BaseModel

class BaseAsset(BaseModel):
    id: int

    file_name: str
    file_name_no_tags: str
    file_extension: str
    file_path: str
    file_size_bytes: int
    full_path: str

    class Config:
        from_attributes = True

class SaveSchema(BaseAsset):
    rom_id: int
    platform_slug: str

class StateSchema(BaseAsset):
    rom_id: int
    platform_slug: str

class ScreenshotSchema(BaseAsset):
    rom_id: int

class BiosSchema(BaseAsset):
    platform_slug: str
