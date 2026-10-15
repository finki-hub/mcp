import pytest

from app.tools import course as course_tools
from app.tools.course import get_course_data, get_course_staff, list_courses
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


@pytest.fixture(autouse=True)
def _courses(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(course_tools, "get_courses", lambda: _COURSES)


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


def test_course_data_by_abbreviation() -> None:
    result = get_course_data("ПАПС")
    assert result.name == "Примена на алгоритми и податочни структури"
    assert result.abbreviation == "ПАПС"
    assert result.error is None
    assert result.match_info == {
        "original_query": "ПАПС",
        "matched_course": "Примена на алгоритми и податочни структури",
        "similarity_score": 100,
        "match_type": "abbreviation",
    }


def test_short_abbreviation_bypasses_min_length() -> None:
    result = get_course_staff("БП")
    assert result.name == "Бази на податоци"
    assert result.abbreviation == "БнП"
    assert result.match_info is not None
    assert result.match_info["match_type"] == "abbreviation"


def test_ambiguous_abbreviation_returns_suggestions() -> None:
    result = get_course_data("СП")
    assert result.error == "Повеќе предмети одговараат на „СП“"
    assert result.suggestions == ["Самостоен проект", "Структурно програмирање"]
    assert result.match_info is None


def test_unknown_abbreviation_falls_back_to_existing_behavior() -> None:
    short = get_course_data("ЏЏ")
    assert short.error is not None
    assert short.error.startswith("Барањето е прекратко")

    missing = get_course_data("ЏЏЏЏ")
    assert missing.error == "Предметот „ЏЏЏЏ“ не е пронајден"


def test_full_name_still_matches() -> None:
    exact = get_course_data("Бази на податоци")
    assert exact.name == "Бази на податоци"
    assert exact.abbreviation == "БнП"
    assert exact.match_info is not None
    assert exact.match_info["match_type"] == "exact"

    capitalized = get_course_data("Структурно Програмирање")
    assert capitalized.name == "Структурно програмирање"
    assert capitalized.match_info is not None
    assert capitalized.match_info["match_type"] == "exact"

    latin = get_course_data("veb programiranje")
    assert latin.name == "Веб програмирање"


def test_list_courses_includes_abbreviation() -> None:
    by_name = {match.name: match.abbreviation for match in list_courses()}
    assert by_name["Бази на податоци"] == "БнП"
