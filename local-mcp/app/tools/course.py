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
from app.utils.abbreviation_matcher import (
    build_abbreviation_index,
    resolve_abbreviation,
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


def _set_accreditation_field(
    accreditation: Accreditation,
    field: str,
    value: object,
) -> None:
    if field == "available":
        accreditation.available = str(value).upper() == "TRUE"
    elif field in {"credits", "level", "semester"}:
        setattr(accreditation, field, _to_int(value))
    elif field == "prerequisite":
        setattr(accreditation, field, value or None)
    elif field in {"name", "code"}:
        setattr(accreditation, field, value)


def _build_accreditations(record: dict) -> dict[str, Accreditation]:
    accreditations: dict[str, Accreditation] = {}
    offered: dict[str, dict[str, str]] = {}
    for key, value in record.items():
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
        else:
            _set_accreditation_field(accreditation, field, value)

    for version, programs in offered.items():
        accreditations[version].offered_in = programs
    return accreditations


def _build_course(record: dict) -> CourseData:
    professors_raw = record.get("professors") or ""
    participants = {
        key: _to_int(value)
        for key, value in record.items()
        if _PARTICIPANTS_YEAR_RE.match(key)
    }

    return CourseData(
        name=record.get("name", ""),
        abbreviation=record.get("abbreviation") or None,
        tags=_split_tags(record.get("tags")),
        channel=str(record.get("channel") or "").upper() == "TRUE",
        staff=Staff(
            professors=_split_people(record.get("professors")),
            assistants=_split_people(record.get("assistants")),
            inactive=professors_raw.strip() == _INACTIVE_MARKER,
        ),
        participants=participants,
        accreditations=_build_accreditations(record),
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

    courses = get_courses()
    abbreviation_matches = resolve_abbreviation(
        query,
        build_abbreviation_index(courses),
    )
    if len(abbreviation_matches) > 1:
        return _Lookup(
            None,
            None,
            f"Повеќе предмети одговараат на „{course_name}“",
            abbreviation_matches,
        )
    if abbreviation_matches:
        matched = next(r for r in courses if r.get("name") == abbreviation_matches[0])
        match_info = {
            "original_query": course_name,
            "matched_course": abbreviation_matches[0],
            "similarity_score": 100,
            "match_type": "abbreviation",
        }
        return _Lookup(_build_course(matched), match_info, None, None)

    if len(query) < _MIN_QUERY_LENGTH:
        return _Lookup(
            None,
            None,
            f"Барањето е прекратко; внесете барем {_MIN_QUERY_LENGTH} знаци.",
            None,
        )

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
        abbreviation=found.data.abbreviation,
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
        abbreviation=found.data.abbreviation,
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
        abbreviation=found.data.abbreviation,
        participants=found.data.participants,
        match_info=found.match_info,
    )


def _base_status(value: str) -> str:
    return value.split(" (", maxsplit=1)[0].strip()


# The same program was renamed between accreditations, so a filter on either code
# must match the course's entry under the other.
_SAME_PROGRAM: dict[str, str] = {
    StudyProgram.KE: StudyProgram.IE,
    StudyProgram.IE: StudyProgram.KE,
}


def _evaluate_offering(
    offered: dict[str, str],
    program: StudyProgram | None,
    status: CourseStatus | None,
) -> tuple[dict[str, str] | None, bool]:
    offered_match: dict[str, str] | None = None
    matched = True

    if program is not None:
        key = program if program in offered else _SAME_PROGRAM.get(program, program)
        offered_match = {key: offered[key]} if key in offered else {}
        if key not in offered or (
            status is not None and _base_status(offered[key]) != status
        ):
            matched = False
    elif status is not None:
        offered_match = {p: v for p, v in offered.items() if _base_status(v) == status}
        if not offered_match:
            matched = False

    return offered_match, matched


def _evaluate_accreditation(
    accreditation: Accreditation,
    program: StudyProgram | None,
    status: CourseStatus | None,
    semester: int | None,
) -> tuple[AccreditationMatch, bool]:
    offered_match, matched = _evaluate_offering(
        accreditation.offered_in or {},
        program,
        status,
    )
    semester_value = accreditation.semester if semester is not None else None
    if semester is not None and accreditation.semester != semester:
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


class _StaffFilter(NamedTuple):
    groups: list[list[str]] | None
    candidates: set[str]


def _staff_filter(
    names: list[str] | None,
    courses: list[CourseData],
    role: str,
) -> _StaffFilter:
    if not names:
        return _StaffFilter(None, set())
    pool = sorted({n for c in courses for n in getattr(c.staff, role)})
    groups = _resolve_staff_groups(names, pool)
    return _StaffFilter(groups, {m for group in (groups or []) for m in group})


def _matches_staff(people: list[str], staff_filter: _StaffFilter) -> bool:
    return staff_filter.groups is None or all(
        any(person in people for person in group) for group in staff_filter.groups
    )


def _matching_accreditations(
    course: CourseData,
    program: StudyProgram | None,
    status: CourseStatus | None,
    semester: int | None,
    accreditation: AccreditationYear | None,
) -> dict[str, AccreditationMatch]:
    entries: dict[str, AccreditationMatch] = {}
    for year, acc in (course.accreditations or {}).items():
        if not acc.available:
            continue
        if accreditation is not None and year != accreditation:
            continue
        entry, matched = _evaluate_accreditation(acc, program, status, semester)
        if matched:
            entries[year] = entry
    return entries


def _matches_course_filters(
    course: CourseData,
    tags: list[CourseTag] | None,
    professors: _StaffFilter,
    assistants: _StaffFilter,
) -> bool:
    if tags is not None and not all(tag in (course.tags or []) for tag in tags):
        return False
    return _matches_staff(course.staff.professors, professors) and _matches_staff(
        course.staff.assistants,
        assistants,
    )


def _course_match(
    course: CourseData,
    tags: list[CourseTag] | None,
    professors: _StaffFilter,
    assistants: _StaffFilter,
    accreditations: dict[str, AccreditationMatch] | None,
) -> CourseMatch:
    return CourseMatch(
        name=course.name,
        abbreviation=course.abbreviation,
        tags=course.tags if tags is not None else None,
        professors=[p for p in course.staff.professors if p in professors.candidates]
        or None,
        assistants=[a for a in course.staff.assistants if a in assistants.candidates]
        or None,
        accreditations=accreditations,
    )


def _reported_accreditations(
    entries: dict[str, AccreditationMatch],
    report: bool,
) -> dict[str, AccreditationMatch] | None:
    return entries if report else None


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

    professor_filter = _staff_filter(professors, courses, "professors")
    if professors and professor_filter.groups is None:
        return []
    assistant_filter = _staff_filter(assistants, courses, "assistants")
    if assistants and assistant_filter.groups is None:
        return []

    report_accreditations = (
        program is not None or status is not None or semester is not None
    )
    scopes_accreditations = report_accreditations or accreditation is not None

    matches: list[CourseMatch] = []
    for course in courses:
        if not _matches_course_filters(
            course, tags, professor_filter, assistant_filter
        ):
            continue

        accreditations: dict[str, AccreditationMatch] | None = None
        if scopes_accreditations:
            matched_entries = _matching_accreditations(
                course,
                program,
                status,
                semester,
                accreditation,
            )
            if not matched_entries:
                continue
            accreditations = _reported_accreditations(
                matched_entries, report_accreditations
            )

        matches.append(
            _course_match(
                course, tags, professor_filter, assistant_filter, accreditations
            ),
        )

    return matches
