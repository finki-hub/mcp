from collections.abc import Callable
from typing import Final

from app.schemas.course import (
    AccreditationYear,
    CourseSyllabus,
    SemesterType,
    WeeklyHours,
)
from app.schemas.syllabus import BookPayload, SubjectPayload
from app.tools.course import _lookup_course
from app.utils.pubapi_client import (
    SyllabusNotFoundError,
    SyllabusUnavailableError,
    fetch_subject,
)

_MAX_BOOKS: Final = 5
_SEMESTER_TYPES: Final = {
    "WINTER": SemesterType.WINTER,
    "SUMMER": SemesterType.SUMMER,
}
_NO_CONTENT: Final = (
    "Официјалната содржина (темите) на предметот не е внесена во pubapi; "
    "не ја погодувај."
)


def _prose(text: str | None) -> str | None:
    return " ".join((text or "").split()) or None


def _lines(text: str | None) -> str | None:
    # Upstream indents with tabs or spaces at random; keep the line structure and a
    # single blank line between sections such as "Предавања:" and "Вежби:".
    lines: list[str] = []
    for raw in (text or "").splitlines():
        line = " ".join(raw.split())
        if line or (lines and lines[-1]):
            lines.append(line)
    return "\n".join(lines).strip() or None


def _localized(
    field: str,
    mk: str | None,
    en: str | None,
    normalize: Callable[[str | None], str | None],
    english_fields: list[str],
) -> str | None:
    value = normalize(mk)
    if value is None and (value := normalize(en)) is not None:
        english_fields.append(field)
    return value


def _book(book: BookPayload) -> str | None:
    if not (book.title or "").strip():
        return None
    parts = [book.author, book.title, book.publisher, str(book.year or "")]
    return ", ".join(p.strip() for p in parts if p and p.strip() and p != "0")


def _bibliography(subject: SubjectPayload) -> list[str] | None:
    books = subject.bibliography.books if subject.bibliography else []
    entries = [entry for book in books if (entry := _book(book))]
    return entries[:_MAX_BOOKS] or None


def _credits(value: float | None) -> int | float | None:
    if value is None:
        return None
    return int(value) if value.is_integer() else value


def _weekly_hours(subject: SubjectPayload) -> WeeklyHours:
    summary = subject.subject_dto
    return WeeklyHours(
        lectures=summary.weekly_lectures_classes or 0,
        auditory_exercises=summary.weekly_auditorium_classes or 0,
        lab_exercises=summary.weekly_lab_classes or 0,
    )


def get_course_syllabus(
    course_name: str,
    accreditation: AccreditationYear | None = None,
) -> CourseSyllabus:
    found = _lookup_course(course_name)
    if found.data is None:
        return CourseSyllabus(
            name=course_name,
            error=found.error,
            suggestions=found.suggestions,
        )

    course = found.data
    codes = {
        year: acc
        for year, acc in sorted(course.accreditations.items(), reverse=True)
        if acc.available and acc.code
    }
    base = CourseSyllabus(
        name=course.name,
        abbreviation=course.abbreviation,
        match_info=found.match_info,
    )
    if not codes:
        base.error = (
            f"Предметот „{course.name}“ нема код во ниедна акредитација, па "
            "силабусот не може да се преземе."
        )
        return base

    year = accreditation or next(iter(codes))
    others = [other for other in codes if other != year] or None
    if year not in codes:
        base.error = (
            f"Предметот „{course.name}“ не постои во акредитација {year}; "
            f"достапни се: {', '.join(codes)}."
        )
        base.other_accreditations = others
        return base

    selected = codes[year]
    code = selected.code or ""
    base.code = code
    base.accreditation = year
    base.other_accreditations = others
    try:
        subject = fetch_subject(code)
    except (SyllabusNotFoundError, SyllabusUnavailableError) as error:
        base.error = str(error)
        return base

    english_fields: list[str] = []
    syllabus = base.model_copy(
        update={
            "name": subject.subject_dto.name or course.name,
            "name_en": _prose(subject.name_en),
            "semester": subject.default_semester or selected.semester,
            "semester_type": _SEMESTER_TYPES.get(
                subject.subject_dto.semester_type or ""
            ),
            "credits": _credits(subject.credits) or selected.credits,
            "weekly_hours": _weekly_hours(subject),
            "language": _prose(subject.language),
            "goals": _localized(
                "goals",
                subject.goals_description,
                subject.goals_description_en,
                _prose,
                english_fields,
            ),
            "content": _localized(
                "content",
                subject.content,
                subject.content_en,
                _lines,
                english_fields,
            ),
            "learning_methods": _prose(subject.learning_methods),
            "bibliography": _bibliography(subject),
        },
    )
    syllabus.english_fields = english_fields or None
    if syllabus.content is None:
        syllabus.error = _NO_CONTENT
    return syllabus
