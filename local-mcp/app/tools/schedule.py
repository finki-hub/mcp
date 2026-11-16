from app.schemas.schedule import Schedule, ScheduleEntry
from app.schemas.timetable import TimetableDay
from app.tools.directus_lookup import (
    Found,
    find_course,
    find_room,
    find_staff,
    room_label,
)
from app.utils.http_client import get_directus_items
from app.utils.query_matcher import transliterate_and_normalize

# The classes of the latest main timetable, from Directus: each slot with
# the course, room and staff its timetable names were matched to.

_DAYS = dict(enumerate(TimetableDay, start=1))

_SLOT_FIELDS = (
    "subject",
    "kind",
    "day",
    "starts",
    "ends",
    "groups",
    "classroom",
    "teachers",
    "course.id",
    "course.name",
    "room.id",
    "room.name",
    "room.location",
    "staff.staff.id",
    "staff.staff.name",
)


def current_timetable() -> dict | None:
    timetables = get_directus_items(
        "timetables",
        {
            "fields": "id,title",
            "filter[main][_eq]": "true",
            "sort": "-date_from",
            "limit": 1,
        },
    )
    return timetables[0] if timetables else None


def timetable_slots(timetable_id: int) -> list[dict]:
    return get_directus_items(
        "timetable_slots",
        {
            "fields": ",".join(_SLOT_FIELDS),
            "filter[timetable][_eq]": timetable_id,
            "limit": -1,
        },
    )


def _related_id(slot: dict, key: str) -> int | None:
    related = slot.get(key)
    return related.get("id") if isinstance(related, dict) else None


def staff_ids(slot: dict) -> set[int]:
    return {
        link["staff"]["id"]
        for link in slot.get("staff") or []
        if isinstance(link.get("staff"), dict)
    }


def _staff_names(slot: dict) -> list[str] | None:
    linked = [
        link["staff"]["name"]
        for link in slot.get("staff") or []
        if isinstance(link.get("staff"), dict)
    ]
    if linked:
        return sorted(linked)
    written = slot.get("teachers")
    return [name.strip() for name in written.split(",")] if written else None


def to_entry(slot: dict) -> ScheduleEntry:
    course = slot.get("course")
    room = slot.get("room")
    return ScheduleEntry(
        course=course["name"] if isinstance(course, dict) else slot["subject"],
        kind=slot.get("kind") or None,
        day=_DAYS[slot["day"]],
        starts=slot.get("starts"),
        ends=slot.get("ends"),
        room=room_label(room) if isinstance(room, dict) else slot.get("classroom"),
        staff=_staff_names(slot),
        groups=slot.get("groups"),
    )


def sorted_entries(slots: list[dict]) -> list[ScheduleEntry]:
    ordered = sorted(
        slots,
        key=lambda slot: (slot["day"], slot.get("starts") or "", slot["subject"]),
    )
    return [to_entry(slot) for slot in ordered if slot.get("day") in _DAYS]


def _in_group(slot: dict, group: str) -> bool:
    query = transliterate_and_normalize(group)
    return any(
        transliterate_and_normalize(name).startswith(query)
        for name in (slot.get("groups") or "").split(",")
    )


def _failed(found: Found) -> Schedule:
    return Schedule(error=found.error, suggestions=found.suggestions)


def schedule(
    *,
    staff: str | None = None,
    course: str | None = None,
    room: str | None = None,
    group: str | None = None,
    day: TimetableDay | None = None,
) -> Schedule:
    staff, course, room, group = (
        value.strip() if value and value.strip() else None
        for value in (staff, course, room, group)
    )
    if not any((staff, course, room, group)):
        return Schedule(error="Внесете вработен, предмет, просторија или група.")

    matched: dict[str, str] = {}
    wanted: dict[str, int] = {}
    for key, query, find in (
        ("staff", staff, find_staff),
        ("course", course, find_course),
        ("room", room, find_room),
    ):
        if query is None:
            continue
        found = find(query)
        if found.record is None:
            return _failed(found)
        wanted[key] = found.record["id"]
        matched[key] = (
            room_label(found.record) if key == "room" else found.record["name"]
        )

    timetable = current_timetable()
    if timetable is None:
        return Schedule(error="Нема главен распоред.")

    slots = [
        slot
        for slot in timetable_slots(timetable["id"])
        if ("staff" not in wanted or wanted["staff"] in staff_ids(slot))
        and ("course" not in wanted or _related_id(slot, "course") == wanted["course"])
        and ("room" not in wanted or _related_id(slot, "room") == wanted["room"])
        and (group is None or _in_group(slot, group))
        and (day is None or _DAYS.get(slot.get("day") or 0) == day)
    ]
    return Schedule(
        timetable=timetable["title"],
        matched=matched or None,
        entries=sorted_entries(slots),
    )
