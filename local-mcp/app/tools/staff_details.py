from collections import Counter

from app.schemas.staff import StaffProfile
from app.schemas.staff_details import (
    CoordinatedProgram,
    MentoredThesis,
    StaffDetails,
    StaffInclude,
    StaffTheses,
    TaughtCourse,
    ThesisRoleCounts,
)
from app.tools.directus_lookup import find_staff
from app.tools.schedule import (
    current_timetable,
    sorted_entries,
    staff_ids,
    timetable_slots,
)
from app.utils.http_client import get_directus_items

# A staff member from Directus, with what the caller includes: the courses
# and classes of the latest main timetable, their theses and the programs
# they coordinate.

_PROFILE_FIELDS = (
    "id,name,title,position,active,email,cabinet,consultations,courses,profile"
)
_RECENT_MENTORED = 5


def _profile(record: dict) -> StaffProfile:
    return StaffProfile(
        title=record.get("title") or None,
        position=record.get("position") or None,
        active=bool(record.get("active")),
        email=record.get("email") or None,
        cabinet=record.get("cabinet") or None,
        consultations=record.get("consultations") or None,
        courses=record.get("courses") or None,
        profile=record.get("profile") or None,
    )


def _teaching(staff_id: int, timetable_id: int) -> list[TaughtCourse]:
    rows = get_directus_items(
        "course_teaching",
        {
            "fields": "role,periods,course.name",
            "filter[staff][_eq]": staff_id,
            "filter[timetable][_eq]": timetable_id,
            "limit": -1,
        },
    )
    courses = [
        TaughtCourse(
            course=row["course"]["name"], role=row["role"], periods=row["periods"]
        )
        for row in rows
        if isinstance(row.get("course"), dict)
    ]
    return sorted(courses, key=lambda course: course.course)


def _thesis_rows(collection: str, staff_id: int, date: str) -> list[dict]:
    return get_directus_items(
        collection,
        {
            "fields": f"role,year,thesis.id,thesis.title,thesis.status,thesis.student_name,thesis.{date}",
            "filter[staff][_eq]": staff_id,
            "limit": -1,
        },
    )


def _counts(rows: list[dict]) -> ThesisRoleCounts:
    roles = Counter(row["role"] for row in rows)
    return ThesisRoleCounts(
        mentor=roles["mentor"],
        member=roles["member"],
        president=roles["president"],
    )


def _mentored(
    kind: str, rows: list[dict], date: str
) -> list[tuple[str, MentoredThesis]]:
    return [
        (
            row["thesis"].get(date) or "",
            MentoredThesis(
                kind=kind,
                title=row["thesis"]["title"],
                student=row["thesis"].get("student_name"),
                status=row["thesis"].get("status"),
                year=row.get("year"),
            ),
        )
        for row in rows
        if row["role"] == "mentor" and isinstance(row.get("thesis"), dict)
    ]


def _theses(staff_id: int) -> StaffTheses:
    bachelor = _thesis_rows("bachelor_thesis_staff", staff_id, "submitted")
    master = _thesis_rows("master_thesis_staff", staff_id, "presented")
    mentored = sorted(
        _mentored("bachelor", bachelor, "submitted")
        + _mentored("master", master, "presented"),
        key=lambda pair: pair[0],
        reverse=True,
    )
    return StaffTheses(
        bachelor=_counts(bachelor),
        master=_counts(master),
        recent_mentored=[thesis for _date, thesis in mentored[:_RECENT_MENTORED]]
        or None,
    )


def _programs(staff_id: int) -> list[CoordinatedProgram]:
    rows = get_directus_items(
        "degree_programs",
        {
            "fields": "code,name",
            "filter[coordinator][_eq]": staff_id,
            "sort": "code",
            "limit": -1,
        },
    )
    return [CoordinatedProgram(code=row["code"], name=row["name"]) for row in rows]


def get_staff(
    name: str,
    include: list[StaffInclude] | None = None,
) -> StaffDetails:
    found = find_staff(name)
    if found.record is None:
        return StaffDetails(name=name, error=found.error, suggestions=found.suggestions)

    staff_id = found.record["id"]
    (record,) = get_directus_items(
        "staff",
        {"fields": _PROFILE_FIELDS, "filter[id][_eq]": staff_id},
    )
    details = StaffDetails(name=record["name"], staff=_profile(record))
    wanted = set(include or ())

    if wanted & {StaffInclude.TEACHING, StaffInclude.SCHEDULE}:
        timetable = current_timetable()
        if timetable is not None:
            details.timetable = timetable["title"]
            if StaffInclude.TEACHING in wanted:
                details.teaching = _teaching(staff_id, timetable["id"])
            if StaffInclude.SCHEDULE in wanted:
                details.schedule = sorted_entries(
                    [
                        slot
                        for slot in timetable_slots(timetable["id"])
                        if staff_id in staff_ids(slot)
                    ],
                )
    if StaffInclude.THESES in wanted:
        details.theses = _theses(staff_id)
    if StaffInclude.PROGRAMS in wanted:
        details.programs = _programs(staff_id)
    return details
