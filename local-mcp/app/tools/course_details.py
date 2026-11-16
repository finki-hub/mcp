from app.schemas.course_details import (
    CourseCurriculum,
    CourseDetails,
    CourseInclude,
    CourseSyllabusText,
    CourseTeacher,
)
from app.tools.directus_lookup import find_course
from app.tools.schedule import current_timetable, sorted_entries, timetable_slots
from app.utils.http_client import get_directus_items

# A course from Directus, with what the caller includes: its place in each
# accreditation, syllabus, equivalent courses, enrollments, and its staff
# and classes in the latest main timetable.

_NOT_OFFERED = "нема"

_BASE_FIELDS = ("id", "name", "name_en", "abbreviation", "status", "tags")
_INCLUDED_FIELDS: dict[CourseInclude, tuple[str, ...]] = {
    CourseInclude.CURRICULA: (
        "curricula.credits",
        "curricula.available",
        "curricula.generation.code",
        "curricula.generation.published",
        "curricula.entry.name",
        "curricula.entry.code",
        "curricula.entry.semester",
        "curricula.entry.prerequisites",
        "curricula.entry.program_states.state",
        "curricula.entry.program_states.program.name",
    ),
    CourseInclude.SYLLABUS: ("objectives", "content", "objectives_en", "content_en"),
    CourseInclude.EQUIVALENCIES: (
        "equivalencies.members.label",
        "equivalencies.members.generation.code",
    ),
    CourseInclude.ENROLLMENTS: (
        "enrollments.count",
        "enrollments.academic_year.label",
    ),
}


def _curricula(record: dict) -> list[CourseCurriculum]:
    rows: list[CourseCurriculum] = []
    for link in record.get("curricula") or []:
        generation = link.get("generation") or {}
        if not generation.get("published"):
            continue
        entry = link.get("entry") or {}
        programs = {
            state["program"]["name"]: state["state"]
            for state in entry.get("program_states") or []
            if isinstance(state.get("program"), dict)
            and state.get("state") != _NOT_OFFERED
        }
        name = entry.get("name")
        rows.append(
            CourseCurriculum(
                accreditation=generation["code"],
                code=entry.get("code"),
                name=name if name and name != record["name"] else None,
                semester=entry.get("semester"),
                credits=link.get("credits"),
                available=link.get("available"),
                prerequisites=entry.get("prerequisites") or None,
                programs=programs or None,
            ),
        )
    return sorted(rows, key=lambda row: row.accreditation, reverse=True)


def _syllabus(record: dict) -> CourseSyllabusText | None:
    syllabus = CourseSyllabusText(
        objectives=record.get("objectives") or None,
        content=record.get("content") or None,
        objectives_en=record.get("objectives_en") or None,
        content_en=record.get("content_en") or None,
    )
    return syllabus if syllabus.model_dump() else None


def _equivalencies(record: dict) -> list[list[str]] | None:
    groups = [
        sorted(
            f"{member['label']} ({member['generation']['code']})"
            for member in group.get("members") or []
            if member.get("label") and isinstance(member.get("generation"), dict)
        )
        for group in record.get("equivalencies") or []
    ]
    return [group for group in groups if len(group) > 1] or None


def _enrollments(record: dict) -> dict[str, int] | None:
    counts = {
        row["academic_year"]["label"]: row["count"]
        for row in record.get("enrollments") or []
        if isinstance(row.get("academic_year"), dict) and row.get("count")
    }
    return dict(sorted(counts.items(), reverse=True)) or None


def _teaching(course_id: int, timetable_id: int) -> list[CourseTeacher]:
    rows = get_directus_items(
        "course_teaching",
        {
            "fields": "role,periods,staff.name",
            "filter[course][_eq]": course_id,
            "filter[timetable][_eq]": timetable_id,
            "limit": -1,
        },
    )
    teachers = [
        CourseTeacher(
            staff=row["staff"]["name"], role=row["role"], periods=row["periods"]
        )
        for row in rows
        if isinstance(row.get("staff"), dict)
    ]
    # Professors first, then by name.
    return sorted(teachers, key=lambda row: (row.role != "professor", row.staff))


def get_course(
    name: str,
    include: list[CourseInclude] | None = None,
) -> CourseDetails:
    found = find_course(name)
    if found.record is None:
        return CourseDetails(
            name=name, error=found.error, suggestions=found.suggestions
        )

    wanted = set(include or ())
    fields: list[str] = list(_BASE_FIELDS)
    for part in wanted:
        fields.extend(_INCLUDED_FIELDS.get(part, ()))
    records = get_directus_items(
        "courses",
        {"fields": ",".join(sorted(fields)), "filter[id][_eq]": found.record["id"]},
    )
    if not records:
        return CourseDetails(name=name, error=f"„{name}“ не е пронајден (предмети)")
    record = records[0]

    details = CourseDetails(
        name=record["name"],
        name_en=record.get("name_en") or None,
        abbreviation=record.get("abbreviation") or None,
        status=record.get("status") or None,
        tags=record.get("tags") or None,
    )
    if CourseInclude.CURRICULA in wanted:
        details.curricula = _curricula(record) or None
    if CourseInclude.SYLLABUS in wanted:
        details.syllabus = _syllabus(record)
    if CourseInclude.EQUIVALENCIES in wanted:
        details.equivalencies = _equivalencies(record)
    if CourseInclude.ENROLLMENTS in wanted:
        details.enrollments = _enrollments(record)
    if wanted & {CourseInclude.TEACHING, CourseInclude.SCHEDULE}:
        timetable = current_timetable()
        if timetable is not None:
            details.timetable = timetable["title"]
            if CourseInclude.TEACHING in wanted:
                details.teaching = _teaching(record["id"], timetable["id"])
            if CourseInclude.SCHEDULE in wanted:
                details.schedule = sorted_entries(
                    [
                        slot
                        for slot in timetable_slots(timetable["id"])
                        if (slot.get("course") or {}).get("id") == record["id"]
                    ],
                )
    return details
