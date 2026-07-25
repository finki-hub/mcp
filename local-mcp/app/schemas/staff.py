from enum import StrEnum

from pydantic import BaseModel, Field

from app.schemas.base import PrunedModel


class StaffTitle(StrEnum):
    DOCTOR = "д-р"
    MASTER = "м-р"
    ENGINEER = "дипл. инж."


class StaffPosition(StrEnum):
    FULL_PROFESSOR = "Редовен професор"
    ASSOCIATE_PROFESSOR = "Вонреден професор"
    DOCENT = "Доцент"
    ASSISTANT = "Асистент докторанд"
    DEMONSTRATOR = "Демонстратор"
    ICT_ADVISOR = "Советник во одделение за ИКТ"
    SECRETARY = "Секретар"


class StaffMatch(PrunedModel):
    name: str = Field(
        ...,
        description="Име и презиме на вработениот",
        examples=["Александар Стојменски"],
    )
    title: str | None = Field(
        None,
        description="Титула на вработениот",
        examples=["д-р"],
    )
    position: str | None = Field(
        None,
        description="Позиција на вработениот.",
        examples=["Доцент"],
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
        examples=["Доцент"],
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


class StaffMember(PrunedModel):
    name: str = Field(
        ...,
        description="Име и презиме на вработениот",
        examples=["Александар Стојменски"],
    )
    staff: StaffProfile | None = Field(
        None,
        description="Податоци за вработениот",
    )
    error: str | None = Field(
        None,
        description="Порака за грешка ако вработениот не е пронајден",
        examples=["Вработениот „непознат“ не е пронајден"],
    )
    suggestions: list[str] | None = Field(
        None,
        description="Предложени имиња ако нема точно совпаѓање",
        examples=[["Александар Стојменски", "Александар Тенев"]],
    )
    match_info: dict | None = Field(
        None,
        description="Информации за совпаѓањето: барање, пронајден вработен, оценка и тип",
        examples=[
            {
                "original_query": "aleksandar stojmenski",
                "matched_staff": "Александар Стојменски",
                "similarity_score": 95,
                "match_type": "fuzzy",
            },
        ],
    )
