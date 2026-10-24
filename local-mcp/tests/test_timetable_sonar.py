from typing import Any

import pytest

from app.schemas.timetable import TimetableDay, TimetableLessonType
from app.tools import timetable
from app.tools.timetable import _lesson_tokens_and_course_name


@pytest.mark.parametrize(
    ("name", "tokens", "course"),
    [
        ("  Course ( П + ав + лаб )  ", ["п", "ав", "лаб"], "Course"),
        ("Course (+п++)", ["п"], "Course"),
        ("Course ((п)", ["п"], "Course ("),
        ("Course (п))", [], "Course (п))"),
        ("Course (unknown)", [], "Course (unknown)"),
        ("Course ()", [], "Course ()"),
        ("", [], ""),
        ("Course\u2003(П)\n", ["п"], "Course"),
        ("(" * 100_000, [], "(" * 100_000),
        (" " * 100_000 + "x", [], "x"),
        ("(" + "x" * 100_000 + ")", [], "(" + "x" * 100_000 + ")"),
    ],
    ids=[f"suffix-{index}" for index in range(11)],
)
def test_lesson_suffix(name: str, tokens: list[str], course: str) -> None:
    assert _lesson_tokens_and_course_name(name) == (tokens, course)


def test_entry_filters(monkeypatch: pytest.MonkeyPatch) -> None:
    card = {
        "subject": {"id": "c", "name": "Course (п+ав)"},
        "classes": [{"id": "g", "name": "Group"}],
        "teachers": [{"id": "p", "name": " Professor "}, {"name": " "}],
        "classrooms": [{"id": "r", "name": "Room"}],
        "dayName": "Monday",
        "startTime": "09:00",
        "endTime": "10:00",
        "durationPeriods": 1,
    }
    monkeypatch.setattr(timetable, "_get_timetable", lambda _id: {"cards": [card]})
    entries = timetable.list_timetable_entries(
        group_id=" g ",
        professor_id="p",
        room_id="r",
        course_id="c",
        day=TimetableDay.MONDAY,
        lesson_type=TimetableLessonType.LECTURE,
        start_after="09:00",
        end_before="10:00",
    )
    assert len(entries) == 1
    assert entries[0].professors == ["Professor"]
    assert entries[0].course == "Course"
    filter_cases: list[dict[str, Any]] = [
        {"group_id": "missing"},
        {"professor_id": "missing"},
        {"room_id": "missing"},
        {"course_id": "missing"},
        {"day": TimetableDay.TUESDAY},
        {"lesson_type": TimetableLessonType.LABORATORY_EXERCISES},
        {"start_after": "09:01"},
        {"end_before": "09:59"},
    ]
    for filters in filter_cases:
        assert timetable.list_timetable_entries(**({"course_id": "c"} | filters)) == []
    card["startTime"] = None
    assert timetable.list_timetable_entries(course_id="c", start_after="09:00") == []
    card["endTime"] = " "
    assert timetable.list_timetable_entries(course_id="c", end_before="10:00") == []


def test_empty_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    def unexpected_fetch(_id: str | None) -> dict:
        pytest.fail("An unfiltered request must not fetch a timetable")

    monkeypatch.setattr(timetable, "_get_timetable", unexpected_fetch)
    assert timetable.list_timetable_entries(group_id=" ", start_after="invalid") == []
    monkeypatch.setattr(timetable, "_get_timetable", lambda _id: {})
    assert timetable.list_timetable_entries(course_id="c") == []
