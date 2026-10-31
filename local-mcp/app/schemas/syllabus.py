from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class _Payload(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, frozen=True)


class SubjectSummaryPayload(_Payload):
    code: str
    name: str | None = None
    semester_type: str | None = None
    weekly_lectures_classes: int | None = None
    weekly_auditorium_classes: int | None = None
    weekly_lab_classes: int | None = None


class BookPayload(_Payload):
    author: str | None = None
    title: str | None = None
    publisher: str | None = None
    year: int | None = None


class BibliographyPayload(_Payload):
    books: list[BookPayload] = Field(default_factory=list)


class SubjectPayload(_Payload):
    subject_dto: SubjectSummaryPayload
    name_en: str | None = None
    default_semester: int | None = None
    credits: float | None = None
    language: str | None = None
    learning_methods: str | None = None
    goals_description: str | None = None
    content: str | None = None
    goals_description_en: str | None = None
    content_en: str | None = None
    bibliography: BibliographyPayload | None = None
