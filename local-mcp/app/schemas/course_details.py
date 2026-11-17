from enum import StrEnum

from pydantic import Field

from app.schemas.base import PrunedModel
from app.schemas.schedule import ScheduleEntry


class CourseInclude(StrEnum):
    CURRICULA = "curricula"
    SYLLABUS = "syllabus"
    EQUIVALENCIES = "equivalencies"
    ENROLLMENTS = "enrollments"
    TEACHING = "teaching"
    SCHEDULE = "schedule"
    PROGRAMS = "programs"


class CourseInProgram(PrunedModel):
    program: str = Field(..., description="Код на програмата", examples=["BKK23_2"])
    kind: str = Field(
        ...,
        description="mandatory (задолжителен) или elective (изборен)",
        examples=["mandatory"],
    )
    semester: int | None = Field(
        None,
        description="Семестар; за изборен препорачаниот",
        examples=[3],
    )
    group: str | None = Field(
        None,
        description=(
            "Изборна група: program_winter, program_summer, faculty_winter, "
            "faculty_summer или named"
        ),
        examples=["faculty_winter"],
    )
    code: str | None = Field(None, description="Код на предметот во програмата")


class CourseCurriculum(PrunedModel):
    accreditation: str = Field(..., description="Акредитација", examples=["2023"])
    code: str | None = Field(
        None, description="Код на предметот", examples=["F23L2W001"]
    )
    name: str | None = Field(
        None,
        description="Име во оваа акредитација, ако е различно",
    )
    semester: int | None = Field(None, description="Семестар (1-8)", examples=[3])
    credits: int | None = Field(None, description="ЕКТС кредити", examples=[6])
    available: bool | None = Field(
        None,
        description="Дали се нуди во акредитацијата",
        examples=[True],
    )
    prerequisites: str | None = Field(
        None,
        description="Предуслови",
        examples=["Структурно програмирање"],
    )
    programs: dict[str, str] | None = Field(
        None,
        description="Статус по студиска програма (кратенка: задолжителен/изборен), без „нема“",
        examples=[{"КН": "задолжителен", "ПИТ": "изборен"}],
    )


class CourseSyllabusText(PrunedModel):
    objectives: str | None = Field(None, description="Цели на предметот")
    content: str | None = Field(
        None,
        description="Содржина (теми по недели, предавања и вежби)",
    )
    objectives_en: str | None = Field(None, description="Цели на англиски")
    content_en: str | None = Field(None, description="Содржина на англиски")


class CourseTeacher(PrunedModel):
    staff: str = Field(..., description="Наставник", examples=["Весна Димитрова"])
    role: str = Field(
        ..., description="professor или assistant", examples=["professor"]
    )
    periods: int = Field(..., description="Неделни часови", examples=[2])


class CourseDetails(PrunedModel):
    name: str = Field(..., description="Име на предметот", examples=["Криптографија"])
    name_en: str | None = Field(None, description="Име на англиски")
    abbreviation: str | None = Field(None, description="Кратенка", examples=["АПС"])
    cycle: str | None = Field(
        None,
        description="Циклус: first (додипломски) или second (магистерски)",
        examples=["second"],
    )
    status: str | None = Field(None, description="Статус", examples=["active"])
    tags: str | None = Field(None, description="Ознаки", examples=["security"])
    curricula: list[CourseCurriculum] | None = Field(
        None,
        description="Предметот во секоја акредитација (со `curricula`)",
    )
    syllabus: CourseSyllabusText | None = Field(
        None,
        description="Цели и содржина од силабусот (со `syllabus`)",
    )
    equivalencies: list[list[str]] | None = Field(
        None,
        description=(
            "Групи еквивалентни предмети низ акредитациите, секој како "
            "„име (акредитација)“ (со `equivalencies`)"
        ),
        examples=[[["Алгоритми и податочни структури (2023)", "Алгоритми (2013)"]]],
    )
    enrollments: dict[str, int] | None = Field(
        None,
        description="Запишани студенти по академска година, најновата прва (со `enrollments`)",
        examples=[{"2026/2027": 468, "2025/2026": 877}],
    )
    teaching_timetable: str | None = Field(
        None,
        description=(
            "Најновиот главен распоред во кој се држи предметот, од кој е `teaching` "
            "(летен предмет во зимскиот семестар го покажува минатиот летен)"
        ),
    )
    teaching: list[CourseTeacher] | None = Field(
        None,
        description="Наставници во `teaching_timetable` (со `teaching`)",
    )
    timetable: str | None = Field(
        None,
        description="Тековниот главен распоред, од кој е `schedule`",
    )
    schedule: list[ScheduleEntry] | None = Field(
        None,
        description="Термини во тековниот главен распоред (со `schedule`)",
    )
    programs: list[CourseInProgram] | None = Field(
        None,
        description=(
            "Магистерските програми во кои е предметот, со вид, семестар и група "
            "(со `programs`)"
        ),
    )
    error: str | None = Field(None, description="Порака за грешка")
    suggestions: list[str] | None = Field(None, description="Предлози")
