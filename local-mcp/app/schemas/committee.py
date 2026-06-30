from pydantic import BaseModel, ConfigDict, Field


class CommitteeOption(BaseModel):
    model_config = ConfigDict(frozen=True)

    mentor: str | None = Field(
        None,
        description="Препорачан или зададен ментор за оваа опција",
        examples=["Ѓорѓи Маџаров"],
    )
    members: list[str] = Field(
        default_factory=list,
        description="Препорачани членови на комисијата за оваа опција",
        examples=[["Ивица Димитровски", "Дејан Ѓорѓевиќ"]],
    )
    confidence: float | None = Field(
        None,
        description="Проценка на сигурноста на препораката, ако сервисот ја врати",
        examples=[0.82],
    )
    reasons: list[str] = Field(
        default_factory=list,
        description="Кратки причини за препораката",
    )
    evidence: list[str] = Field(
        default_factory=list,
        description="Кратки докази: слични дипломски или релевантни трудови",
    )


class CommitteeRecommendation(BaseModel):
    model_config = ConfigDict(frozen=True)

    mode: str = Field(
        ...,
        description="'full' (препорачан ментор и двајца членови) или 'members_only' (само двајца членови)",
        examples=["full"],
    )
    mentor: str | None = Field(
        None,
        description="Препорачан ментор (кога mode е 'full') или дадениот ментор (кога mode е 'members_only')",
        examples=["Ѓорѓи Маџаров"],
    )
    members: list[str] = Field(
        default_factory=list,
        description="Двајцата препорачани членови на комисијата",
        examples=[["Ивица Димитровски", "Дејан Ѓорѓевиќ"]],
    )
    recommendations: list[CommitteeOption] = Field(
        default_factory=list,
        description="Една или повеќе препорачани комисии, подредени од најдобра кон алтернативни",
    )
    error: str | None = Field(
        None,
        description="Се пополнува кога сервисот за препорака е недостапен",
        examples=[
            "Сервисот за препорака на комисии за дипломски работи моментално е недостапен.",
        ],
    )
