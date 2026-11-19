import pytest

from app.tools import prerequisites as prerequisite_tools
from app.tools.prerequisites import courses_unlocked_by, named_courses

_NAMES = [
    "Компјутерски мрежи",
    "Компјутерски мрежи и безбедност",
    "Оперативни системи",
    "Бази на податоци",
    "Напредни бази на податоци",
    "Веројатност и статистика",
]


def _entry(
    name: str, prerequisites: str | None, code: str = "2023", *, published: bool = True
) -> dict:
    return {
        "name": name,
        "prerequisites": prerequisites,
        "generation": {"code": code, "published": published},
        "course_links": [{"course": {"name": name}}],
    }


def test_names_with_and_inside_are_matched_whole() -> None:
    found = named_courses(
        "Оперативни системи и (Компјутерски мрежи или Компјутерски мрежи и безбедност)",
        _NAMES,
    )

    assert found == {
        "оперативни системи",
        "компјутерски мрежи",
        "компјутерски мрежи и безбедност",
    }


def test_a_longer_name_does_not_count_as_its_prefix() -> None:
    assert named_courses("Компјутерски мрежи и безбедност", _NAMES) == {
        "компјутерски мрежи и безбедност",
    }
    assert named_courses("Напредни бази на податоци", _NAMES) == {
        "напредни бази на податоци",
    }


def test_case_and_spacing_do_not_matter() -> None:
    assert named_courses("компјутерски  мрежи или Бази на податоци", _NAMES) == {
        "компјутерски мрежи",
        "бази на податоци",
    }


def test_unlocked_courses_newest_accreditation_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entries = [
        _entry("Компјутерски мрежи", None),
        _entry("Компјутерски мрежи и безбедност", None),
        _entry("Бази на податоци", None),
        _entry(
            "Дистрибуирани системи",
            "Оперативни системи и (Компјутерски мрежи или Компјутерски мрежи и безбедност)",
        ),
        _entry("Етичко хакирање", "Компјутерски мрежи и безбедност"),
        _entry("Дизајн на компјутерски мрежи", "Компјутерски мрежи", "2018"),
        _entry("Скриен предмет", "Компјутерски мрежи", "2026", published=False),
        _entry("Напредни бази на податоци", "Бази на податоци"),
    ]
    monkeypatch.setattr(prerequisite_tools, "get_directus_items", lambda *_: entries)

    unlocked = courses_unlocked_by(["Компјутерски мрежи"])

    assert [(row.accreditation, row.course) for row in unlocked] == [
        ("2023", "Дистрибуирани системи"),
        ("2018", "Дизајн на компјутерски мрежи"),
    ]
    assert unlocked[0].prerequisites.startswith("Оперативни системи и")
