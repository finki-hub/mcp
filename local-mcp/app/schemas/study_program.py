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
    title: str | None = Field(
        None,
        description="Звање што се стекнува по завршување на програмата",
        examples=["Магистер по Безбедност, криптографија и кодирање"],
    )
    title_en: str | None = Field(
        None,
        description="Звање на англиски",
        examples=["Bachelor of Science in Computer Science"],
    )
    ects: int | None = Field(
        None,
        description="Вкупен број ЕКТС кредити на програмата",
        examples=[240],
    )
    coordinator: str | None = Field(
        None,
        description="Координатор на програмата (магистерски студии)",
        examples=["Весна Димитрова"],
    )
    description: str | None = Field(
        None,
        description=(
            "Општи информации за програмата, на јазикот на кој ги дава "
            "страницата (само со `details`)"
        ),
    )
    rules: str | None = Field(
        None,
        description=(
            "Правила на наставната програма: број на предмети, ограничувања на "
            "изборните предмети по тежина, екстракурикуларни кредити (само со "
            "`details`)"
        ),
    )
