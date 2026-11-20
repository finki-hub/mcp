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

# Directus numbers the days 1 (Monday) to 5 (Friday).
_DAYS = {
    1: TimetableDay.MONDAY,
    2: TimetableDay.TUESDAY,
    3: TimetableDay.WEDNESDAY,
    4: TimetableDay.THURSDAY,
    5: TimetableDay.FRIDAY,
}

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
    "courses.course.id",
    "courses.course.name",
    "room.id",
    "room.name",
    "room.location",
    "staff.staff.id",
    "staff.staff.name",
    "staff.teacher",
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
    # The linked staff by their names, then every teacher the timetable
    # names that no link stands for (such as "Демонстратор 4").
    links = [
        link for link in slot.get("staff") or [] if isinstance(link.get("staff"), dict)
    ]
    linked_teachers = {link.get("teacher") for link in links}
    unlinked = [
        name
        for name in (part.strip() for part in (slot.get("teachers") or "").split(","))
        if name and name not in linked_teachers
    ]
    names = sorted({link["staff"]["name"] for link in links}) + unlinked
    return names or None


def _courses(slot: dict) -> dict[int, str]:
    # Every course the slot is held for: both parts of a joint class
    # ("A / B"), else its one course.
    linked = {
        link["course"]["id"]: link["course"]["name"]
        for link in slot.get("courses") or []
        if isinstance(link.get("course"), dict)
    }
    course = slot.get("course")
    if isinstance(course, dict):
        linked.setdefault(course["id"], course["name"])
    return linked


def course_ids(slot: dict) -> set[int]:
    return set(_courses(slot))


def to_entry(slot: dict) -> ScheduleEntry:
    names = sorted(_courses(slot).values())
    room = slot.get("room")
    return ScheduleEntry(
        course=" / ".join(names) if names else slot.get("subject") or "",
        kind=slot.get("kind") or None,
        day=_DAYS[slot["day"]],
        starts=slot.get("starts"),
        ends=slot.get("ends"),
        room=room_label(room) if isinstance(room, dict) else slot.get("classroom"),
        staff=_staff_names(slot),
        groups=slot.get("groups"),
    )


def sorted_entries(slots: list[dict]) -> list[ScheduleEntry]:
    # A slot without a weekday cannot be placed, so it is left out.
    placed = [slot for slot in slots if slot.get("day") in _DAYS]
    ordered = sorted(
        placed,
        key=lambda slot: (
            slot["day"],
            slot.get("starts") or "",
            slot.get("subject") or "",
        ),
    )
    return [to_entry(slot) for slot in ordered]


def _in_group(slot: dict, group: str) -> bool:
    query = transliterate_and_normalize(group)
    return any(
        transliterate_and_normalize(name).startswith(query)
        for name in (slot.get("groups") or "").split(",")
    )


def _failed(found: Found) -> Schedule:
    return Schedule(error=found.error, suggestions=found.suggestions)


def _slot_wanted(
    slot: dict,
    wanted: dict[str, int],
    group: str | None,
    day: TimetableDay | None,
) -> bool:
    """Whether a slot has every matched staff member, course and room."""
    checks = (
        "staff" not in wanted or wanted["staff"] in staff_ids(slot),
        "course" not in wanted or wanted["course"] in course_ids(slot),
        "room" not in wanted or _related_id(slot, "room") == wanted["room"],
    )
    return (
        all(checks)
        and (group is None or _in_group(slot, group))
        and (day is None or _DAYS.get(slot.get("day") or 0) == day)
    )


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
        if _slot_wanted(slot, wanted, group, day)
    ]
    return Schedule(
        timetable=timetable["title"],
        matched=matched or None,
        entries=sorted_entries(slots),
    )
