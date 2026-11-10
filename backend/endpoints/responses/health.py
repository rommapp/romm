from typing import Literal, TypedDict


class HealthLiveResponse(TypedDict):
    status: Literal["ok"]


class HealthReadyResponse(TypedDict):
    database: bool
    valkey: bool
    worker: bool
    library: bool
    resources: bool
