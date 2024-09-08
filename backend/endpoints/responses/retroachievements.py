from __future__ import annotations
from fastapi import HTTPException, Query, Request, UploadFile, status
from typing import Any

from pydantic import BaseModel, Field

class Achievements(BaseModel):
    ID: int
    NumAwarded: int
    NumAwardedHardcore: int
    Title: str
    Description: str
    Points: int
    TrueRatio: int
    Author: str
    DateModified: str
    DateCreated: str
    DateEarned: str | None = None
    BadgeName: str
    DisplayOrder: int
    MemAddr: str
    type: Any




class RetroAchievementsGameSchema(BaseModel):
    ID: int
    Title: str
    ConsoleID: int
    ForumTopicID: int
    Flags: int
    ImageIcon: str
    ImageTitle: str
    ImageIngame: str
    ImageBoxArt: str
    Publisher: str
    Developer: str
    Genre: str
    Released: str
    IsFinal: int
    RichPresencePatch: str
    GuideURL: str | None = None
    ConsoleName: str
    NumDistinctPlayers: int
    ParentGameID: str | None = None
    NumAchievements: int
    Achievements: dict[str, Achievements]
    NumAwardedToUser: int
    NumAwardedToUserHardcore: int
    NumDistinctPlayersCasual: int
    NumDistinctPlayersHardcore: int
    ReleasedAtGranularity: str
    UserCompletion: str
    UserCompletionHardcore: str
    HighestAwardKind: str | None = None
    HighestAwardDate: str | None = None

    @classmethod
    def from_orm_with_request(cls, db_rom: RetroAchievementsGameSchema, request: Request) -> RetroAchievementsGameSchema:
        rom = cls.model_validate(db_rom)

        return rom

