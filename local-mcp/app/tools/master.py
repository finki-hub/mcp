from typing import assert_never

from app.schemas.defense import MasterDefense, MasterResult
from app.tools.defense import (
    DefenseLookupFailure,
    DefenseLookupSuccess,
    collapse_defense_records,
    parse_student_filter,
    resolve_defense_lookup,
)
from app.utils.http_client import get_masters


def _effective_masters() -> list[MasterDefense]:
    return collapse_defense_records(
        get_masters(),
        lambda record: record.date_of_presentation,
    )


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
