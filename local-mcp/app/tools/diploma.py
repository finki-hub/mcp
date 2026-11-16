from typing import assert_never

from app.schemas.defense import Diploma, DiplomaResult
from app.tools.defense import (
    DefenseLookupFailure,
    DefenseLookupSuccess,
    collapse_defense_records,
    parse_student_filter,
    resolve_defense_lookup,
)
from app.utils.http_client import get_diplomas


def _effective_diplomas() -> list[Diploma]:
    return collapse_defense_records(
        get_diplomas(),
        lambda diploma: diploma.date_of_submission,
    )


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
