from enum import StrEnum

from pydantic import Field

from app.schemas.base import PrunedModel


class StatsMetric(StrEnum):
    TOP_COURSES = "top_courses"
    THESES_PER_YEAR = "theses_per_year"
    TOP_MENTORS = "top_mentors"
    TEACHING_LOAD = "teaching_load"


class StatRow(PrunedModel):
    label: str = Field(
        ...,
        description="Предмет, вработен или година",
        examples=["Алгоритми и податочни структури"],
    )
    value: int = Field(..., description="Вредноста по која е подредено", examples=[877])
    parts: dict[str, int] | None = Field(
        None,
        description="Поделба на вредноста, на пр. дипломски и магистерски",
        examples=[{"bachelor": 310, "master": 12}],
    )


class Stats(PrunedModel):
    metric: StatsMetric = Field(..., description="Пресметаната статистика")
    scope: str | None = Field(
        None,
        description="На што се однесува: академска година, распоред, вработен",
        examples=["2025/2026"],
    )
    unit: str | None = Field(
        None,
        description="Што брои `value`",
        examples=["запишани студенти"],
    )
    total: int | None = Field(
        None,
        description="Вкупно редови пред `limit`",
        examples=[178],
    )
    rows: list[StatRow] | None = Field(
        None,
        description="Редови: најголемите прво, а за `theses_per_year` најновата година прво",
    )
    error: str | None = Field(None, description="Порака за грешка")
    suggestions: list[str] | None = Field(None, description="Предлози")
