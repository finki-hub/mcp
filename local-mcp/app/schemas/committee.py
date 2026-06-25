from pydantic import BaseModel, Field


class CommitteeRecommendation(BaseModel):
    mode: str = Field(
        ...,
        description="'full' (mentor + members recommended) or 'members_only' (members only)",
        examples=["full"],
    )
    mentor: str | None = Field(
        None,
        description="Recommended mentor (FULL) or the given mentor (MEMBERS-ONLY)",
        examples=["Ѓорѓи Маџаров"],
    )
    members: list[str] = Field(
        default_factory=list,
        description="The two recommended committee members",
        examples=[["Ивица Димитровски", "Дејан Ѓорѓевиќ"]],
    )
    error: str | None = Field(
        None,
        description="Set when the recommendation service could not be reached",
        examples=[
            "The thesis committee recommendation service is currently unavailable.",
        ],
    )
