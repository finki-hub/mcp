from app.schemas.staff import (
    StaffMatch,
    StaffPosition,
    StaffTitle,
)
from app.utils.http_client import get_staff


def _is_active(record: dict) -> bool:
    return record.get("active") is True


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
