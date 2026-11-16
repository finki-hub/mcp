import pytest

from app.tools import course as course_tools
from app.tools import directus_lookup
from app.tools.course import list_courses
from app.tools.directus_lookup import find_course
from app.utils.abbreviation_matcher import (
    build_abbreviation_index,
    resolve_abbreviation,
)

_COURSES = [
    {"name": "Алгоритми и податочни структури", "abbreviation": "АПС"},
    {"name": "Примена на алгоритми и податочни структури", "abbreviation": "ПАПС"},
    {"name": "Бази на податоци", "abbreviation": "БнП"},
    {"name": "Администрација на бази податоци", "abbreviation": "АнБП"},
    {
        "name": "Адаптивни и интерактивни веб информациски системи",
        "abbreviation": "АиИВИС",
    },
    {"name": "Компјутерски мрежи и безбедност", "abbreviation": "КМиБ"},
    {"name": "Софтверски квалитет и тестирање", "abbreviation": "СКиТ"},
    {"name": "Вовед во науката за податоци", "abbreviation": "ВНП"},
    {"name": "Објектно-ориентирано програмирање", "abbreviation": "ООП"},
    {"name": "Веб програмирање", "abbreviation": "ВебП"},
    {"name": "Напредно програмирање", "abbreviation": "НП"},
    {"name": "Самостоен проект", "abbreviation": "СП"},
    {"name": "Структурно програмирање", "abbreviation": "СП"},
    {"name": "Компјутерска анимација", "abbreviation": "КА"},
    {"name": "Компјутерски архитектури", "abbreviation": "КА"},
    {"name": "Интегрирани системи", "abbreviation": "ИС"},
    {"name": "Интелигентни системи", "abbreviation": "ИнС"},
    {"name": "Шаблони за дизајн на кориснички интерфејси", "abbreviation": "ШДКИ"},
    {"name": "Web3 апликации", "abbreviation": "Web3"},
    {"name": "Физика", "abbreviation": "Физика"},
]


_DIRECTUS_COURSES = [
    {"id": index, "name_en": None, **course} for index, course in enumerate(_COURSES)
]


@pytest.fixture(autouse=True)
def _courses(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(course_tools, "get_courses", lambda: _COURSES)
    monkeypatch.setattr(
        directus_lookup,
        "get_directus_items",
        lambda _collection, _params: _DIRECTUS_COURSES,
    )


def _resolve(query: str) -> list[str]:
    return resolve_abbreviation(query, build_abbreviation_index(_COURSES))


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("АПС", "Алгоритми и податочни структури"),
        ("апс", "Алгоритми и податочни структури"),
        ("ПАПС", "Примена на алгоритми и податочни структури"),
        ("paps", "Примена на алгоритми и податочни структури"),
        ("KMIB", "Компјутерски мрежи и безбедност"),
        ("kmib", "Компјутерски мрежи и безбедност"),
        ("skit", "Софтверски квалитет и тестирање"),
        ("БП", "Бази на податоци"),
        ("bp", "Бази на податоци"),
        ("БнП", "Бази на податоци"),
        ("АиПС", "Алгоритми и податочни структури"),
        ("AiPS", "Алгоритми и податочни структури"),
        ("АИВИС", "Адаптивни и интерактивни веб информациски системи"),
        ("А.П.С.", "Алгоритми и податочни структури"),
        ("в н п", "Вовед во науката за податоци"),
        ("shdki", "Шаблони за дизајн на кориснички интерфејси"),
        ("web3", "Web3 апликации"),
        ("ИС", "Интегрирани системи"),
    ],
)
def test_resolves_abbreviation(query: str, expected: str) -> None:
    assert _resolve(query) == [expected]


def test_shared_abbreviation_returns_all_courses() -> None:
    assert _resolve("СП") == ["Самостоен проект", "Структурно програмирање"]
    assert _resolve("sp") == ["Самостоен проект", "Структурно програмирање"]


def test_unknown_abbreviation_and_names_do_not_match() -> None:
    assert _resolve("ЏЏЏ") == []
    assert _resolve("Бази на податоци") == []
    assert _resolve("Структурно Програмирање") == []


def test_course_by_its_abbreviation() -> None:
    found = find_course("ПАПС")

    assert found.record is not None
    assert found.record["name"] == "Примена на алгоритми и податочни структури"


def test_derived_abbreviation() -> None:
    found = find_course("БП")

    assert found.record is not None
    assert found.record["name"] == "Бази на податоци"


def test_shared_abbreviation_returns_suggestions() -> None:
    found = find_course("СП")

    assert found.record is None
    assert found.error == "Повеќе предмети одговараат на „СП“"
    assert found.suggestions == ["Самостоен проект", "Структурно програмирање"]


def test_unknown_short_and_long_queries() -> None:
    short = find_course("ЏЏ")
    assert short.error is not None
    assert short.error.startswith("Барањето „ЏЏ“ е прекратко")

    assert find_course("ЏЏЏЏ").record is None


def test_full_name_matches_in_any_case_and_script() -> None:
    for query, name in (
        ("Бази на податоци", "Бази на податоци"),
        ("Структурно Програмирање", "Структурно програмирање"),
        ("veb programiranje", "Веб програмирање"),
    ):
        found = find_course(query)
        assert found.record is not None
        assert found.record["name"] == name


def test_list_courses_includes_abbreviation() -> None:
    by_name = {match.name: match.abbreviation for match in list_courses().items}
    assert by_name["Бази на податоци"] == "БнП"
