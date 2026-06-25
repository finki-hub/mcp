from pydantic import BaseModel, Field


class CommitteeRecommendation(BaseModel):
    mode: str = Field(
        ...,
        description="'full' (препорачани ментор и членови) или 'members_only' (само членови)",
        examples=["full"],
    )
    mentor: str | None = Field(
        None,
        description="Препорачан ментор (FULL) или дадениот ментор (MEMBERS-ONLY)",
        examples=["Ѓорѓи Маџаров"],
    )
    members: list[str] = Field(
        default_factory=list,
        description="Двајцата препорачани членови на комисијата",
        examples=[["Ивица Димитровски", "Дејан Ѓорѓевиќ"]],
    )
    error: str | None = Field(
        None,
        description="Се пополнува кога сервисот за препорака е недостапен",
        examples=[
            "The thesis committee recommendation service is currently unavailable.",
        ],
    )
