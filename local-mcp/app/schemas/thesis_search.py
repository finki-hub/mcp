from enum import StrEnum

from pydantic import Field

from app.schemas.base import PrunedModel


class ThesisKind(StrEnum):
    BACHELOR = "bachelor"
    MASTER = "master"


class ThesisRole(StrEnum):
    MENTOR = "mentor"
    MEMBER = "member"
    PRESIDENT = "president"


class ThesisMatch(PrunedModel):
    kind: ThesisKind = Field(
        ..., description="bachelor (дипломска) или master (магистерска)"
    )
    title: str = Field(..., description="Наслов на трудот")
    student: str | None = Field(None, description="Студент", examples=["Ана Анова"])
    student_index: str | None = Field(
        None,
        description="Број на индекс на студентот",
        examples=["221090"],
    )
    mentor: str | None = Field(None, description="Ментор", examples=["Весна Димитрова"])
    year: int | None = Field(None, description="Година", examples=[2026])
    date: str | None = Field(
        None,
        description="Датум на пријавување (дипломска) или презентација (магистерска)",
        examples=["2026-11-01"],
    )
    status: str | None = Field(None, description="Статус")
    role: ThesisRole | None = Field(
        None,
        description="Улогата на бараниот вработен во трудот (само со `staff`)",
    )


class ThesisSearch(PrunedModel):
    total: int = Field(0, description="Вкупно трудови што ги исполнуваат филтрите")
    truncated: bool = Field(
        False,
        description="Дали листата е скратена на `limit`; стеснете ги филтрите",
    )
    staff: str | None = Field(
        None,
        description="Пронајдениот вработен, ако е зададен `staff`",
    )
    items: list[ThesisMatch] | None = Field(
        None,
        description="Трудови, најновите прво",
    )
    error: str | None = Field(None, description="Порака за грешка")
    suggestions: list[str] | None = Field(None, description="Предлози")
