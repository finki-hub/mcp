from enum import StrEnum

from pydantic import BaseModel, Field

from app.schemas.base import ListPage, PrunedModel

_ELECTIVE = "изборен"
_COURSE_NAME_DESCRIPTION = "Име на предметот"


class StudyProgram(StrEnum):
    """
    Кодови на студиските програми. ИЕ (Информатичка едукација, акредитација 2023) е истата програма како КЕ (Компјутерска едукација, акредитација 2018).
    """

    KN = "КН"
    SIIS = "СИИС"
    PIT = "ПИТ"
    IMB = "ИМБ"
    KI = "КИ"
    KE = "КЕ"
    SEIS = "SEIS"
    IE = "ИЕ"
    SSP = "ССП"

    @classmethod
    def from_upstream(cls, code: str) -> str | None:
        try:
            return cls[code.upper()].value
        except KeyError:
            return None


class CourseStatus(StrEnum):
    MANDATORY = "задолжителен"
    ELECTIVE = _ELECTIVE


class SemesterType(StrEnum):
    """
    Зимски семестар = непарни семестри (1, 3, 5, 7), летен = парни (2, 4, 6, 8).
    """

    WINTER = "зимски"
    SUMMER = "летен"


class CourseTag(StrEnum):
    """
    Тематски ознаки (тагови). „филер“ = лесен предмет, „препорака на Стефан“ = личен избор на Стефан, создавачот на ФИНКИ Хаб.
    """

    AI = "AI"
    CODING = "програмирање"
    DATABASES = "бази на податоци"
    DELEMANGI = "препорака на Стефан"
    DEVOPS = "DevOps"
    FILLER = "филер"
    MATH = "математика"
    MOBILE = "мобилни технологии"
    NETWORKING = "компјутерски мрежи"
    SECURITY = "безбедност"
    WEB = "веб"

    @classmethod
    def from_upstream(cls, tag: str) -> str | None:
        try:
            return cls[tag.upper()].value
        except KeyError:
            return None


class AccreditationYear(StrEnum):
    Y2018 = "2018"
    Y2023 = "2023"


class Staff(BaseModel):
    professors: list[str] = Field(
        default_factory=list,
        description="Професори кои го предаваат предметот",
        examples=[["Ѓорѓи Маџаров", "Ана Мадевска Богданова"]],
    )
    assistants: list[str] = Field(
        default_factory=list,
        description="Асистенти на предметот",
        examples=[["Александар Тенев", "Влатко Спасев"]],
    )
    inactive: bool = Field(
        False,
        description="Дали предметот е неактивен",
        examples=[False],
    )


class Accreditation(BaseModel):
    available: bool = Field(
        ...,
        description="Дали предметот постои во оваа акредитација",
        examples=[True],
    )
    name: str | None = Field(
        None,
        description=_COURSE_NAME_DESCRIPTION,
        examples=["Структурно програмирање"],
    )
    code: str | None = Field(
        None,
        description="Код на предметот",
        examples=["F23L1W020"],
    )
    level: int | None = Field(
        None,
        description="Ниво на предметот (1–3)",
        examples=[1],
    )
    semester: int | None = Field(
        None,
        description="Семестар (1–8)",
        examples=[1],
    )
    credits: int | None = Field(
        None,
        description="Број на ЕКТС кредити",
        examples=[6],
    )
    prerequisite: str | None = Field(
        None,
        description="Предуслов, доколку постои",
        examples=["Машинско учење"],
    )
    offered_in: dict[str, str] | None = Field(
        None,
        description=(
            "Статус по студиска програма: клуч е кодот на програмата (на пр. „КН“, "
            "„СИИС“), вредност „задолжителен“ или „изборен“. Програмите каде предметот "
            "не се нуди не се вклучени. ИЕ (акредитација 2023) е истата програма како КЕ "
            "(акредитација 2018)."
        ),
        examples=[{"КН": "задолжителен", "СИИС": _ELECTIVE}],
    )


class CourseData(BaseModel):
    name: str
    abbreviation: str | None = None
    tags: list[str]
    channel: bool
    staff: Staff
    participants: dict[str, int]
    accreditations: dict[str, Accreditation]


class _CourseLookup(PrunedModel):
    name: str = Field(
        ...,
        description=_COURSE_NAME_DESCRIPTION,
        examples=["Структурно програмирање"],
    )
    abbreviation: str | None = Field(
        None,
        description="Кратенка на предметот",
        examples=["СП"],
    )
    error: str | None = Field(
        None,
        description="Порака за грешка ако предметот не е пронајден",
        examples=["Предметот „структурно програмирање“ не е пронајден"],
    )
    suggestions: list[str] | None = Field(
        None,
        description="Предложени предмети ако нема точно совпаѓање",
        examples=[["Алгоритми и податочни структури", "Бази на податоци"]],
    )
    match_info: dict | None = Field(
        None,
        description="Информации за совпаѓањето: барање, пронајден предмет, оценка и тип",
        examples=[
            {
                "original_query": "веб програмирање",
                "matched_course": "Веб програмирање",
                "similarity_score": 95,
                "match_type": "fuzzy",
            },
        ],
    )


class Course(_CourseLookup):
    tags: list[str] | None = Field(
        None,
        description="Тематски ознаки (тагови) поврзани со предметот",
        examples=[["AI", "програмирање"]],
    )
    channel: bool | None = Field(
        None,
        description="Дали предметот има посветен Discord канал",
        examples=[True],
    )
    accreditations: dict[str, Accreditation] | None = Field(
        None,
        description="Податоци по акредитација; клуч е годината на акредитацијата (на пр. „2018“, „2023“)",
    )


class CourseStaff(_CourseLookup):
    staff: Staff | None = Field(
        None,
        description="Наставен кадар (професори и асистенти)",
    )


class CourseParticipants(_CourseLookup):
    participants: dict[str, int] | None = Field(
        None,
        description="Број на запишани студенти по академска година (клуч „ГГГГ/ГГГГ“)",
        examples=[{"2024/2025": 1608, "2023/2024": 1758}],
    )


class AccreditationMatch(PrunedModel):
    offered_in: dict[str, str] | None = Field(
        None,
        description="Статус во филтрираната студиска програма",
        examples=[{"КН": _ELECTIVE}],
    )
    programs: str | None = Field(
        None,
        description=(
            "Програми каде предметот го има филтрираниот статус, одделени со запирка "
            "(со евентуална напомена, на пр. „КН (4 г.)“ = само за четиригодишната "
            "варијанта)"
        ),
        examples=["КН, СИИС (4 г.)"],
    )
    semester: int | None = Field(
        None,
        description="Семестар во оваа акредитација (се изоставува ако е филтриран)",
        examples=[5],
    )


class CourseMatch(PrunedModel):
    name: str = Field(
        ...,
        description=_COURSE_NAME_DESCRIPTION,
        examples=["Веб програмирање"],
    )
    abbreviation: str | None = Field(
        None,
        description="Кратенка на предметот",
        examples=["ВебП"],
    )
    tags: list[str] | None = Field(
        None,
        description="Тематски ознаки (тагови) на предметот",
        examples=[["AI", "веб"]],
    )
    professors: list[str] | None = Field(
        None,
        description="Совпаднати професори",
        examples=[["Димитар Трајанов"]],
    )
    assistants: list[str] | None = Field(
        None,
        description="Совпаднати асистенти",
        examples=[["Ана Тодоровска"]],
    )
    participants: int | None = Field(
        None,
        description="Број на запишани студенти во `participants_year`",
        examples=[42],
    )
    accreditations: dict[str, AccreditationMatch] | None = Field(
        None,
        description="Совпаѓања по акредитација (клуч е годината на акредитацијата)",
    )


class CourseList(ListPage[CourseMatch]):
    participants_year: str | None = Field(
        None,
        description="Академска година за која е даден бројот на запишани студенти",
        examples=["2026/2027"],
    )
