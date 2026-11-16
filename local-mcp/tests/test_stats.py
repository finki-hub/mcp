import anyio
import pytest
from mcp.types import CallToolResult

from app.main import app
from app.schemas.stats import StatsMetric
from app.schemas.thesis_search import ThesisKind
from app.tools import directus_lookup, schedule
from app.tools import stats as stats_tools
from app.tools.stats import stats

_COURSES = [
    {"id": 1, "name": "Структурно програмирање"},
    {"id": 2, "name": "Бази на податоци"},
]
_STAFF = [{"id": 24, "name": "Весна Димитрова"}, {"id": 97, "name": "Ристе Стојанов"}]
_YEARS = [{"id": 1, "label": "2026/2027"}, {"id": 2, "label": "2025/2026"}]


def _items(collection: str, params: dict[str, str | int]) -> list[dict]:
    if collection == "course_enrollments" and params["groupBy[]"] == "academic_year":
        return [
            {"academic_year": 1, "sum": {"count": None}},
            {"academic_year": 2, "sum": {"count": "1500"}},
        ]
    if collection == "course_enrollments":
        assert params["filter[academic_year][label][_eq]"] == "2025/2026"
        return [
            {"course": 1, "sum": {"count": "877"}},
            {"course": 2, "sum": {"count": "983"}},
            {"course": 99, "sum": {"count": "5"}},
        ]
    if collection in {"bachelor_theses", "master_theses"}:
        return (
            [
                {"year": 2025, "count": {"id": "680"}},
                {"year": 2026, "count": {"id": "527"}},
            ]
            if collection == "bachelor_theses"
            else [{"year": 2026, "count": {"id": "40"}}]
        )
    if collection == "bachelor_thesis_staff" and params["groupBy[]"] == "year":
        assert params["filter[staff][_eq]"] == 24
        return [{"year": 2026, "count": {"id": "8"}}]
    if collection == "master_thesis_staff" and params["groupBy[]"] == "year":
        return [{"year": 2026, "count": {"id": "3"}}]
    if collection == "bachelor_thesis_staff":
        return [
            {"staff": 24, "count": {"id": "9"}},
            {"staff": 97, "count": {"id": "32"}},
        ]
    if collection == "master_thesis_staff":
        return [{"staff": 24, "count": {"id": "3"}}]
    if collection == "course_teaching":
        return [
            {"staff": 24, "sum": {"periods": "5"}, "countDistinct": {"course": "2"}},
            {"staff": 97, "sum": {"periods": "12"}, "countDistinct": {"course": "3"}},
        ]
    return {
        "courses": _COURSES,
        "staff": _STAFF,
        "academic_years": _YEARS,
        "timetables": [{"id": 1, "title": "raspored"}],
    }[collection]


@pytest.fixture(autouse=True)
def _data(monkeypatch: pytest.MonkeyPatch) -> None:
    for module in (directus_lookup, schedule, stats_tools):
        monkeypatch.setattr(module, "get_directus_items", _items)


def test_top_courses_default_to_the_latest_year_with_enrollments() -> None:
    result = stats(StatsMetric.TOP_COURSES, limit=1)

    assert result.scope == "2025/2026"
    assert result.total == 2
    assert [(r.label, r.value) for r in result.rows or []] == [
        ("Бази на податоци", 983)
    ]


def test_theses_per_year_newest_first_with_kinds() -> None:
    result = stats(StatsMetric.THESES_PER_YEAR)

    assert [(r.label, r.value, r.parts) for r in result.rows or []] == [
        ("2026", 567, {"bachelor": 527, "master": 40}),
        ("2025", 680, {"bachelor": 680}),
    ]


def test_theses_per_year_of_one_mentor() -> None:
    result = stats(StatsMetric.THESES_PER_YEAR, staff="Весна Димитрова")

    assert result.scope == "Весна Димитрова"
    assert result.unit == "трудови како ментор"
    assert [(r.label, r.value) for r in result.rows or []] == [("2026", 11)]


def test_top_mentors_across_kinds() -> None:
    result = stats(StatsMetric.TOP_MENTORS, year=2026)

    assert result.scope == "2026"
    assert [(r.label, r.value) for r in result.rows or []] == [
        ("Ристе Стојанов", 32),
        ("Весна Димитрова", 12),
    ]
    only_master = stats(StatsMetric.TOP_MENTORS, kind=ThesisKind.MASTER)
    assert [r.label for r in only_master.rows or []] == ["Весна Димитрова"]


def test_teaching_load_in_the_current_timetable() -> None:
    result = stats(StatsMetric.TEACHING_LOAD)

    assert result.scope == "raspored"
    assert [(r.label, r.value, r.parts) for r in result.rows or []] == [
        ("Ристе Стојанов", 12, {"courses": 3}),
        ("Весна Димитрова", 5, {"courses": 2}),
    ]


def test_unknown_staff_member() -> None:
    result = stats(StatsMetric.THESES_PER_YEAR, staff="Непознат Човек")

    assert result.error
    assert result.rows is None


def test_stats_tool_returns_structured_content() -> None:
    async def call() -> CallToolResult:
        result = await app.call_tool("stats", {"metric": "teaching_load", "limit": 1})
        assert isinstance(result, CallToolResult)
        return result

    structured = anyio.run(call).structured_content

    assert structured is not None
    assert structured["rows"] == [
        {"label": "Ристе Стојанов", "value": 12, "parts": {"courses": 3}},
    ]
