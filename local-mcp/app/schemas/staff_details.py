from enum import StrEnum

from pydantic import Field

from app.schemas.base import PrunedModel
from app.schemas.schedule import ScheduleEntry
from app.schemas.staff import StaffProfile


class StaffInclude(StrEnum):
    TEACHING = "teaching"
    SCHEDULE = "schedule"
    THESES = "theses"
    PROGRAMS = "programs"
    BIO = "bio"


class TaughtCourse(PrunedModel):
    course: str = Field(..., description="Предмет", examples=["Криптографија"])
    role: str = Field(
        ...,
        description="Улога според позицијата: professor или assistant",
        examples=["professor"],
    )
    periods: int = Field(
        ...,
        description="Неделни часови на предметот во распоредот",
        examples=[4],
    )


class ThesisRoleCounts(PrunedModel):
    mentor: int = Field(0, description="Како ментор", examples=[42])
    member: int = Field(0, description="Како член на комисија", examples=[80])
    president: int = Field(
        0,
        description="Како претседател на комисија (само магистерски)",
        examples=[3],
    )


class MentoredThesis(PrunedModel):
    kind: str = Field(
        ...,
        description="bachelor (дипломска) или master (магистерска)",
        examples=["bachelor"],
    )
    title: str = Field(..., description="Наслов на трудот")
    student: str | None = Field(None, description="Студент", examples=["Ана Анова"])
    status: str | None = Field(None, description="Статус на трудот")
    year: int | None = Field(None, description="Година", examples=[2026])


class StaffTheses(PrunedModel):
    bachelor: ThesisRoleCounts = Field(..., description="Дипломски работи по улога")
    master: ThesisRoleCounts = Field(..., description="Магистерски трудови по улога")
    recent_mentored: list[MentoredThesis] | None = Field(
        None,
        description="Најновите трудови каде е ментор (до 5); целосно со `find_theses`",
    )


class CoordinatedProgram(PrunedModel):
    code: str = Field(..., description="Код на програмата", examples=["BKK23_2"])
    name: str = Field(
        ...,
        description="Име на програмата",
        examples=["Безбедност, криптографија и кодирање"],
    )


class StaffDetails(PrunedModel):
    name: str = Field(..., description="Име и презиме", examples=["Весна Димитрова"])
    staff: StaffProfile | None = Field(None, description="Податоци за вработениот")
    institute: str | None = Field(
        None,
        description="Институтот на кој припаѓа",
        examples=["Институт за софтверско инженерство"],
    )
    roles: list[str] | None = Field(
        None,
        description=(
            "Функции на факултетот: во деканатската управа, раководител на институт "
            "или центар, член на ННС"
        ),
        examples=[["Продекан за настава", "Член на Наставно-научниот совет (ННС)"]],
    )
    bio: str | None = Field(
        None,
        description="Биографија од профилот на ФИНКИ (со `bio`)",
    )
    timetable: str | None = Field(
        None,
        description="Распоредот од кој се `teaching` и `schedule`",
    )
    teaching: list[TaughtCourse] | None = Field(
        None,
        description="Предмети што ги држи во најновиот главен распоред (со `teaching`)",
    )
    schedule: list[ScheduleEntry] | None = Field(
        None,
        description="Термини во најновиот главен распоред (со `schedule`)",
    )
    theses: StaffTheses | None = Field(
        None,
        description="Менторства и комисии (со `theses`)",
    )
    programs: list[CoordinatedProgram] | None = Field(
        None,
        description="Студиски програми што ги координира (со `programs`)",
    )
    error: str | None = Field(
        None,
        description="Порака за грешка ако вработениот не е пронајден",
    )
    suggestions: list[str] | None = Field(
        None,
        description="Предложени имиња ако нема точно совпаѓање",
    )
