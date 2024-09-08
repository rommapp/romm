from pydantic import BaseModel

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
    ParentGameID: int | None = None
    NumAchievements: int
    NumAwardedToUser: int
    NumAwardedToUserHardcore:int
    NumDistinctPlayersCasual: int
    NumDistinctPlayersHardcore: int
    ReleasedAtGranularity: str
    UserCompletion: str
    UserCompletionHardcore: str
    HighestAwardKind: str | None = None
    HighestAwardDate: str | None = None
    Achievements: dict