import pytest

from app.schemas.course import CourseStatus, SemesterType, StudyProgram
from app.tools import course as course_tools
from app.tools.course import list_courses


def _course(
    name: str,
    abbreviation: str,
    semester: int,
    participants: dict[str, int],
    states: dict[str, str],
) -> dict:
    record: dict = {
        "name": name,
        "abbreviation": abbreviation,
        "2023-available": "TRUE",
        "2023-name": name,
        "2023-semester": str(semester),
    }
    record.update({year: str(count) for year, count in participants.items()})
    record.update({f"2023-state-{program}": state for program, state in states.items()})
    return record


_COURSES = [
    _course(
        "Бази на податоци",
        "БнП",
        5,
        {"2025/2026": 900, "2026/2027": 0},
        {"kn": "задолжителен", "siis": "задолжителен (4 г.)", "pit": "изборен"},
    ),
    _course(
        "Веб програмирање",
        "ВебП",
        5,
        {"2025/2026": 800, "2026/2027": 12},
        {"kn": "изборен", "siis": "задолжителен"},
    ),
    _course(
        "Напредно програмирање",
        "НП",
        4,
        {"2025/2026": 700, "2026/2027": 0},
        {"kn": "задолжителен", "ssp": "нема"},
    ),
    _course(
        "Вовед во паметни градови",
        "ВвПГ",
        7,
        {"2025/2026": 9, "2026/2027": 6},
        {"kn": "изборен", "ie": "изборен"},
    ),
]


@pytest.fixture(autouse=True)
def _courses(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(course_tools, "get_courses", lambda: _COURSES)


def _names(
    *,
    query: str | None = None,
    semester_type: SemesterType | None = None,
) -> list[str]:
    result = list_courses(query=query, semester_type=semester_type)
    return [match.name for match in result.items]


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("програмирање", ["Веб програмирање", "Напредно програмирање"]),
        ("programiranje", ["Веб програмирање", "Напредно програмирање"]),
        ("БП", ["Бази на податоци"]),
        ("np", ["Напредно програмирање"]),
        ("паметни", ["Вовед во паметни градови"]),
    ],
)
def test_query_matches_name_and_abbreviation(query: str, expected: list[str]) -> None:
    assert _names(query=query) == expected


def test_semester_type_selects_odd_or_even_semesters() -> None:
    assert _names(semester_type=SemesterType.WINTER) == [
        "Бази на податоци",
        "Веб програмирање",
        "Вовед во паметни градови",
    ]
    assert _names(semester_type=SemesterType.SUMMER) == ["Напредно програмирање"]


def test_participant_range_defaults_to_latest_year_with_data() -> None:
    result = list_courses(
        semester_type=SemesterType.WINTER,
        min_participants=5,
        max_participants=15,
    )

    assert result.participants_year == "2026/2027"
    assert [(m.name, m.participants) for m in result.items] == [
        ("Веб програмирање", 12),
        ("Вовед во паметни градови", 6),
    ]


def test_participant_range_for_explicit_year() -> None:
    result = list_courses(participants_year="2025/2026", max_participants=10)

    assert result.participants_year == "2025/2026"
    assert [(m.name, m.participants) for m in result.items] == [
        ("Вовед во паметни градови", 9),
    ]


def test_sort_by_participants() -> None:
    result = list_courses(participants_year="2025/2026", sort_by_participants=True)

    assert [m.participants for m in result.items] == [900, 800, 700, 9]


def test_participants_are_omitted_without_participant_filters() -> None:
    result = list_courses()

    assert result.participants_year is None
    assert all(match.participants is None for match in result.items)


def test_limit_truncates_with_note() -> None:
    result = list_courses(limit=2)

    assert result.total == 4
    assert result.truncated is True
    assert result.note is not None
    assert "`offset`=2" in result.note
    assert len(result.items) == 2

    rest = list_courses(limit=2, offset=2)
    assert rest.truncated is False
    assert rest.note is None
    assert [m.name for m in rest.items] == [
        "Напредно програмирање",
        "Вовед во паметни градови",
    ]


def test_status_without_program_lists_programs_compactly() -> None:
    (match, *_) = list_courses(status=CourseStatus.MANDATORY, query="бази").items

    assert match.accreditations is not None
    entry = match.accreditations["2023"]
    assert entry.programs == "КН, СИИС (4 г.)"
    assert entry.offered_in is None
    assert entry.semester == 5


def test_filtered_semester_is_not_repeated() -> None:
    (match, *_) = list_courses(program=StudyProgram.KN, semester=4).items

    assert match.name == "Напредно програмирање"
    assert match.accreditations is not None
    assert match.accreditations["2023"].semester is None
    assert match.accreditations["2023"].offered_in == {"КН": "задолжителен"}


def test_parsed_courses_are_reused_until_upstream_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    build = course_tools._build_course  # noqa: SLF001

    def counting_build(record: dict) -> object:
        calls.append(record["name"])
        return build(record)

    monkeypatch.setattr(course_tools, "_build_course", counting_build)
    monkeypatch.setattr(course_tools, "get_courses", lambda: list(_COURSES[:2]))
    list_courses()
    list_courses()
    assert len(calls) == 4  # a new list object per call means a new snapshot

    snapshot = list(_COURSES)
    monkeypatch.setattr(course_tools, "get_courses", lambda: snapshot)
    calls.clear()
    list_courses()
    list_courses(query="веб")
    assert len(calls) == len(_COURSES)
