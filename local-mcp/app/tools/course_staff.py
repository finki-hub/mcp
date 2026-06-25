from typing import NotRequired, TypedDict

from app.utils.http_client import get_courses


class CourseStaffRow(TypedDict):
    course: str
    professors: list[str]
    assistants: list[str]
    error: NotRequired[str]
    suggestions: NotRequired[list[str] | None]
    match_info: NotRequired[dict | None]


def _get_staff_data() -> list[CourseStaffRow]:
    return [
        CourseStaffRow(
            course=row["name"],
            professors=row.get("professors", "").split("\n")
            if row.get("professors")
            else [],
            assistants=row.get("assistants", "").split("\n")
            if row.get("assistants")
            else [],
        )
        for row in get_courses()
    ]


def get_available_courses_for_staff() -> list[str]:
    return [row["course"] for row in _get_staff_data()]


def get_staff_for_course(course_name: str) -> CourseStaffRow:
    for row in _get_staff_data():
        if row["course"] == course_name:
            return row

    return CourseStaffRow(
        course=course_name,
        professors=[],
        assistants=[],
        error="Предметот не е пронајден",
    )
