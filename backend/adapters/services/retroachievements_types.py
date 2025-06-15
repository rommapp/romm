import enum
from collections.abc import Mapping
from typing import NotRequired, TypedDict


class PaginatedResponse[T: Mapping](TypedDict):
    Count: int
    Total: int
    Results: list[T]


# https://github.com/RetroAchievements/RAWeb/blob/master/app/Platform/Enums/AchievementType.php
class RAGameAchievementType(enum.StrEnum):
    PROGRESSION = "progression"
    WIN_CONDITION = "win_condition"
    MISSABLE = "missable"


# https://github.com/RetroAchievements/RAWeb/blob/master/app/Platform/Enums/ReleasedAtGranularity.php
class RAGameReleasedAtGranularity(enum.StrEnum):
    DAY = "day"
    MONTH = "month"
    YEAR = "year"


# https://github.com/RetroAchievements/RAWeb/blob/master/resources/js/common/components/AwardIndicator/AwardIndicator.tsx
class RAUserCompletionProgressKind(enum.StrEnum):
    COMPLETED = "completed"
    MASTERED = "mastered"
    BEATEN_HARDCORE = "beaten-hardcore"
    BEATEN_SOFTCORE = "beaten-softcore"


# https://api-docs.retroachievements.org/v1/get-game-extended.html#response
class RAGameExtendedDetailsAchievement(TypedDict):
    ID: int
    NumAwarded: int
    NumAwardedHardcore: int
    Title: str
    Description: str
    Points: int
    TrueRatio: int
    Author: str
    AuthorULID: str
    DateModified: str  # ISO 8601 datetime format
    DateCreated: str  # ISO 8601 datetime format
    BadgeName: str
    DisplayOrder: int
    MemAddr: str
    type: RAGameAchievementType | None


# https://api-docs.retroachievements.org/v1/get-game-extended.html#response
class RAGameExtendedDetails(TypedDict):
    ID: int
    Title: str
    ConsoleID: int
    ForumTopicID: int | None
    ImageIcon: str
    ImageTitle: str
    ImageIngame: str
    ImageBoxArt: str
    Publisher: str
    Developer: str
    Genre: str
    Released: str  # ISO 8601 date format
    ReleasedAtGranularity: RAGameReleasedAtGranularity
    RichPresencePatch: str
    GuideURL: str | None
    Updated: str  # ISO 8601 datetime format
    ConsoleName: str
    ParentGameID: int | None
    NumDistinctPlayers: int
    NumAchievements: int
    Achievements: dict[
        str, RAGameExtendedDetailsAchievement
    ]  # Key is achievement ID as string
    NumDistinctPlayersCasual: int
    NumDistinctPlayersHardcore: int


# https://api-docs.retroachievements.org/v1/get-user-completion-progress.html#response
class RAUserCompletionProgressResult(TypedDict):
    GameID: int
    Title: str
    ImageIcon: str
    ConsoleID: int
    ConsoleName: str
    MaxPossible: int
    NumAwarded: int
    NumAwardedHardcore: int
    MostRecentAwardedDate: str  # ISO 8601 datetime format
    HighestAwardKind: RAUserCompletionProgressKind  # e.g., "beaten-hardcore"
    HighestAwardDate: str  # ISO 8601 datetime format


# https://api-docs.retroachievements.org/v1/get-user-completion-progress.html#response
RAUserCompletionProgress = PaginatedResponse[RAUserCompletionProgressResult]


# https://api-docs.retroachievements.org/v1/get-game-info-and-user-progress.html#response
class RAGameInfoAndUserProgressAchievement(TypedDict):
    ID: int
    NumAwarded: int
    NumAwardedHardcore: int
    Title: str
    Description: str
    Points: int
    TrueRatio: int
    Author: str
    AuthorULID: str
    DateModified: str  # ISO 8601 datetime format
    DateCreated: str  # ISO 8601 datetime format
    BadgeName: str
    DisplayOrder: int
    MemAddr: str
    type: RAGameAchievementType | None
    DateEarnedHardcore: NotRequired[str]  # ISO 8601 datetime format
    DateEarned: NotRequired[str]  # ISO 8601 datetime format


# https://api-docs.retroachievements.org/v1/get-game-info-and-user-progress.html#response
class RAGameInfoAndUserProgress(TypedDict):
    ID: int
    Title: str
    ConsoleID: int
    ForumTopicID: int | None
    ImageIcon: str
    ImageTitle: str
    ImageIngame: str
    ImageBoxArt: str
    Publisher: str
    Developer: str
    Genre: str
    Released: str  # ISO 8601 date format
    ReleasedAtGranularity: RAGameReleasedAtGranularity
    RichPresencePatch: str
    GuideURL: str | None
    ConsoleName: str
    ParentGameID: int | None
    NumDistinctPlayers: int
    NumAchievements: int
    Achievements: dict[
        str, RAGameInfoAndUserProgressAchievement
    ]  # Key is achievement ID as string
    NumAwardedToUser: int
    NumAwardedToUserHardcore: int
    NumDistinctPlayersCasual: int
    NumDistinctPlayersHardcore: int
    UserCompletion: str  # e.g., "100.00%"
    UserCompletionHardcore: str  # e.g., "100.00%"
    HighestAwardKind: NotRequired[RAUserCompletionProgressKind]
    HighestAwardDate: NotRequired[str]  # ISO 8601 datetime format


# https://api-docs.retroachievements.org/v1/get-game-list.html#response
class RAGameListItem(TypedDict):
    Title: str
    ID: int
    ConsoleID: int
    ConsoleName: str
    ImageIcon: str
    NumAchievements: int
    NumLeaderboards: int
    Points: int
    DateModified: str  # ISO 8601 datetime format
    ForumTopicID: int | None
    Hashes: NotRequired[list[str]]
