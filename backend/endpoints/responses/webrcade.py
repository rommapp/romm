from typing_extensions import TypedDict


class WebrcadeFeedSchema(TypedDict):
    title: str
    longTitle: str
    description: str
    thumbnail: str
    background: str
    categories: list[dict]
