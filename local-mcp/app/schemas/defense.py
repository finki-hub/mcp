import re
from dataclasses import dataclass
from typing import Annotated, Final

from pydantic import AfterValidator, BaseModel, ConfigDict, Field
from pydantic_core import PydanticCustomError

from app.schemas.base import PrunedModel
from app.schemas.defense_progress import diploma_progress, master_progress

STUDENT_LABEL_PATTERN: Final = re.compile(
    r"\s*([0-9]+)\s*-\s*(\S(?:.*\S)?)\s*",
)


@dataclass(slots=True)  # MUTABLE_OK: CPython writes traceback metadata onto exceptions.
class InvalidUpstreamStudentError(ValueError):
    def __str__(self) -> str:
        return "student must contain an ASCII numeric prefix, hyphen, and name"


@dataclass(frozen=True, slots=True)
class ParsedUpstreamStudent:
    raw: str
    canonical_index: str
    name: str


def parse_upstream_student(raw: str) -> ParsedUpstreamStudent:
    match = STUDENT_LABEL_PATTERN.fullmatch(raw)
    if match is None:
        raise InvalidUpstreamStudentError

    index, name = match.groups()
    return ParsedUpstreamStudent(
        raw=raw,
        canonical_index=index.lstrip("0") or "0",
        name=name,
    )


def _preserve_valid_student(raw: str) -> str:
    parse_upstream_student(raw)
    return raw


def _bounded_text(max_length: int) -> AfterValidator:
    def validate(value: str) -> str:
        if len(value) > max_length:
            raise PydanticCustomError(
                "string_too_long", "string exceeds internal field limit"
            )
        return value

    return AfterValidator(validate)


DefenseScalarText = Annotated[str, _bounded_text(256)]
DefenseDescriptionText = Annotated[str, _bounded_text(8192)]
DefenseTitleText = Annotated[str, _bounded_text(1024)]
ValidatedUpstreamStudent = Annotated[
    str,
    _bounded_text(256),
    AfterValidator(_preserve_valid_student),
]


class DefenseMatch(BaseModel):
    model_config = ConfigDict(frozen=True)

    student: str = Field(
        ...,
        description="Студент во формат „број на индекс - име“.",
        examples=["95110 - Ана Анова"],
    )
    mentor: str = Field(
        ...,
        description="Име на менторот.",
        examples=["Бојан Јовановски"],
    )
    title: str = Field(
        ...,
        description="Наслов на трудот.",
        examples=["Пример за тема на труд"],
    )


class Diploma(BaseModel):
    model_config = ConfigDict(frozen=True)

    date_of_submission: str = Field(
        ...,
        description="Датум на пријавување на дипломската работа.",
        examples=["10.07.2026"],
    )
    description: str = Field(
        ...,
        description="Опис на дипломската работа.",
        examples=["Краток опис на трудот."],
    )
    file_id: str | None = Field(
        ...,
        description="ID на датотеката за преземање, ако е достапна.",
        examples=["42", None],
    )
    member1: str = Field(
        ...,
        description="Прв член на комисијата.",
        examples=["Весна Димитрова"],
    )
    member2: str = Field(
        ...,
        description="Втор член на комисијата.",
        examples=["Марко Николов"],
    )
    mentor: str = Field(
        ...,
        description="Име на менторот.",
        examples=["Бојан Јовановски"],
    )
    status: str = Field(
        ...,
        description="Статус на дипломската работа.",
        examples=["Одбрана"],
    )
    progress: str = Field(
        ...,
        description="Тековен чекор во формат „x/y“.",
        examples=["8/8"],
        pattern=r"^[0-9]+/[0-9]+$",
    )
    student: str = Field(
        ...,
        description="Студент во формат „број на индекс - име“.",
        examples=["95110 - Ана Анова"],
    )
    title: str = Field(
        ...,
        description="Наслов на дипломската работа.",
        examples=["Пример за тема на дипломска работа"],
    )


class MasterDefense(BaseModel):
    model_config = ConfigDict(frozen=True)

    date_of_presentation: str = Field(
        ...,
        description="Датум на презентација на магистерскиот труд.",
        examples=["10.07.2026"],
    )
    description: str = Field(
        ...,
        description="Опис на магистерскиот труд.",
        examples=["Краток опис на трудот."],
    )
    file_id: str | None = Field(
        ...,
        description="ID на датотеката за преземање, ако е достапна.",
        examples=["42", None],
    )
    member: str = Field(
        ...,
        description="Член на комисијата.",
        examples=["Весна Димитрова"],
    )
    mentor: str = Field(
        ...,
        description="Име на менторот.",
        examples=["Бојан Јовановски"],
    )
    president: str = Field(
        ...,
        description="Претседател на комисијата.",
        examples=["Марко Николов"],
    )
    status: str = Field(
        ...,
        description="Статус на магистерскиот труд.",
        examples=["24. Магистерската е завршена."],
    )
    progress: str = Field(
        ...,
        description="Тековен чекор во формат „x/y“.",
        examples=["24/25"],
        pattern=r"^[0-9]+/[0-9]+$",
    )
    student: str = Field(
        ...,
        description="Студент во формат „број на индекс - име“.",
        examples=["95110 - Ана Анова"],
    )
    title: str = Field(
        ...,
        description="Наслов на магистерскиот труд.",
        examples=["Пример за тема на магистерски труд"],
    )


class DiplomaPayload(BaseModel):
    model_config = ConfigDict(frozen=True)

    date_of_submission: DefenseScalarText = Field(
        ..., validation_alias="dateOfSubmission"
    )
    description: DefenseDescriptionText = Field(...)
    file_id: DefenseScalarText | None = Field(..., validation_alias="fileId")
    member1: DefenseScalarText = Field(...)
    member2: DefenseScalarText = Field(...)
    mentor: DefenseScalarText = Field(...)
    status: DefenseScalarText = Field(...)
    student: ValidatedUpstreamStudent = Field(...)
    title: DefenseTitleText = Field(...)

    def to_public(self) -> Diploma:
        return Diploma(
            date_of_submission=self.date_of_submission,
            description=self.description,
            file_id=self.file_id,
            member1=self.member1,
            member2=self.member2,
            mentor=self.mentor,
            status=self.status,
            progress=diploma_progress(self.status),
            student=self.student,
            title=self.title,
        )


class MasterPayload(BaseModel):
    model_config = ConfigDict(frozen=True)

    date_of_presentation: DefenseScalarText = Field(
        ..., validation_alias="dateOfPresentation"
    )
    description: DefenseDescriptionText = Field(...)
    file_id: DefenseScalarText | None = Field(..., validation_alias="fileId")
    member: DefenseScalarText = Field(...)
    mentor: DefenseScalarText = Field(...)
    president: DefenseScalarText = Field(...)
    status: DefenseScalarText = Field(...)
    student: ValidatedUpstreamStudent = Field(...)
    title: DefenseTitleText = Field(...)

    def to_public(self) -> MasterDefense:
        return MasterDefense(
            date_of_presentation=self.date_of_presentation,
            description=self.description,
            file_id=self.file_id,
            member=self.member,
            mentor=self.mentor,
            president=self.president,
            status=self.status,
            progress=master_progress(self.status),
            student=self.student,
            title=self.title,
        )


class DiplomaResult(PrunedModel):
    model_config = ConfigDict(frozen=True)

    diploma: Diploma | None = Field(
        None,
        description="Податоци за пронајдената дипломска работа.",
        examples=[None],
    )
    error: str | None = Field(
        None,
        description="Порака за грешка при пребарувањето.",
        examples=["Дипломската работа не е пронајдена."],
    )
    suggestions: list[DefenseMatch] | None = Field(
        None,
        description="Предлози ако нема еднозначно совпаѓање.",
        examples=[[]],
    )


class MasterResult(PrunedModel):
    model_config = ConfigDict(frozen=True)

    master: MasterDefense | None = Field(
        None,
        description="Податоци за пронајдениот магистерски труд.",
        examples=[None],
    )
    error: str | None = Field(
        None,
        description="Порака за грешка при пребарувањето.",
        examples=["Магистерската одбрана не е пронајдена."],
    )
    suggestions: list[DefenseMatch] | None = Field(
        None,
        description="Предлози ако нема еднозначно совпаѓање.",
        examples=[[]],
    )
