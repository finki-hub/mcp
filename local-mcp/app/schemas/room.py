from enum import StrEnum

from pydantic import BaseModel, Field

from app.schemas.base import PrunedModel


class RoomType(StrEnum):
    PVC_BOX = "PVC Кутија"
    AMPHITHEATER = "Амфитеатар"
    DEANERY = "Деканат"
    CABINET = "Кабинет"
    OFFICE = "Канцеларија"
    LABORATORY = "Лабораторија"
    LECTURE_HALL = "Предавална"
    HALL = "Сала"


class RoomLocation(StrEnum):
    MF_ANNEX = "Анекс на МФ"
    FEIT_ANNEX = "Анекс на ФЕИТ"
    BARRACKS = "Бараки"
    MF = "МФ"
    PF = "ПФ"
    TMF = "ТМФ"
    FEIT = "ФЕИТ"
    FINKI = "ФИНКИ"


class RoomMatch(PrunedModel):
    name: str = Field(
        ...,
        description="Име на просторијата",
        examples=["Ф10"],
    )
    type: str | None = Field(
        None,
        description="Тип на просторијата",
        examples=["Кабинет"],
    )
    location: str | None = Field(
        None,
        description="Локација на просторијата",
        examples=["Анекс на ФЕИТ"],
    )


class Room(BaseModel):
    name: str = Field(
        ...,
        description="Име на просторијата",
        examples=["Ф10"],
    )
    type: str | None = Field(
        None,
        description="Тип на просторијата",
        examples=["Кабинет"],
    )
    location: str | None = Field(
        None,
        description="Локација на просторијата",
        examples=["Анекс на ФЕИТ"],
    )
    description: str | None = Field(
        None,
        description="Насоки до просторијата",
        examples=["Низ влезот, па десно по ходникот"],
    )
    floor: str | None = Field(
        None,
        description="Кат на просторијата",
        examples=["1"],
    )
    capacity: str | None = Field(
        None,
        description="Капацитет на просторијата",
        examples=["40"],
    )
    mrbs: str | None = Field(
        None,
        description="Линк до MRBS распоредот за просторијата",
        examples=["https://mrbs.finki.ukim.mk/week.php?area=1&room=19"],
    )


class RoomData(BaseModel):
    name: str = Field(
        ...,
        description="Име на просторијата",
        examples=["Амфитеатар"],
    )
    rooms: list[Room] | None = Field(
        None,
        description="Податоци за сите простории со совпаднатото име",
    )
    error: str | None = Field(
        None,
        description="Порака за грешка ако просторијата не е пронајдена",
        examples=["Просторијата „непозната“ не е пронајдена"],
    )
    suggestions: list[str] | None = Field(
        None,
        description="Предложени простории ако нема точно совпаѓање",
        examples=[["Амфитеатар", "Мал Амфитеатар", "Голем Амфитеатар"]],
    )
    match_info: dict | None = Field(
        None,
        description="Информации за совпаѓањето: барање, пронајдена просторија, оценка и тип",
        examples=[
            {
                "original_query": "f10",
                "matched_room": "Ф10",
                "similarity_score": 100,
                "match_type": "exact",
            },
        ],
    )
