from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.base import PrunedModel


class TimetableDay(StrEnum):
    MONDAY = "Понеделник"
    TUESDAY = "Вторник"
    WEDNESDAY = "Среда"
    THURSDAY = "Четврток"
    FRIDAY = "Петок"


class TimetableLessonType(StrEnum):
    LECTURE = "предавање"
    AUDITORY_EXERCISES = "аудиториски вежби"
    LABORATORY_EXERCISES = "лабораториски вежби"


class TimetableSummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    id: str = Field(
        ...,
        description="ID на распоредот.",
        examples=["28"],
    )
    title: str = Field(
        ...,
        description="Наслов на распоредот.",
        examples=["raspored-leten-2025-26-L (23/2 - 1/7/2026)"],
    )
    date_from: str = Field(
        ...,
        alias="dateFrom",
        description="Почетен датум на распоредот.",
        examples=["2026-02-23"],
    )
    year: int = Field(
        ...,
        description="Академска година на распоредот.",
        examples=[2025],
    )


class TimetableEntity(PrunedModel):
    id: str = Field(
        ...,
        description="ID на ставката во распоредот.",
        examples=["28"],
    )
    name: str = Field(
        ...,
        description="Име на ставката во распоредот.",
        examples=["Вештачка интелигенција"],
    )


class TimetableEntryGroup(PrunedModel):
    name: str = Field(
        ...,
        description="Име на групата.",
        examples=["2г-КН"],
    )
    subgroups: list[str] | None = Field(
        None,
        description="Подгрупи, доколку терминот важи само за дел од групата.",
        examples=[["Прва група"]],
    )


class TimetableEntry(PrunedModel):
    course: str = Field(
        ...,
        description="Име на предметот.",
        examples=["Вештачка интелигенција"],
    )
    professors: list[str] = Field(
        default_factory=list,
        description="Професори на терминот.",
        examples=[["Кире Триводалиев"]],
    )
    groups: list[TimetableEntryGroup] = Field(
        default_factory=list,
        description="Групи за кои важи терминот.",
    )
    room: str | None = Field(
        None,
        description="Просторија на терминот.",
        examples=["Барака 2.2"],
    )
    day: TimetableDay = Field(
        ...,
        description="Ден во неделата.",
        examples=["Понеделник"],
    )
    start_time: str = Field(
        ...,
        description="Време на почеток на терминот.",
        examples=["08:00"],
    )
    end_time: str = Field(
        ...,
        description="Време на крај на терминот.",
        examples=["09:45"],
    )
    duration_periods: int = Field(
        ...,
        description="Времетраење изразено во број на часови/периоди.",
        examples=[2],
    )
    lesson_types: list[TimetableLessonType] | None = Field(
        None,
        description="Типови на термин, доколку може да се одредат од името на предметот.",
        examples=[["предавање", "аудиториски вежби"]],
    )
