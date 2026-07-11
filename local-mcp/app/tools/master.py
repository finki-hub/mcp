from dataclasses import dataclass
from enum import StrEnum
from typing import assert_never

from app.schemas.defense import DefenseMatch, MasterDefense, MasterResult
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
from app.utils.http_client import get_masters


class MasterListErrorCategory(StrEnum):
    MISSING_FILTER = "Внесете барем еден филтер за магистерски трудови."
    INDEX_EXCLUSIVE = "Индексот на студент не може да се комбинира со други филтри."


@dataclass(frozen=True, slots=True)
class InvalidMasterListFilterError(ValueError):
    category: MasterListErrorCategory

    def __str__(self) -> str:
        return self.category.value


def _effective_masters() -> list[MasterDefense]:
    return collapse_defense_records(
        get_masters(),
        lambda record: record.date_of_presentation,
    )


def list_masters(
    student: str | None = None,
    mentor: str | None = None,
    title: str | None = None,
) -> list[DefenseMatch]:
    student_filter = parse_optional_student_filter(student)
    mentor_filter = strip_list_filter(mentor)
    title_filter = strip_list_filter(title)
    if student_filter is None and mentor_filter is None and title_filter is None:
        raise InvalidMasterListFilterError(MasterListErrorCategory.MISSING_FILTER)

    match student_filter:
        case StudentIndexFilter() if (
            mentor_filter is not None or title_filter is not None
        ):
            raise InvalidMasterListFilterError(MasterListErrorCategory.INDEX_EXCLUSIVE)
        case StudentIndexFilter() | StudentNameFilter() | None:
            pass
        case unreachable:
            assert_never(unreachable)

    matches = filter_defense_records(
        _effective_masters(),
        student=student_filter,
        mentor=mentor_filter,
        title=title_filter,
    )
    return to_defense_matches(matches)


def get_master(student: str) -> MasterResult:
    outcome = resolve_defense_lookup(
        _effective_masters(),
        parse_student_filter(student),
    )
    match outcome:
        case DefenseLookupSuccess(record=record):
            return MasterResult(master=record)
        case DefenseLookupFailure(category=category, suggestions=suggestions):
            return MasterResult(
                error=category.value,
                suggestions=list(suggestions) or None,
            )
        case unreachable:
            assert_never(unreachable)
