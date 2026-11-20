import pytest

from app.schemas.leadership import LeadershipBody
from app.tools import leadership as leadership_tools
from app.tools.leadership import get_leadership

# Slices of Directus `deans_office` and `student_council`, as
# `get_directus_items` returns them (sorted by -year, id).
_DEANS_OFFICE = [
    {
        "id": 5,
        "year": 2025,
        "position": "Продекан за настава",
        "staff": {
            "name": "Дејан Спасов",
            "title": "д-р",
            "position": "Редовен професор",
        },
    },
    {
        "id": 6,
        "year": 2025,
        "position": "Декан",
        "staff": {
            "name": "Петре Ламески",
            "title": "д-р",
            "position": "Вонреден професор",
        },
    },
    {
        "id": 3,
        "year": 2015,
        "position": "Декан",
        "staff": {
            "name": "Андреа Кулаков",
            "title": "д-р",
            "position": "Редовен професор",
        },
    },
    {"id": 4, "year": 2015, "position": "Продекан за финансии", "staff": None},
    {
        "id": 1,
        "year": 2011,
        "position": "Декан",
        "staff": {"name": "Маргита Кон-Поповска", "title": "д-р", "position": None},
    },
]

_STUDENT_COUNCIL = [
    {"id": 70, "year": 2026, "position": "СИИС", "student": {"name": "Ана Новеска"}},
    {
        "id": 71,
        "year": 2026,
        "position": "Претседател",
        "student": {"name": "Георгина Илиевска"},
    },
    {
        "id": 10,
        "year": 2024,
        "position": "Претседател",
        "student": {"name": "Петар Петров"},
    },
]


@pytest.fixture(autouse=True)
def _data(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = {"deans_office": _DEANS_OFFICE, "student_council": _STUDENT_COUNCIL}
    monkeypatch.setattr(
        leadership_tools,
        "get_directus_items",
        lambda collection, _params: rows[collection],
    )


def test_the_current_deans_office_lists_the_dean_first() -> None:
    result = get_leadership()

    assert result.body is LeadershipBody.DEANS_OFFICE
    assert result.year == 2025
    assert [(m.position, m.name) for m in (result.members or [])] == [
        ("Декан", "Петре Ламески"),
        ("Продекан за настава", "Дејан Спасов"),
    ]
    assert (result.members or [])[0].title == "д-р"
    assert (result.members or [])[0].staff_position == "Вонреден професор"
    assert result.years == [2025, 2015, 2011]


def test_a_year_picks_the_term_in_office_then() -> None:
    assert get_leadership(year=2019).year == 2015
    assert get_leadership(year=2015).year == 2015
    assert get_leadership(year=2030).year == 2025
    # Before every recorded term: the earliest one.
    assert get_leadership(year=2005).year == 2011


def test_a_position_without_a_person_is_left_out() -> None:
    result = get_leadership(year=2015)

    assert [m.name for m in (result.members or [])] == ["Андреа Кулаков"]


def test_the_student_council_lists_its_president_first_without_staff_fields() -> None:
    result = get_leadership(LeadershipBody.STUDENT_COUNCIL)

    assert result.year == 2026
    assert [(m.position, m.name) for m in (result.members or [])] == [
        ("Претседател", "Георгина Илиевска"),
        ("СИИС", "Ана Новеска"),
    ]
    assert all(
        m.title is None and m.staff_position is None for m in (result.members or [])
    )
    assert result.years == [2026, 2024]


def test_reads_names_only_never_index_numbers(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []

    def fake(collection: str, params: dict[str, str | int]) -> list[dict]:
        seen.append(str(params["fields"]))
        return _STUDENT_COUNCIL

    monkeypatch.setattr(leadership_tools, "get_directus_items", fake)
    get_leadership(LeadershipBody.STUDENT_COUNCIL)

    assert seen == ["id,year,position,student.name"]


def test_no_members_is_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(leadership_tools, "get_directus_items", lambda *_: [])

    with pytest.raises(ValueError, match="deans_office"):
        get_leadership()
