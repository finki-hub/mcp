import re
from typing import Required, TypedDict, cast

from app.utils.http_client import get_courses

_YEAR_KEY_RE = re.compile(r"^\d{4}/\d{4}$")


class CourseParticipantsRow(TypedDict, total=False):
    course: Required[str]
    error: str | None
    suggestions: list[str] | None
    match_info: dict | None


def _get_participants_data() -> list[CourseParticipantsRow]:
    result: list[CourseParticipantsRow] = []

    for row in get_courses():
        entry: dict[str, str | int] = {"course": row["name"]}

        for key, value in row.items():
            if _YEAR_KEY_RE.match(key):
                try:
                    entry[key] = int(value)
                except ValueError, TypeError:
                    entry[key] = 0

        result.append(cast(CourseParticipantsRow, entry))

    return result


def get_available_courses_for_participants() -> list[str]:
    return [row["course"] for row in _get_participants_data()]


def get_participants_for_course(course_name: str) -> CourseParticipantsRow:
    for row in _get_participants_data():
        if row["course"] == course_name:
            return row

    return CourseParticipantsRow(
        course=course_name,
        error="Предметот не е пронајден",
    )
