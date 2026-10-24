from enum import StrEnum

from pydantic import Field

from app.schemas.base import PrunedModel


class StudyCycle(StrEnum):
    FIRST = "прв"
    SECOND = "втор"
    THIRD = "трет"


class StudyProgramInfo(PrunedModel):
    code: str = Field(
        ...,
        description="Код на програмата на ФИНКИ (суфикс _3 = тригодишна варијанта)",
        examples=["KN23"],
    )
    abbreviation: str | None = Field(
        None,
        description="Кратенка што се користи како `program` во `list_courses` (само прв циклус)",
        examples=["КН"],
    )
    name: str = Field(
        ...,
        description="Име на програмата",
        examples=["Компјутерски науки"],
    )
    name_en: str | None = Field(
        None,
        description="Име на програмата на англиски",
        examples=["Computer Science"],
    )
    cycle: StudyCycle = Field(
        ...,
        description="Циклус на студии",
        examples=["прв"],
    )
    duration_years: int | None = Field(
        None,
        description="Времетраење во години",
        examples=[4],
    )
    accreditation: str | None = Field(
        None,
        description="Година на акредитација",
        examples=["2023"],
    )
    language: str | None = Field(
        None,
        description=(
            "Јазик на настава. Наведен е само кога е официјално потврден; ако го нема, "
            "јазикот не е познат и не треба да се претпоставува."
        ),
        examples=["англиски"],
    )
    url: str | None = Field(
        None,
        description="Линк до страницата на програмата",
        examples=["https://finki.ukim.mk/program/KN23"],
    )
