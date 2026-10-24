import re
from typing import NamedTuple

from app.schemas.course import (
    Accreditation,
    AccreditationMatch,
    AccreditationYear,
    Course,
    CourseData,
    CourseList,
    CourseMatch,
    CourseParticipants,
    CourseStaff,
    CourseStatus,
    CourseTag,
    SemesterType,
    Staff,
    StudyProgram,
)
from app.utils.abbreviation_matcher import (
    build_abbreviation_index,
    resolve_abbreviation,
)
from app.utils.http_client import get_courses
from app.utils.pagination import paginate
from app.utils.query_matcher import (
    match_query_to_group,
    resolve_query,
    transliterate_and_normalize,
)

DEFAULT_COURSE_LIMIT = 50

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


class _AccreditationFilter(NamedTuple):
    program: StudyProgram | None
    status: CourseStatus | None
    semester: int | None
    semester_type: SemesterType | None
    accreditation: AccreditationYear | None

    @property
    def reports(self) -> bool:
        return (
            self.program is not None
            or self.status is not None
            or self.semester is not None
            or self.semester_type is not None
        )

    @property
    def scopes(self) -> bool:
        return self.reports or self.accreditation is not None


def _programs_summary(offered: dict[str, str]) -> str | None:
    # The status is implied by the filter; keep only qualifiers such as "(4 г.)".
    summary = ", ".join(
        program + value.removeprefix(_base_status(value))
        for program, value in offered.items()
    )
    return summary or None


def _matches_semester(
    accreditation: Accreditation,
    semester: int | None,
    semester_type: SemesterType | None,
) -> bool:
    if semester is not None and accreditation.semester != semester:
        return False
    if semester_type is None:
        return True
    return accreditation.semester is not None and (accreditation.semester % 2 == 1) == (
        semester_type == SemesterType.WINTER
    )


def _evaluate_accreditation(
    accreditation: Accreditation,
    filters: _AccreditationFilter,
) -> tuple[AccreditationMatch, bool]:
    offered_match, matched = _evaluate_offering(
        accreditation.offered_in or {},
        filters.program,
        filters.status,
    )
    programs = None
    if filters.program is None and offered_match is not None:
        programs = _programs_summary(offered_match)
        offered_match = None
    matched = matched and _matches_semester(
        accreditation,
        filters.semester,
        filters.semester_type,
    )

    return AccreditationMatch(
        offered_in=offered_match,
        programs=programs,
        semester=accreditation.semester if filters.semester is None else None,
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
    filters: _AccreditationFilter,
) -> dict[str, AccreditationMatch]:
    entries: dict[str, AccreditationMatch] = {}
    for year, acc in (course.accreditations or {}).items():
        if not acc.available:
            continue
        if filters.accreditation is not None and year != filters.accreditation:
            continue
        entry, matched = _evaluate_accreditation(acc, filters)
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
    *,
    participants: int | None = None,
) -> CourseMatch:
    return CourseMatch(
        name=course.name,
        abbreviation=course.abbreviation,
        tags=course.tags if tags is not None else None,
        professors=[p for p in course.staff.professors if p in professors.candidates]
        or None,
        assistants=[a for a in course.staff.assistants if a in assistants.candidates]
        or None,
        participants=participants,
        accreditations=accreditations,
    )


def _reported_accreditations(
    entries: dict[str, AccreditationMatch],
    report: bool,
) -> dict[str, AccreditationMatch] | None:
    return entries if report else None


class _Snapshot(NamedTuple):
    records: list[dict]
    courses: list[CourseData]
    latest_participants_year: str | None


_snapshots: list[_Snapshot] = []


def _course_snapshot() -> _Snapshot:
    # The HTTP cache returns the same list object until it refreshes, so the parsed
    # courses are rebuilt only when upstream data changes.
    records = get_courses()
    if _snapshots and _snapshots[0].records is records:
        return _snapshots[0]

    courses = [_build_course(record) for record in records]
    years = {
        year
        for course in courses
        for year, count in course.participants.items()
        if count > 0
    }
    snapshot = _Snapshot(records, courses, max(years, default=None))
    _snapshots[:] = [snapshot]
    return snapshot


class _QueryFilter(NamedTuple):
    normalized: str
    abbreviation_matches: list[str]


def _query_filter(query: str | None, records: list[dict]) -> _QueryFilter | None:
    query = (query or "").strip()
    if not query:
        return None
    return _QueryFilter(
        transliterate_and_normalize(query),
        resolve_abbreviation(query, build_abbreviation_index(records)),
    )


def _matches_query(course: CourseData, query: _QueryFilter | None) -> bool:
    if query is None:
        return True
    # An exact abbreviation wins over substrings, so "НП" does not also match "БнП".
    if query.abbreviation_matches:
        return course.name in query.abbreviation_matches
    names = [course.name, course.abbreviation or ""]
    names += [acc.name for acc in course.accreditations.values() if acc.name]
    return any(query.normalized in transliterate_and_normalize(n) for n in names)


class _ParticipantFilter(NamedTuple):
    year: str | None
    minimum: int | None
    maximum: int | None
    reports: bool


def _participant_count(
    course: CourseData,
    filters: _ParticipantFilter,
) -> tuple[int | None, bool]:
    if not filters.reports:
        return None, True
    count = course.participants.get(filters.year, 0) if filters.year else 0
    if filters.minimum is None and filters.maximum is None:
        return count, True
    # Upstream stores 0 for courses not running that year, so a range filter skips
    # them unless the caller asks for them with min_participants=0.
    if count == 0 and filters.minimum != 0:
        return count, False
    within = (filters.minimum is None or count >= filters.minimum) and (
        filters.maximum is None or count <= filters.maximum
    )
    return count, within


def _course_list(
    matches: list[CourseMatch],
    participants: _ParticipantFilter,
    limit: int,
    offset: int,
) -> CourseList:
    page = paginate(matches, limit=limit, offset=offset)
    return CourseList(
        total=page.total,
        truncated=page.truncated,
        note=page.note,
        participants_year=participants.year if participants.reports else None,
        items=page.items,
    )


def list_courses(
    *,
    program: StudyProgram | None = None,
    status: CourseStatus | None = None,
    semester: int | None = None,
    semester_type: SemesterType | None = None,
    accreditation: AccreditationYear | None = None,
    tags: list[CourseTag] | None = None,
    professors: list[str] | None = None,
    assistants: list[str] | None = None,
    query: str | None = None,
    participants_year: str | None = None,
    min_participants: int | None = None,
    max_participants: int | None = None,
    sort_by_participants: bool = False,
    limit: int = DEFAULT_COURSE_LIMIT,
    offset: int = 0,
) -> CourseList:
    snapshot = _course_snapshot()
    courses = snapshot.courses
    participant_filter = _ParticipantFilter(
        participants_year or snapshot.latest_participants_year,
        min_participants,
        max_participants,
        participants_year is not None
        or min_participants is not None
        or max_participants is not None
        or sort_by_participants,
    )

    professor_filter = _staff_filter(professors, courses, "professors")
    assistant_filter = _staff_filter(assistants, courses, "assistants")
    if (professors and professor_filter.groups is None) or (
        assistants and assistant_filter.groups is None
    ):
        return _course_list([], participant_filter, limit, offset)

    query_filter = _query_filter(query, snapshot.records)
    accreditation_filter = _AccreditationFilter(
        program,
        status,
        semester,
        semester_type,
        accreditation,
    )

    matches: list[CourseMatch] = []
    for course in courses:
        if not _matches_query(course, query_filter) or not _matches_course_filters(
            course, tags, professor_filter, assistant_filter
        ):
            continue

        participants, within = _participant_count(course, participant_filter)
        if not within:
            continue

        accreditations: dict[str, AccreditationMatch] | None = None
        if accreditation_filter.scopes:
            matched_entries = _matching_accreditations(course, accreditation_filter)
            if not matched_entries:
                continue
            accreditations = _reported_accreditations(
                matched_entries, accreditation_filter.reports
            )

        matches.append(
            _course_match(
                course,
                tags,
                professor_filter,
                assistant_filter,
                accreditations,
                participants=participants,
            ),
        )

    if sort_by_participants:
        matches.sort(key=lambda match: -(match.participants or 0))

    return _course_list(matches, participant_filter, limit, offset)
