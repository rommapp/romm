from .base import BaseModel


class ActivityEntrySchema(BaseModel):
    user_id: int
    username: str
    avatar_path: str
    rom_id: int
    rom_name: str
    rom_cover_path: str = ""
    platform_slug: str
    platform_name: str
    device_id: str
    device_type: str
    started_at: str


class ActivityClearSchema(BaseModel):
    user_id: int
    device_id: str
    rom_id: int
