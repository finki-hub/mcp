import re

from app.schemas.timetable import (
    TimetableDay,
    TimetableEntity,
    TimetableEntry,
    TimetableEntryGroup,
    TimetableLessonType,
    TimetableSummary,
)
from app.utils.http_client import get_timetable_detail, get_timetables

_LESSON_SUFFIX_RE = re.compile(r"\s*\(([^()]*)\)\s*$")
_LESSON_TOKENS = {"п", "ав", "лаб"}
_LESSON_TYPE_TOKENS = {
    TimetableLessonType.LECTURE: "п",
    TimetableLessonType.AUDITORY_EXERCISES: "ав",
    TimetableLessonType.LABORATORY_EXERCISES: "лаб",
}
_UPSTREAM_DAYS = {
    "Monday": TimetableDay.MONDAY,
    "Tuesday": TimetableDay.TUESDAY,
    "Wednesday": TimetableDay.WEDNESDAY,
    "Thursday": TimetableDay.THURSDAY,
    "Friday": TimetableDay.FRIDAY,
}


def _clean(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _to_int(value: object, default: int = 0) -> int:
    try:
        return int(str(value))
    except TypeError, ValueError:
        return default


def _latest_active_timetable_id() -> str:
    active = [record for record in get_timetables() if not record.get("hidden")]
    if not active:
        raise RuntimeError("No active timetable is available")

    latest = max(active, key=lambda record: str(record.get("dateFrom") or ""))
    timetable_id = _clean(latest.get("id"))
    if timetable_id is None:
        raise RuntimeError("Active timetable is missing an ID")
    return timetable_id


def _resolve_timetable_id(id: str | None) -> str:
    timetable_id = _clean(id)
    if timetable_id is not None:
        return timetable_id
    return _latest_active_timetable_id()


def _get_timetable(id: str | None) -> dict:
    return get_timetable_detail(_resolve_timetable_id(id))


def _lesson_tokens_and_course_name(name: str) -> tuple[list[str], str]:
    course_name = name.strip()
    match = _LESSON_SUFFIX_RE.search(course_name)
    if not match:
        return [], course_name

    tokens = [
        token.strip().casefold() for token in match.group(1).split("+") if token.strip()
    ]
    if tokens and all(token in _LESSON_TOKENS for token in tokens):
        return tokens, course_name[: match.start()].strip()

    return [], course_name


def _course_name(name: object) -> str:
    _tokens, course_name = _lesson_tokens_and_course_name(_clean(name) or "")
    return course_name


def _entry_lesson_types(name: object) -> list[TimetableLessonType] | None:
    tokens, _course_name = _lesson_tokens_and_course_name(_clean(name) or "")
    lesson_types = [
        lesson_type
        for lesson_type, token in _LESSON_TYPE_TOKENS.items()
        if token in tokens
    ]
    return lesson_types or None


def _matches_lesson_type(name: object, lesson_type: TimetableLessonType | None) -> bool:
    if lesson_type is None:
        return True

    tokens, _course_name = _lesson_tokens_and_course_name(_clean(name) or "")
    return _LESSON_TYPE_TOKENS[lesson_type] in tokens


def _time_to_minutes(value: str) -> int:
    hours, minutes = value.split(":", maxsplit=1)
    return int(hours) * 60 + int(minutes)


def _build_summary(record: dict) -> TimetableSummary:
    return TimetableSummary(
        id=_clean(record.get("id")) or "",
        title=_clean(record.get("title")) or "",
        date_from=_clean(record.get("dateFrom")) or "",
        year=_to_int(record.get("year")),
    )


def _build_entity(record: dict, *, strip_lesson_type: bool = False) -> TimetableEntity:
    name = _clean(record.get("name")) or ""
    if strip_lesson_type:
        name = _course_name(name)

    return TimetableEntity(
        id=_clean(record.get("id")) or "",
        name=name,
    )


def _entities(
    detail: dict,
    key: str,
    *,
    strip_lesson_type: bool = False,
) -> list[TimetableEntity]:
    return [
        _build_entity(record, strip_lesson_type=strip_lesson_type)
        for record in detail.get(key, [])
    ]


def _is_entire_class(group: dict) -> bool:
    value = group.get("entireClass")
    if isinstance(value, bool):
        return value
    return str(value).casefold() == "true"


def _subgroups_for_class(card: dict, class_id: str) -> list[str] | None:
    subgroups: list[str] = []
    for group in card.get("groups", []) or []:
        if _clean(group.get("classId")) != class_id or _is_entire_class(group):
            continue
        name = _clean(group.get("name"))
        if name and name not in subgroups:
            subgroups.append(name)

    return subgroups or None


def _entry_groups(card: dict) -> list[TimetableEntryGroup]:
    groups: list[TimetableEntryGroup] = []
    for group in card.get("classes", []) or []:
        class_id = _clean(group.get("id")) or ""
        groups.append(
            TimetableEntryGroup(
                name=_clean(group.get("name")) or "",
                subgroups=_subgroups_for_class(card, class_id),
            ),
        )
    return groups


def _entry_room(card: dict) -> str | None:
    rooms = [
        name
        for room in (card.get("classrooms", []) or [])
        if (name := _clean(room.get("name")))
    ]
    if not rooms:
        return None
    return ", ".join(rooms)


def _build_entry(card: dict) -> TimetableEntry:
    subject = card.get("subject") or {}
    subject_name = _clean(subject.get("name")) or ""
    day_name = _clean(card.get("dayName")) or ""
    return TimetableEntry(
        course=_course_name(subject_name),
        professors=[
            name
            for teacher in (card.get("teachers", []) or [])
            if (name := _clean(teacher.get("name")))
        ],
        groups=_entry_groups(card),
        room=_entry_room(card),
        day=_UPSTREAM_DAYS[day_name],
        start_time=_clean(card.get("startTime")) or "",
        end_time=_clean(card.get("endTime")) or "",
        duration_periods=_to_int(card.get("durationPeriods")),
        lesson_types=_entry_lesson_types(subject_name),
    )


def _contains_entity_id(card: dict, key: str, entity_id: str | None) -> bool:
    if entity_id is None:
        return True

    return any(
        _clean(entity.get("id")) == entity_id for entity in card.get(key, []) or []
    )


def list_timetables() -> list[TimetableSummary]:
    return [_build_summary(record) for record in get_timetables()]


def list_timetable_groups(id: str | None = None) -> list[TimetableEntity]:
    return _entities(_get_timetable(id), "classes")


def list_timetable_professors(id: str | None = None) -> list[TimetableEntity]:
    return _entities(_get_timetable(id), "teachers")


def list_timetable_rooms(id: str | None = None) -> list[TimetableEntity]:
    return _entities(_get_timetable(id), "classrooms")


def list_timetable_courses(id: str | None = None) -> list[TimetableEntity]:
    return _entities(_get_timetable(id), "subjects", strip_lesson_type=True)


def list_timetable_entries(
    id: str | None = None,
    group_id: str | None = None,
    professor_id: str | None = None,
    room_id: str | None = None,
    course_id: str | None = None,
    day: TimetableDay | None = None,
    lesson_type: TimetableLessonType | None = None,
    start_after: str | None = None,
    end_before: str | None = None,
) -> list[TimetableEntry]:
    group_id = _clean(group_id)
    professor_id = _clean(professor_id)
    room_id = _clean(room_id)
    course_id = _clean(course_id)
    if not any([group_id, professor_id, room_id, course_id]):
        return []

    start_after_minutes = _time_to_minutes(start_after) if start_after else None
    end_before_minutes = _time_to_minutes(end_before) if end_before else None

    entries: list[TimetableEntry] = []
    for card in _get_timetable(id).get("cards", []):
        subject = card.get("subject") or {}
        if course_id is not None and _clean(subject.get("id")) != course_id:
            continue
        if not _contains_entity_id(card, "classes", group_id):
            continue
        if not _contains_entity_id(card, "teachers", professor_id):
            continue
        if not _contains_entity_id(card, "classrooms", room_id):
            continue
        if day is not None and _UPSTREAM_DAYS.get(str(card.get("dayName"))) != day:
            continue
        if not _matches_lesson_type(subject.get("name"), lesson_type):
            continue
        if start_after_minutes is not None:
            start_time = _clean(card.get("startTime"))
            if start_time is None or _time_to_minutes(start_time) < start_after_minutes:
                continue
        if end_before_minutes is not None:
            end_time = _clean(card.get("endTime"))
            if end_time is None or _time_to_minutes(end_time) > end_before_minutes:
                continue

        entries.append(_build_entry(card))

    return entries
