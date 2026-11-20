from enum import StrEnum

from pydantic import Field

from app.schemas.base import PrunedModel


class LeadershipBody(StrEnum):
    DEANS_OFFICE = "деканат"
    STUDENT_COUNCIL = "студентско собрание"
    MANAGEMENT_BOARD = "деканатска управа"
    COUNCIL = "ннс"
    INSTITUTES = "институти"
    CENTERS = "центри"


class LeadershipMember(PrunedModel):
    position: str | None = Field(
        None,
        description=(
            "Функцијата: во деканатот „Декан“, продекан или „Секретар“; во "
            "деканатската управа и раководителите на институти; во студентското "
            "собрание (ФСС) "
            "„Претседател“ или групата што членот ја претставува. Членовите на ННС "
            "немаат функција."
        ),
        examples=["Продекан за настава", "Претседател", "СИИС"],
    )
    name: str = Field(..., description="Име и презиме", examples=["Дејан Спасов"])
    title: str | None = Field(
        None, description="Титула (не за студентското собрание)", examples=["д-р"]
    )
    staff_position: str | None = Field(
        None,
        description="Звање на вработениот (не за студентското собрание)",
        examples=["Редовен професор"],
    )


class FacultyUnit(PrunedModel):
    name: str = Field(
        ...,
        description="Име на институтот или центарот",
        examples=["Институт за софтверско инженерство"],
    )
    page: str | None = Field(None, description="Страница на finki.ukim.mk")
    head: LeadershipMember | None = Field(None, description="Раководител")
    members: list[str] | None = Field(
        None,
        description="Членови на институтот (само за институти)",
        examples=[["Иван Чорбев", "Бобан Јоксимоски"]],
    )


class Leadership(PrunedModel):
    body: LeadershipBody = Field(..., description="Телото")
    year: int | None = Field(
        None,
        description=(
            "Година кога започнал составот (мандатот); само за деканатот и "
            "студентското собрание, другите се тековниот состав"
        ),
        examples=[2025],
    )
    members: list[LeadershipMember] | None = Field(
        None, description="Членовите по функција (не за институти и центри)"
    )
    units: list[FacultyUnit] | None = Field(
        None, description="Институтите или центрите (само за нив)"
    )
    years: list[int] | None = Field(
        None,
        description="Сите години за кои постои состав, најновите прво",
        examples=[[2025, 2021, 2018]],
    )
