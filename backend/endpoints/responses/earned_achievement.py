from .base import BaseModel


class AchievementTypeCountsSchema(BaseModel):
    progression: int
    missable: int
    win_condition: int
    other: int


class CatalogAchievementSchema(BaseModel):
    id: str
    title: str | None
    description: str | None
    points: int | None
    badge_url: str | None
    badge_path: str | None
    badge_url_lock: str | None
    badge_path_lock: str | None
    type: str | None
    display_order: int | None
    earned: bool
    earned_at: str | None


class AchievementGameSchema(BaseModel):
    rom_id: int
    name: str
    platform_name: str | None
    platform_slug: str | None = None
    platform_fs_slug: str | None = None
    cover_url: str | None
    path_cover_large: str | None = None
    path_cover_small: str | None = None
    url_cover: str | None = None
    title_url: str | None
    ingame_url: str | None
    box_art_url: str | None
    earned: int
    total: int
    points_earned: int
    points_total: int
    earned_by_type: AchievementTypeCountsSchema
    achievements: list[CatalogAchievementSchema]


class EarnedAchievementsSchema(BaseModel):
    """RetroAchievements progress for the visible library, including games still at 0%."""

    linked: bool
    synced: bool
    earned: int
    total: int
    points_earned: int
    points_total: int
    earned_by_type: AchievementTypeCountsSchema
    games: list[AchievementGameSchema]
