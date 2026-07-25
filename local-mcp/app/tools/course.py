import re
from typing import NamedTuple

from app.schemas.course import (
    Accreditation,
    AccreditationMatch,
    AccreditationYear,
    Course,
    CourseData,
    CourseMatch,
    CourseParticipants,
    CourseStaff,
    CourseStatus,
    CourseTag,
    Staff,
    StudyProgram,
)
from app.utils.http_client import get_courses
from app.utils.query_matcher import match_query_to_group, resolve_query

_INACTIVE_MARKER = "(неактивиран предмет)"
_NOT_OFFERED = "нема"
_PARTICIPANTS_YEAR_RE = re.compile(r"^\d{4}/\d{4}$")
_ACCREDITATION_FIELD_RE = re.compile(r"^(\d{4})-(.+)$")


def _to_int(value: object, default: int = 0) -> int:
    try:
        return int(str(value))
    except ValueError, TypeError:
        return default


def _split_people(value: str | None) -> list[str]:
    if not value or value.strip() == _INACTIVE_MARKER:
        return []
    return [line.strip() for line in value.split("\n") if line.strip()]


def _split_tags(value: str | None) -> list[str]:
    tags = (tag.strip() for tag in (value or "").split(","))
    return [CourseTag.from_upstream(tag) or tag for tag in tags if tag]


def _build_course(record: dict) -> CourseData:
    professors_raw = record.get("professors") or ""

    participants: dict[str, int] = {}
    accreditations: dict[str, Accreditation] = {}
    offered: dict[str, dict[str, str]] = {}

    for key, value in record.items():
        if _PARTICIPANTS_YEAR_RE.match(key):
            participants[key] = _to_int(value)
            continue

        field_match = _ACCREDITATION_FIELD_RE.match(key)
        if not field_match:
            continue

        version, field = field_match.group(1), field_match.group(2)
        accreditation = accreditations.setdefault(
            version,
            Accreditation(available=False),
        )

        if field == "channel":
            continue
        if field.startswith("state-"):
            program = StudyProgram.from_upstream(field.removeprefix("state-"))
            if program and value and value != _NOT_OFFERED:
                offered.setdefault(version, {})[program] = value
        elif field == "available":
            accreditation.available = str(value).upper() == "TRUE"
        elif field == "credits":
            accreditation.credits = _to_int(value)
        elif field == "level":
            accreditation.level = _to_int(value)
        elif field == "semester":
            accreditation.semester = _to_int(value)
        elif field == "prerequisite":
            accreditation.prerequisite = value or None
        elif field == "name":
            accreditation.name = value
        elif field == "code":
            accreditation.code = value

    for version, programs in offered.items():
        accreditations[version].offered_in = programs

    return CourseData(
        name=record.get("name", ""),
        tags=_split_tags(record.get("tags")),
        channel=str(record.get("channel") or "").upper() == "TRUE",
        staff=Staff(
            professors=_split_people(record.get("professors")),
            assistants=_split_people(record.get("assistants")),
            inactive=professors_raw.strip() == _INACTIVE_MARKER,
        ),
        participants=participants,
        accreditations=accreditations,
    )


_MIN_QUERY_LENGTH = 3


def _not_found(course_name: str) -> str:
    return f"Предметот „{course_name}“ не е пронајден"


class _Lookup(NamedTuple):
    data: CourseData | None
    match_info: dict | None
    error: str | None
    suggestions: list[str] | None


def _lookup_course(course_name: str) -> _Lookup:
    query = course_name.strip()
    if not query:
        return _Lookup(None, None, "Внесете име на предметот.", None)
    if len(query) < _MIN_QUERY_LENGTH:
        return _Lookup(
            None,
            None,
            f"Барањето е прекратко; внесете барем {_MIN_QUERY_LENGTH} знаци.",
            None,
        )

    courses = get_courses()
    course_names = [record.get("name", "") for record in courses]
    resolution = resolve_query(course_name, course_names)

    if resolution["status"] == "matched":
        record = next(
            (r for r in courses if r.get("name") == resolution["match"]),
            None,
        )
        if record is not None:
            match_info = {
                "original_query": course_name,
                "matched_course": resolution["match"],
                "similarity_score": resolution["score"],
                "match_type": resolution["match_type"],
            }
            return _Lookup(_build_course(record), match_info, None, None)

    if resolution["status"] == "ambiguous":
        return _Lookup(
            None,
            None,
            f"Повеќе предмети одговараат на „{course_name}“",
            resolution["candidates"],
        )

    return _Lookup(
        None,
        None,
        _not_found(course_name),
        resolution["candidates"] or None,
    )


def get_course_data(course_name: str) -> Course:
    found = _lookup_course(course_name)
    if found.data is None:
        return Course(
            name=course_name,
            error=found.error,
            suggestions=found.suggestions,
        )
    return Course(
        name=found.data.name,
        tags=found.data.tags,
        channel=found.data.channel,
        accreditations=found.data.accreditations,
        match_info=found.match_info,
    )


def get_course_staff(course_name: str) -> CourseStaff:
    found = _lookup_course(course_name)
    if found.data is None:
        return CourseStaff(
            name=course_name,
            error=found.error,
            suggestions=found.suggestions,
        )
    return CourseStaff(
        name=found.data.name,
        staff=found.data.staff,
        match_info=found.match_info,
    )


def get_course_participants(course_name: str) -> CourseParticipants:
    found = _lookup_course(course_name)
    if found.data is None:
        return CourseParticipants(
            name=course_name,
            error=found.error,
            suggestions=found.suggestions,
        )
    return CourseParticipants(
        name=found.data.name,
        participants=found.data.participants,
        match_info=found.match_info,
    )


def _base_status(value: str) -> str:
    return value.split(" (", maxsplit=1)[0].strip()


def _evaluate_accreditation(
    accreditation: Accreditation,
    program: StudyProgram | None,
    status: CourseStatus | None,
    semester: int | None,
) -> tuple[AccreditationMatch, bool]:
    offered = accreditation.offered_in or {}
    offered_match: dict[str, str] | None = None
    semester_value: int | None = None
    matched = True

    if program is not None:
        offered_match = {program: offered[program]} if program in offered else {}
        if program not in offered or (
            status is not None and _base_status(offered[program]) != status
        ):
            matched = False
    elif status is not None:
        offered_match = {p: v for p, v in offered.items() if _base_status(v) == status}
        if not offered_match:
            matched = False

    if semester is not None:
        semester_value = accreditation.semester
        if accreditation.semester != semester:
            matched = False

    return AccreditationMatch(
        offered_in=offered_match,
        semester=semester_value,
    ), matched


def _resolve_staff_groups(names: list[str], pool: list[str]) -> list[list[str]] | None:
    groups: list[list[str]] = []
    for name in names:
        group = match_query_to_group(name, pool)
        if group is None:
            return None
        groups.append(group)
    return groups


def list_courses(
    *,
    program: StudyProgram | None = None,
    status: CourseStatus | None = None,
    semester: int | None = None,
    accreditation: AccreditationYear | None = None,
    tags: list[CourseTag] | None = None,
    professors: list[str] | None = None,
    assistants: list[str] | None = None,
) -> list[CourseMatch]:
    courses = [_build_course(record) for record in get_courses()]

    professor_groups: list[list[str]] | None = None
    professor_candidates: set[str] = set()
    if professors:
        pool = sorted({n for c in courses for n in c.staff.professors})
        professor_groups = _resolve_staff_groups(professors, pool)
        if professor_groups is None:
            return []
        professor_candidates = {m for group in professor_groups for m in group}

    assistant_groups: list[list[str]] | None = None
    assistant_candidates: set[str] = set()
    if assistants:
        pool = sorted({n for c in courses for n in c.staff.assistants})
        assistant_groups = _resolve_staff_groups(assistants, pool)
        if assistant_groups is None:
            return []
        assistant_candidates = {m for group in assistant_groups for m in group}

    report_accreditations = (
        program is not None or status is not None or semester is not None
    )
    scopes_accreditations = report_accreditations or accreditation is not None

    matches: list[CourseMatch] = []
    for course in courses:
        course_tags = course.tags or []
        if tags is not None and not all(t in course_tags for t in tags):
            continue

        course_professors = course.staff.professors
        if professor_groups is not None and not all(
            any(m in course_professors for m in group) for group in professor_groups
        ):
            continue

        course_assistants = course.staff.assistants
        if assistant_groups is not None and not all(
            any(m in course_assistants for m in group) for group in assistant_groups
        ):
            continue

        accreditations: dict[str, AccreditationMatch] | None = None
        if scopes_accreditations:
            matched_entries: dict[str, AccreditationMatch] = {}
            any_match = False
            for year, acc in (course.accreditations or {}).items():
                if not acc.available:
                    continue
                if accreditation is not None and year != accreditation:
                    continue
                entry, matched = _evaluate_accreditation(acc, program, status, semester)
                if not matched:
                    continue
                any_match = True
                if report_accreditations:
                    matched_entries[year] = entry
            if not any_match:
                continue
            accreditations = matched_entries or None

        matches.append(
            CourseMatch(
                name=course.name,
                tags=course.tags if tags is not None else None,
                professors=[p for p in course_professors if p in professor_candidates]
                or None,
                assistants=[a for a in course_assistants if a in assistant_candidates]
                or None,
                accreditations=accreditations,
            ),
        )

    return matches
