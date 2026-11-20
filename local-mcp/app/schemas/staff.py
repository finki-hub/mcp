from enum import StrEnum

from pydantic import BaseModel, Field

from app.schemas.base import PrunedModel

_DOCENT = "Доцент"
_STAFF_NAME_EXAMPLE = "Александар Стојменски"


class StaffTitle(StrEnum):
    DOCTOR = "д-р"
    MASTER = "м-р"
    ENGINEER = "дипл. инж."


class StaffPosition(StrEnum):
    FULL_PROFESSOR = "Редовен професор"
    ASSOCIATE_PROFESSOR = "Вонреден професор"
    DOCENT = _DOCENT
    ASSISTANT = "Асистент докторанд"
    DEMONSTRATOR = "Демонстратор"
    ICT_ADVISOR = "Советник во одделение за ИКТ"
    SECRETARY = "Секретар"


class StaffMatch(PrunedModel):
    name: str = Field(
        ...,
        description="Име и презиме на вработениот",
        examples=[_STAFF_NAME_EXAMPLE],
    )
    title: str | None = Field(
        None,
        description="Титула на вработениот",
        examples=["д-р"],
    )
    position: str | None = Field(
        None,
        description="Позиција на вработениот.",
        examples=[_DOCENT],
    )
    active: bool = Field(
        ...,
        description="Дали вработениот е активен или не (пензиониран).",
        examples=[True],
    )


class StaffProfile(BaseModel):
    title: str | None = Field(
        None,
        description="Титула на вработениот",
        examples=["д-р"],
    )
    position: str | None = Field(
        None,
        description="Позиција на вработениот.",
        examples=[_DOCENT],
    )
    active: bool = Field(
        ...,
        description="Дали вработениот е активен или не (пензиониран).",
        examples=[True],
    )
    email: str | None = Field(
        None,
        description="Е-пошта на вработениот",
        examples=["aleksandar.stojmenski@finki.ukim.mk"],
    )
    cabinet: str | None = Field(
        None,
        description="Канцеларија/кабинет на вработениот",
        examples=["Ф10 - Ф14"],
    )
    consultations: str | None = Field(
        None,
        description="Линк до распоредот за консултации",
        examples=["https://consultations.finki.ukim.mk/display/aleksandar.s"],
    )
    courses: str | None = Field(
        None,
        description="Линк до профилот на courses.finki.ukim.mk",
        examples=["https://courses.finki.ukim.mk/user/profile.php?id=8449"],
    )
    profile: str | None = Field(
        None,
        description="Линк до профилот на веб-страницата на ФИНКИ",
        examples=["https://www.finki.ukim.mk/mk/staff/aleksandar-tenev"],
    )
    photo: str | None = Field(
        None,
        description="Линк до фотографијата од профилот на ФИНКИ",
    )
