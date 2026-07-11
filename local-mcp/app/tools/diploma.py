from dataclasses import dataclass
from enum import StrEnum
from typing import assert_never

from app.schemas.defense import DefenseMatch, Diploma, DiplomaResult
from app.tools.defense import (
    DefenseLookupFailure,
    DefenseLookupSuccess,
    StudentIndexFilter,
    StudentNameFilter,
    collapse_defense_records,
    filter_defense_records,
    parse_optional_student_filter,
    parse_student_filter,
    resolve_defense_lookup,
    strip_list_filter,
    to_defense_matches,
)
from app.utils.http_client import get_diplomas


class DiplomaFilterError(StrEnum):
    REQUIRED = "Внесете барем еден филтер за дипломските работи."
    INDEX_EXCLUSIVE = "Индексот не може да се комбинира со ментор или наслов."


@dataclass(frozen=True, slots=True)
class InvalidDiplomaFiltersError(ValueError):
    category: DiplomaFilterError

    def __str__(self) -> str:
        return self.category.value


def _effective_diplomas() -> list[Diploma]:
    return collapse_defense_records(
        get_diplomas(),
        lambda diploma: diploma.date_of_submission,
    )


def list_diplomas(
    student: str | None = None,
    mentor: str | None = None,
    title: str | None = None,
) -> list[DefenseMatch]:
    student_filter = parse_optional_student_filter(student)
    mentor_filter = strip_list_filter(mentor)
    title_filter = strip_list_filter(title)

    if student_filter is None and mentor_filter is None and title_filter is None:
        raise InvalidDiplomaFiltersError(DiplomaFilterError.REQUIRED)

    match student_filter:
        case StudentIndexFilter():
            if mentor_filter is not None or title_filter is not None:
                raise InvalidDiplomaFiltersError(DiplomaFilterError.INDEX_EXCLUSIVE)
        case StudentNameFilter() | None:
            pass
        case unreachable:
            assert_never(unreachable)

    records = _effective_diplomas()
    matches = filter_defense_records(
        records,
        student=student_filter,
        mentor=mentor_filter,
        title=title_filter,
    )
    return to_defense_matches(matches)


def get_diploma(student: str) -> DiplomaResult:
    records = _effective_diplomas()
    outcome = resolve_defense_lookup(records, parse_student_filter(student))
    match outcome:
        case DefenseLookupSuccess(record=record):
            return DiplomaResult(diploma=record)
        case DefenseLookupFailure(category=category, suggestions=suggestions):
            return DiplomaResult(
                error=category.value,
                suggestions=list(suggestions) or None,
            )
        case unreachable:
            assert_never(unreachable)
