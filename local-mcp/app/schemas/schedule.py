from pydantic import Field

from app.schemas.base import PrunedModel
from app.schemas.timetable import TimetableDay


class ScheduleEntry(PrunedModel):
    course: str = Field(
        ...,
        description=(
            "Предмет; за заеднички час двата предмета со „/“, а името од "
            "распоредот кога не е поврзан со предмет"
        ),
        examples=["Вештачка интелигенција"],
    )
    kind: str | None = Field(
        None,
        description="Тип на часот како во распоредот: п (предавања), ав, лаб",
        examples=["п"],
    )
    day: TimetableDay = Field(..., description="Ден во неделата", examples=["Среда"])
    starts: str | None = Field(None, description="Почеток", examples=["08:10"])
    ends: str | None = Field(None, description="Крај", examples=["09:45"])
    room: str | None = Field(
        None,
        description="Просторија (име и локација); името од распоредот ако не е поврзана",
        examples=["Б2.2 (Бараки)"],
    )
    staff: list[str] | None = Field(
        None,
        description="Наставници; имињата од распоредот кога не се поврзани",
        examples=[["Весна Димитрова"]],
    )
    groups: str | None = Field(
        None,
        description="Класови од распоредот што го посетуваат часот",
        examples=["2г-КН, 2г-КИ"],
    )


class Schedule(PrunedModel):
    timetable: str | None = Field(
        None,
        description="Распоред од кој се термините (најновиот главен распоред)",
        examples=["raspored-zimski-2026-27-W (10/10/2026 - 15/1/2027)"],
    )
    matched: dict[str, str] | None = Field(
        None,
        description="Што се пронајде за секој филтер (вработен, предмет, просторија)",
        examples=[{"staff": "Весна Димитрова"}],
    )
    entries: list[ScheduleEntry] | None = Field(
        None,
        description="Термини, подредени по ден и време",
    )
    error: str | None = Field(
        None,
        description="Порака за грешка, на пр. кога филтерот не е пронајден",
        examples=["Вработениот „непознат“ не е пронајден"],
    )
    suggestions: list[str] | None = Field(
        None,
        description="Предлози кога филтерот е нееднозначен или не е пронајден",
        examples=[["Весна Димитрова", "Весна Димитриевска Ристовска"]],
    )
