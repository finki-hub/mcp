from typing import NotRequired, TypedDict


class CommitteeRecommendation(TypedDict):
    mode: str
    mentor: str | None
    members: list[str]
    error: NotRequired[str]
