from typing import NamedTuple

from app.schemas.staff import (
    StaffMatch,
    StaffMember,
    StaffPosition,
    StaffTitle,
)
from app.utils.http_client import get_staff
from app.utils.query_matcher import resolve_query

_MIN_QUERY_LENGTH = 3


def _is_active(record: dict) -> bool:
    return str(record.get("active", "")).strip() == "1"


def list_staff(
    active: bool | None = None,
    title: StaffTitle | None = None,
    position: StaffPosition | None = None,
) -> list[StaffMatch]:
    matches: list[StaffMatch] = []
    for record in get_staff():
        if active is not None and _is_active(record) != active:
            continue
        if title is not None and record.get("title") != title:
            continue
        if position is not None and record.get("position") != position:
            continue

        matches.append(
            StaffMatch(
                name=record.get("name", ""),
                title=record.get("title") or None,
                position=record.get("position") or None,
                active=_is_active(record),
            ),
        )

    return matches


def _not_found(name: str) -> str:
    return f"Вработениот „{name}“ не е пронајден"


class _Lookup(NamedTuple):
    record: dict | None
    match_info: dict | None
    error: str | None
    suggestions: list[str] | None


def _lookup_staff(name: str) -> _Lookup:
    query = name.strip()
    if not query:
        return _Lookup(None, None, "Внесете име на вработениот.", None)
    if len(query) < _MIN_QUERY_LENGTH:
        return _Lookup(
            None,
            None,
            f"Барањето е прекратко; внесете барем {_MIN_QUERY_LENGTH} знаци.",
            None,
        )

    staff = get_staff()
    names = [record.get("name", "") for record in staff]
    resolution = resolve_query(name, names)

    if resolution["status"] == "matched":
        record = next(
            (r for r in staff if r.get("name") == resolution["match"]),
            None,
        )
        if record is not None:
            match_info = {
                "original_query": name,
                "matched_staff": resolution["match"],
                "similarity_score": resolution["score"],
                "match_type": resolution["match_type"],
            }
            return _Lookup(record, match_info, None, None)

    if resolution["status"] == "ambiguous":
        return _Lookup(
            None,
            None,
            f"Повеќе вработени одговараат на „{name}“",
            resolution["candidates"],
        )

    return _Lookup(
        None,
        None,
        _not_found(name),
        resolution["candidates"] or None,
    )


def get_staff_member(name: str) -> StaffMember:
    found = _lookup_staff(name)
    if found.record is None:
        return StaffMember(
            name=name,
            error=found.error,
            suggestions=found.suggestions,
        )
    record = found.record
    return StaffMember(
        name=record.get("name", ""),
        title=record.get("title") or None,
        position=record.get("position") or None,
        active=_is_active(record),
        email=record.get("email") or None,
        cabinet=record.get("cabinet") or None,
        consultations=record.get("consultations") or None,
        courses=record.get("courses") or None,
        profile=record.get("profile") or None,
        match_info=found.match_info,
    )
