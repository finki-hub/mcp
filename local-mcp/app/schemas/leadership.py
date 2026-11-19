from enum import StrEnum

from pydantic import Field

from app.schemas.base import PrunedModel


class LeadershipBody(StrEnum):
    DEANS_OFFICE = "деканска управа"
    STUDENT_COUNCIL = "студентско собрание"


class LeadershipMember(PrunedModel):
    position: str = Field(
        ...,
        description=(
            "Функцијата: во деканската управа „Декан“ или продекан; во студентското "
            "собрание (ФСС) „Претседател“ или групата што членот ја претставува."
        ),
        examples=["Продекан за настава", "Претседател", "СИИС"],
    )
    name: str = Field(..., description="Име и презиме", examples=["Дејан Спасов"])
    title: str | None = Field(
        None, description="Титула (само за деканската управа)", examples=["д-р"]
    )
    staff_position: str | None = Field(
        None,
        description="Звање на вработениот (само за деканската управа)",
        examples=["Редовен професор"],
    )


class Leadership(PrunedModel):
    body: LeadershipBody = Field(..., description="Телото")
    year: int = Field(
        ...,
        description="Година кога започнал составот (мандатот)",
        examples=[2025],
    )
    members: list[LeadershipMember] = Field(..., description="Членовите по функција")
    years: list[int] = Field(
        ...,
        description="Сите години за кои постои состав, најновите прво",
        examples=[[2025, 2021, 2018]],
    )
