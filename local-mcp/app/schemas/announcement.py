from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.base import PrunedModel


class RenderedText(BaseModel):
    model_config = ConfigDict(frozen=True)

    rendered: str


class AnnouncementPayload(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int
    date: datetime
    modified: datetime
    link: str
    title: RenderedText
    content: RenderedText


class AnnouncementMatch(PrunedModel):
    id: int = Field(
        ...,
        description="ID на огласот; се користи со get_announcement за целиот текст.",
        examples=[21653],
    )
    title: str = Field(
        ...,
        description="Наслов на огласот.",
        examples=[
            "Продолжување на рокот за заверка на летен и упис на зимски семестар 2026/2027"
        ],
    )
    published: date = Field(
        ...,
        description="Датум на објавување.",
        examples=["2026-09-17"],
    )
    updated: date | None = Field(
        None,
        description="Датум на последна измена, само ако се разликува од датумот на објавување.",
        examples=["2026-10-01"],
    )
    url: str = Field(
        ...,
        description="Линк до огласот на finki.ukim.mk.",
        examples=["https://finki.ukim.mk/announcements/prodolzhuvanje-na-rokot/"],
    )
    excerpt: str = Field(
        ...,
        description="Извадок од текстот околу најрелевантниот дел.",
        examples=[
            "Заверката на летниот и запишувањето на зимскиот семестар е продолжено до 19.09.2026."
        ],
    )


class AnnouncementSearchResult(BaseModel):
    announcements: list[AnnouncementMatch] = Field(
        ...,
        description="Пронајдени огласи, подредени според релевантност и датум.",
    )
    fetched_at: datetime = Field(
        ...,
        description="Време (UTC) кога огласите последен пат се преземени од finki.ukim.mk.",
        examples=["2026-10-24T15:30:00Z"],
    )
    stale: bool = Field(
        ...,
        description="Дали огласите се од постара копија бидејќи освежувањето не успеало.",
        examples=[False],
    )


class AnnouncementDetail(PrunedModel):
    id: int = Field(..., description="ID на огласот.", examples=[21653])
    title: str = Field(
        ...,
        description="Наслов на огласот.",
        examples=[
            "Продолжување на рокот за заверка на летен и упис на зимски семестар 2026/2027"
        ],
    )
    published: date = Field(
        ...,
        description="Датум на објавување.",
        examples=["2026-09-17"],
    )
    updated: date | None = Field(
        None,
        description="Датум на последна измена, само ако се разликува од датумот на објавување.",
        examples=["2026-10-01"],
    )
    url: str = Field(
        ...,
        description="Линк до огласот на finki.ukim.mk.",
        examples=["https://finki.ukim.mk/announcements/prodolzhuvanje-na-rokot/"],
    )
    text: str = Field(
        ...,
        description="Текст на огласот без HTML; пасусите и ставките од листи се во посебни редови.",
        examples=[
            "Почитувани студенти,\nЗаверката на летниот и запишувањето на зимскиот семестар е продолжено до 19.09.2026."
        ],
    )
    truncated: bool = Field(
        ...,
        description="Дали текстот е скратен поради должина.",
        examples=[False],
    )
