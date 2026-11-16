import json

import anyio
import pytest
from mcp.types import CallToolResult

from app.main import app
from app.schemas.staff_details import StaffInclude
from app.schemas.timetable import TimetableDay
from app.tools import directus_lookup, schedule, staff_details
from app.tools.schedule import schedule as schedule_of
from app.tools.staff_details import get_staff

_STAFF = [
    {"id": 4, "name": "Александра Каневче Дединец"},
    {"id": 23, "name": "Весна Димитриевска Ристовска"},
    {"id": 24, "name": "Весна Димитрова"},
]
_PROFILE = {
    "id": 24,
    "name": "Весна Димитрова",
    "title": "д-р",
    "position": "Редовен професор",
    "active": True,
    "email": "vesna.dimitrova@finki.ukim.mk",
    "cabinet": "209",
    "consultations": None,
    "courses": None,
    "profile": None,
}
_COURSES = [
    {
        "id": 9,
        "name": "Алгоритми и податочни структури",
        "name_en": "Algorithms and Data Structures",
        "abbreviation": "АПС",
    },
    {
        "id": 20,
        "name": "Криптографија",
        "name_en": "Cryptography",
        "abbreviation": None,
    },
]
_ROOMS = [
    {"id": 1, "name": "Б2.2", "location": "Бараки"},
    {"id": 2, "name": "117", "location": "ТМФ"},
    {"id": 3, "name": "117", "location": "Бараки"},
]
_TIMETABLES = [{"id": 1, "title": "raspored-zimski-2026-27-W"}]


def _slot(**values: object) -> dict:
    return {
        "subject": "Алгоритми и податочни структури",
        "kind": "п",
        "day": 1,
        "starts": "08:10",
        "ends": "09:45",
        "groups": "2г-КН, 2г-КИ",
        "classroom": "Б 2.2",
        "teachers": "Весна Димитрова",
        "course": {"id": 9, "name": "Алгоритми и податочни структури"},
        "room": {"id": 1, "name": "Б2.2", "location": "Бараки"},
        "staff": [{"staff": {"id": 24, "name": "Весна Димитрова"}}],
        **values,
    }


_SLOTS = [
    _slot(day=3, starts="12:00"),
    _slot(),
    _slot(
        subject="Криптографија",
        kind="ав",
        day=2,
        groups="3г-СИИС",
        teachers="Александра Дединец",
        course={"id": 20, "name": "Криптографија"},
        room={"id": 2, "name": "117", "location": "ТМФ"},
        staff=[{"staff": {"id": 4, "name": "Александра Каневче Дединец"}}],
    ),
    _slot(
        subject="Онлајн предавање",
        course=None,
        room=None,
        classroom="online",
        teachers="Демонстратор 4",
        staff=[],
        groups="1г-КН",
        day=5,
    ),
]


def _items(collection: str, params: dict[str, str | int]) -> list[dict]:
    if collection == "staff":
        return [_PROFILE] if "filter[id][_eq]" in params else _STAFF
    if collection == "course_teaching":
        return [
            {"role": "professor", "periods": 3, "course": {"name": "Криптографија"}}
        ]
    if collection == "bachelor_thesis_staff":
        return [
            {
                "role": "mentor",
                "year": 2025,
                "thesis": {"title": "Стара", "submitted": "2025-01-01"},
            },
            {
                "role": "mentor",
                "year": 2026,
                "thesis": {"title": "Нова", "submitted": "2026-11-01"},
            },
            {"role": "member", "year": 2026, "thesis": {"title": "Туѓа"}},
        ]
    if collection == "master_thesis_staff":
        return [{"role": "president", "year": 2026, "thesis": {"title": "М"}}]
    if collection == "degree_programs":
        return [{"code": "BKK23_2", "name": "Безбедност, криптографија и кодирање"}]
    return {
        "courses": _COURSES,
        "rooms": _ROOMS,
        "timetables": _TIMETABLES,
        "timetable_slots": _SLOTS,
    }[collection]


@pytest.fixture(autouse=True)
def _data(monkeypatch: pytest.MonkeyPatch) -> None:
    for module in (directus_lookup, schedule, staff_details):
        monkeypatch.setattr(module, "get_directus_items", _items)


def test_staff_schedule_is_sorted_by_day_and_time() -> None:
    result = schedule_of(staff="vesna dimitrova")

    assert result.matched == {"staff": "Весна Димитрова"}
    assert result.timetable == "raspored-zimski-2026-27-W"
    assert [(e.day, e.starts) for e in result.entries or []] == [
        (TimetableDay.MONDAY, "08:10"),
        (TimetableDay.WEDNESDAY, "12:00"),
    ]
    assert (result.entries or [])[0].room == "Б2.2 (Бараки)"


def test_course_by_abbreviation_and_day() -> None:
    result = schedule_of(course="АПС", day=TimetableDay.WEDNESDAY)

    assert result.matched == {"course": "Алгоритми и податочни структури"}
    assert [e.starts for e in result.entries or []] == ["12:00"]


def test_filters_combine_with_and() -> None:
    assert schedule_of(staff="Весна Димитрова", course="Криптографија").entries == []


def test_a_room_name_in_two_buildings_asks_for_the_location() -> None:
    result = schedule_of(room="117")

    assert result.entries is None
    assert result.suggestions == ["117 (ТМФ)", "117 (Бараки)"]
    assert [e.course for e in schedule_of(room="117 (ТМФ)").entries or []] == [
        "Криптографија",
    ]


def test_group_matches_the_start_of_a_class_name() -> None:
    result = schedule_of(group="3г-сиис")

    assert [e.course for e in result.entries or []] == ["Криптографија"]


def test_unlinked_slot_keeps_the_timetable_names() -> None:
    (entry,) = schedule_of(group="1г-КН").entries or []

    assert entry.course == "Онлајн предавање"
    assert entry.room == "online"
    assert entry.staff == ["Демонстратор 4"]


def test_ambiguous_staff_returns_suggestions() -> None:
    result = schedule_of(staff="Весна")

    assert result.entries is None
    assert result.suggestions == ["Весна Димитриевска Ристовска", "Весна Димитрова"]


def test_a_filter_is_required() -> None:
    assert schedule_of(group="  ").error


def test_get_staff_includes_only_what_is_asked() -> None:
    brief = get_staff("Весна Димитрова")

    assert brief.staff is not None
    assert brief.staff.cabinet == "209"
    assert brief.teaching is None
    assert brief.schedule is None
    assert brief.theses is None


def test_get_staff_with_everything() -> None:
    details = get_staff("Весна Димитрова", list(StaffInclude))

    assert details.timetable == "raspored-zimski-2026-27-W"
    assert [c.course for c in details.teaching or []] == ["Криптографија"]
    assert len(details.schedule or []) == 2
    assert details.theses is not None
    assert details.theses.bachelor.mentor == 2
    assert details.theses.bachelor.member == 1
    assert details.theses.master.president == 1
    assert [t.title for t in details.theses.recent_mentored or []] == ["Нова", "Стара"]
    assert [p.code for p in details.programs or []] == ["BKK23_2"]


def test_get_staff_unknown_name() -> None:
    details = get_staff("Непознат Човек")

    assert details.staff is None
    assert details.error


def test_schedule_tool_returns_compact_json() -> None:
    async def call() -> CallToolResult:
        result = await app.call_tool("schedule", {"staff": "Дединец"})
        assert isinstance(result, CallToolResult)
        return result

    result = anyio.run(call)
    structured = result.structured_content

    assert structured is not None
    assert structured["matched"] == {"staff": "Александра Каневче Дединец"}
    assert json.loads(result.content[0].text) == structured  # type: ignore[union-attr]
