import json

import anyio
import pytest
from mcp.types import CallToolResult, TextContent

from app.main import app
from app.tools import room as room_tools
from app.tools import session as session_tools
from app.tools import timetable as timetable_tools
from app.tools.room import list_rooms
from app.tools.session import list_exam_session_schedules
from app.tools.timetable import (
    list_timetable_courses,
    list_timetable_entries,
    list_timetable_groups,
    list_timetables,
)

_TIMETABLES = [
    {
        "id": "28",
        "title": "leten-2025-26",
        "dateFrom": "2026-02-23",
        "year": 2025,
        "hidden": True,
    },
    {
        "id": "31",
        "title": "zimski-2026-27",
        "dateFrom": "2026-10-10",
        "year": 2026,
        "hidden": False,
    },
    {
        "id": "30",
        "title": "zimski-2026-27-prva",
        "dateFrom": "2026-10-02",
        "year": 2026,
        "hidden": False,
    },
]


def _card(subject_id: str, subject: str, class_id: str, day: str) -> dict:
    return {
        "subject": {"id": subject_id, "name": subject},
        "classes": [{"id": class_id, "name": "2г-КН"}],
        "teachers": [{"id": "-1", "name": "Професор"}],
        "classrooms": [{"id": "9", "name": "Б1"}],
        "dayName": day,
        "startTime": "08:00",
        "endTime": "09:45",
        "durationPeriods": 2,
    }


_DETAIL = {
    "classes": [
        {"id": "15", "name": "2г-КН"},
        {"id": "16", "name": "2y-SEIS"},
        {"id": "17", "name": "3г-КН"},
    ],
    "subjects": [
        {"id": "-189", "name": "Бази на податоци (ав)"},
        {"id": "-227", "name": "Бази на податоци (п)"},
        {"id": "15", "name": "Веројатност и статистика(п)"},
    ],
    "teachers": [],
    "classrooms": [],
    "cards": [
        _card("-189", "Бази на податоци (ав)", "15", "Monday"),
        _card("-227", "Бази на податоци (п)", "15", "Tuesday"),
        _card("15", "Веројатност и статистика(п)", "15", "Friday"),
    ],
}

_SESSIONS = {
    "2025/2026 Јуни": "jun_2025_2026.xlsx",
    "2025/2026 Летен - Прв Колоквиум": "leten_kol_1_2025_2026.xlsx",
    "2024/2025 Јуни": "jun_2024_2025.xlsx",
}

_ROOMS = [
    {"name": "Амфитеатар", "type": "Амфитеатар", "location": "ТМФ"},
    {"name": "Б2.1", "type": "Лабораторија", "location": "Бараки"},
    {"name": "Б2.2", "type": "Лабораторија", "location": "Бараки"},
]


@pytest.fixture(autouse=True)
def _data(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(timetable_tools, "get_timetables", lambda: _TIMETABLES)
    monkeypatch.setattr(timetable_tools, "get_timetable_detail", lambda _id: _DETAIL)
    monkeypatch.setattr(session_tools, "get_exam_sessions", lambda: _SESSIONS)
    monkeypatch.setattr(room_tools, "get_rooms", lambda: _ROOMS)


def test_timetables_are_newest_first_with_active_flag() -> None:
    result = list_timetables()

    assert [t.id for t in result.items] == ["31", "30", "28"]
    assert [t.active for t in result.items] == [True, True, False]
    assert [t.id for t in list_timetables(academic_year=2025).items] == ["28"]

    limited = list_timetables(limit=1)
    assert limited.total == 3
    assert limited.truncated is True


def test_timetable_courses_are_listed_once() -> None:
    result = list_timetable_courses()

    assert [(c.id, c.name) for c in result.items] == [
        ("-189", "Бази на податоци"),
        ("15", "Веројатност и статистика"),
    ]
    assert [c.name for c in list_timetable_courses(query="bazi").items] == [
        "Бази на податоци",
    ]


@pytest.mark.parametrize("course_id", ["-189", "-227"])
def test_course_id_includes_lectures_and_exercises(course_id: str) -> None:
    entries = list_timetable_entries(course_id=course_id)

    assert [e.day for e in entries] == ["Понеделник", "Вторник"]


def test_timetable_groups_query() -> None:
    assert [g.name for g in list_timetable_groups(query="КН").items] == [
        "2г-КН",
        "3г-КН",
    ]
    assert [g.name for g in list_timetable_groups(query="seis").items] == ["2y-SEIS"]
    assert list_timetable_groups().total == 3


def test_exam_session_filters() -> None:
    assert [
        f.session for f in list_exam_session_schedules(academic_year="2024/2025").items
    ] == [
        "2024/2025 Јуни",
    ]
    assert [
        f.session for f in list_exam_session_schedules(query="kolokvium").items
    ] == [
        "2025/2026 Летен - Прв Колоквиум",
    ]
    assert list_exam_session_schedules(limit=1).truncated is True


def test_rooms_query_and_limit() -> None:
    assert [r.name for r in list_rooms(query="b2").items] == ["Б2.1", "Б2.2"]
    assert [r.name for r in list_rooms(query="амфитеатар").items] == ["Амфитеатар"]

    limited = list_rooms(limit=2)
    assert limited.total == 3
    assert len(limited.items) == 2
    assert limited.truncated is True


def test_list_tools_return_compact_json_with_structured_content() -> None:
    async def call() -> CallToolResult:
        result = await app.call_tool("list_rooms", {"type": "Лабораторија", "limit": 1})
        assert isinstance(result, CallToolResult)
        return result

    result = anyio.run(call)
    (block,) = result.content
    assert isinstance(block, TextContent)
    structured = result.structured_content
    assert structured is not None

    assert "\n" not in block.text
    assert json.loads(block.text) == structured
    assert structured["total"] == 2
    assert structured["truncated"] is True
    assert structured["items"] == [
        {"name": "Б2.1", "type": "Лабораторија", "location": "Бараки"},
    ]


def test_study_programs_tool_wraps_list_for_structured_content() -> None:
    async def call() -> CallToolResult:
        result = await app.call_tool("list_study_programs", {"query": "SEIS23_3"})
        assert isinstance(result, CallToolResult)
        return result

    structured = anyio.run(call).structured_content

    assert structured == {
        "result": [
            {
                "code": "SEIS23_3",
                "abbreviation": "SEIS",
                "name": "Software Engineering and Information Systems",
                "cycle": "прв",
                "duration_years": 3,
                "accreditation": "2023",
                "language": "англиски",
                "url": "https://finki.ukim.mk/program/SEIS23_3",
            },
        ],
    }
