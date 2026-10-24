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
        abbreviation=record.get("abbreviation") or None,
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


def _evaluate_accreditation(
    accreditation: Accreditation,
    program: StudyProgram | None,
    status: CourseStatus | None,
    semester: int | None,
    semester_type: SemesterType | None = None,
) -> tuple[AccreditationMatch, bool]:
    offered = accreditation.offered_in or {}
    offered_match: dict[str, str] | None = None
    programs: str | None = None
    matched = True

    if program is not None:
        key = program if program in offered else _SAME_PROGRAM.get(program, program)
        offered_match = {key: offered[key]} if key in offered else {}
        if key not in offered or (
            status is not None and _base_status(offered[key]) != status
        ):
            matched = False
    elif status is not None:
        # The status is implied by the filter; keep only qualifiers such as "(4 г.)".
        programs = ", ".join(
            p + value.removeprefix(_base_status(value))
            for p, value in offered.items()
            if _base_status(value) == status
        )
        if not programs:
            matched = False

    if semester is not None and accreditation.semester != semester:
        matched = False
    if semester_type is not None and (
        accreditation.semester is None
        or (accreditation.semester % 2 == 1) != (semester_type == SemesterType.WINTER)
    ):
        matched = False

    return AccreditationMatch(
        offered_in=offered_match,
        programs=programs or None,
        semester=accreditation.semester if semester is None else None,
    ), matched


def _resolve_staff_groups(names: list[str], pool: list[str]) -> list[list[str]] | None:
    groups: list[list[str]] = []
    for name in names:
        group = match_query_to_group(name, pool)
        if group is None:
            return None
        groups.append(group)
    return groups


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


def _query_matches(
    course: CourseData,
    normalized_query: str,
    abbreviation_matches: list[str],
) -> bool:
    # An exact abbreviation wins over substrings, so "НП" does not also match "БнП".
    if abbreviation_matches:
        return course.name in abbreviation_matches
    names = [course.name, course.abbreviation or ""]
    names += [acc.name for acc in course.accreditations.values() if acc.name]
    return any(normalized_query in transliterate_and_normalize(n) for n in names)


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

    report_participants = (
        participants_year is not None
        or min_participants is not None
        or max_participants is not None
        or sort_by_participants
    )
    year = participants_year or snapshot.latest_participants_year

    def page_of(matches: list[CourseMatch]) -> CourseList:
        page = paginate(matches, limit=limit, offset=offset)
        return CourseList(
            total=page.total,
            truncated=page.truncated,
            note=page.note,
            participants_year=year if report_participants else None,
            items=page.items,
        )

    professor_groups: list[list[str]] | None = None
    professor_candidates: set[str] = set()
    if professors:
        pool = sorted({n for c in courses for n in c.staff.professors})
        professor_groups = _resolve_staff_groups(professors, pool)
        if professor_groups is None:
            return page_of([])
        professor_candidates = {m for group in professor_groups for m in group}

    assistant_groups: list[list[str]] | None = None
    assistant_candidates: set[str] = set()
    if assistants:
        pool = sorted({n for c in courses for n in c.staff.assistants})
        assistant_groups = _resolve_staff_groups(assistants, pool)
        if assistant_groups is None:
            return page_of([])
        assistant_candidates = {m for group in assistant_groups for m in group}

    query = (query or "").strip()
    normalized_query = transliterate_and_normalize(query) if query else ""
    abbreviation_matches = (
        resolve_abbreviation(query, build_abbreviation_index(snapshot.records))
        if query
        else []
    )

    report_accreditations = (
        program is not None
        or status is not None
        or semester is not None
        or semester_type is not None
    )
    scopes_accreditations = report_accreditations or accreditation is not None

    matches: list[CourseMatch] = []
    for course in courses:
        if normalized_query and not _query_matches(
            course,
            normalized_query,
            abbreviation_matches,
        ):
            continue

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

        participants: int | None = None
        if report_participants:
            participants = course.participants.get(year, 0) if year else 0
            # Upstream stores 0 for courses not running that year, so a range filter
            # skips them unless the caller asks for them with min_participants=0.
            filtered = min_participants is not None or max_participants is not None
            if filtered and participants == 0 and min_participants != 0:
                continue
            if min_participants is not None and participants < min_participants:
                continue
            if max_participants is not None and participants > max_participants:
                continue

        accreditations: dict[str, AccreditationMatch] | None = None
        if scopes_accreditations:
            matched_entries: dict[str, AccreditationMatch] = {}
            any_match = False
            for acc_year, acc in (course.accreditations or {}).items():
                if not acc.available:
                    continue
                if accreditation is not None and acc_year != accreditation:
                    continue
                entry, matched = _evaluate_accreditation(
                    acc,
                    program,
                    status,
                    semester,
                    semester_type,
                )
                if not matched:
                    continue
                any_match = True
                if report_accreditations:
                    matched_entries[acc_year] = entry
            if not any_match:
                continue
            accreditations = matched_entries or None

        matches.append(
            CourseMatch(
                name=course.name,
                abbreviation=course.abbreviation,
                tags=course.tags if tags is not None else None,
                professors=[p for p in course_professors if p in professor_candidates]
                or None,
                assistants=[a for a in course_assistants if a in assistant_candidates]
                or None,
                participants=participants,
                accreditations=accreditations,
            ),
        )

    if sort_by_participants:
        matches.sort(key=lambda match: -(match.participants or 0))

    return page_of(matches)
