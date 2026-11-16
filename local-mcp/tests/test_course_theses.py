import anyio
import pytest
from mcp.types import CallToolResult

from app.main import app
from app.schemas.course_details import CourseInclude
from app.schemas.thesis_search import ThesisKind, ThesisRole
from app.tools import course_details, directus_lookup, schedule, thesis_search
from app.tools.course_details import get_course
from app.tools.thesis_search import find_theses

_STAFF = [
    {"id": 24, "name": "Весна Димитрова"},
    {"id": 97, "name": "Ристе Стојанов"},
]
_COURSES = [
    {
        "id": 9,
        "name": "Алгоритми и податочни структури",
        "name_en": "Algorithms and Data Structures",
        "abbreviation": "АПС",
    },
]


def _state(program: str, state: str) -> dict:
    return {"state": state, "program": {"name": program}}


_COURSE = {
    "id": 9,
    "name": "Алгоритми и податочни структури",
    "name_en": "Algorithms and Data Structures",
    "abbreviation": "АПС",
    "status": "active",
    "tags": "coding",
    "objectives": "Цели.",
    "content": "Предавања:\n1. Вовед.",
    "objectives_en": None,
    "content_en": "",
    "curricula": [
        {
            "credits": 6,
            "available": True,
            "generation": {"code": "2018", "published": True},
            "entry": {
                "name": "Алгоритми и податочни структури",
                "code": "F18L2W001",
                "semester": 3,
                "prerequisites": "Објектно-ориентирано програмирање",
                "program_states": [_state("КН", "задолжителен"), _state("ПИТ", "нема")],
            },
        },
        {
            "credits": 6,
            "available": True,
            "generation": {"code": "2023", "published": True},
            "entry": {
                "name": "Алгоритми и податочни структури",
                "code": "F23L2W001",
                "semester": 3,
                "prerequisites": "",
                "program_states": [_state("КН", "задолжителен")],
            },
        },
        {
            "credits": 6,
            "available": False,
            "generation": {"code": "2013", "published": False},
            "entry": {"name": "Алгоритми", "code": None},
        },
    ],
    "equivalencies": [
        {
            "members": [
                {
                    "label": "Алгоритми и податочни структури",
                    "generation": {"code": "2023"},
                },
                {"label": "Алгоритми", "generation": {"code": "2013"}},
            ],
        },
        {"members": [{"label": "Сам", "generation": {"code": "2023"}}]},
    ],
    "enrollments": [
        {"count": 877, "academic_year": {"label": "2025/2026"}},
        {"count": 0, "academic_year": {"label": "2015/2016"}},
        {"count": 468, "academic_year": {"label": "2026/2027"}},
    ],
}

_BACHELOR = [
    {
        "id": 1,
        "title": "Блокчејн и паметни договори",
        "student_index": "0201010",
        "student_name": "Ана Анова",
        "mentor": "Весна Димитрова",
        "year": 2025,
        "status": "Одбрана",
        "submitted": "2025-06-01",
    },
    {
        "id": 2,
        "title": "Веб апликација",
        "student_name": "Борис Боров",
        "mentor": "Ристе Стојанов",
        "year": 2026,
        "status": "Одбрана",
        "submitted": "2026-02-01",
    },
]
_MASTER = [
    {
        "id": 7,
        "title": "Криптографски хеш функции",
        "student_name": "Ристо Стојанов",
        "mentor": "Весна Димитрова",
        "year": 2026,
        "status": "Завршена",
        "presented": "2026-03-01",
    },
]


def _items(collection: str, params: dict[str, str | int]) -> list[dict]:
    if collection == "staff":
        return _STAFF
    if collection == "courses":
        return [_COURSE] if "filter[id][_eq]" in params else _COURSES
    if collection == "bachelor_thesis_staff":
        rows = {
            24: [{"thesis": 1, "role": "mentor"}, {"thesis": 2, "role": "member"}],
            97: [{"thesis": 2, "role": "mentor"}],
        }
        return rows[int(params["filter[staff][_eq]"])]
    if collection == "master_thesis_staff":
        return (
            [{"thesis": 7, "role": "mentor"}]
            if params["filter[staff][_eq]"] == 24
            else []
        )
    if collection == "course_teaching":
        summer = {"id": 3, "title": "leten-2025-26", "date_from": "2026-02-23"}
        winter = {"id": 5, "title": "zimski-2025-26", "date_from": "2025-10-04"}
        return [
            {
                "role": "assistant",
                "periods": 2,
                "staff": {"name": "Ана Тодоровска"},
                "timetable": summer,
            },
            {
                "role": "professor",
                "periods": 2,
                "staff": {"name": "Ристе Стојанов"},
                "timetable": summer,
            },
            {
                "role": "professor",
                "periods": 2,
                "staff": {"name": "Стар Наставник"},
                "timetable": winter,
            },
        ]
    return {
        "bachelor_theses": _BACHELOR,
        "master_theses": _MASTER,
        "timetables": [{"id": 1, "title": "raspored"}],
        "timetable_slots": [],
    }[collection]


@pytest.fixture(autouse=True)
def _data(monkeypatch: pytest.MonkeyPatch) -> None:
    for module in (course_details, directus_lookup, schedule, thesis_search):
        monkeypatch.setattr(module, "get_directus_items", _items)


def test_course_base_only_by_default() -> None:
    course = get_course("АПС")

    assert course.name == "Алгоритми и податочни структури"
    assert course.curricula is None
    assert course.syllabus is None


def test_course_curricula_newest_first_without_unpublished_or_not_offered() -> None:
    course = get_course("aps", [CourseInclude.CURRICULA])

    assert [c.accreditation for c in course.curricula or []] == ["2023", "2018"]
    assert (course.curricula or [])[1].programs == {"КН": "задолжителен"}
    assert (course.curricula or [])[0].prerequisites is None
    assert (course.curricula or [])[0].name is None


def test_course_syllabus_equivalencies_and_enrollments() -> None:
    course = get_course(
        "Алгоритми и податочни структури",
        [
            CourseInclude.SYLLABUS,
            CourseInclude.EQUIVALENCIES,
            CourseInclude.ENROLLMENTS,
        ],
    )

    assert course.syllabus is not None
    assert course.syllabus.objectives == "Цели."
    assert course.syllabus.content_en is None
    assert course.equivalencies == [
        ["Алгоритми (2013)", "Алгоритми и податочни структури (2023)"],
    ]
    assert course.enrollments == {"2026/2027": 468, "2025/2026": 877}


def test_course_teaching_comes_from_the_latest_timetable_it_is_in() -> None:
    course = get_course("АПС", [CourseInclude.TEACHING])

    assert course.teaching_timetable == "leten-2025-26"
    assert course.timetable is None
    assert [t.staff for t in course.teaching or []] == [
        "Ристе Стојанов",
        "Ана Тодоровска",
    ]


def test_course_not_found() -> None:
    course = get_course("Непостоечки предмет")

    assert course.error
    assert course.curricula is None


def test_theses_of_a_staff_member_across_kinds_newest_first() -> None:
    result = find_theses(staff="Весна Димитрова")

    assert result.staff == "Весна Димитрова"
    assert [(t.kind, t.title, t.role) for t in result.items or []] == [
        (ThesisKind.MASTER, "Криптографски хеш функции", ThesisRole.MENTOR),
        (ThesisKind.BACHELOR, "Веб апликација", ThesisRole.MEMBER),
        (ThesisKind.BACHELOR, "Блокчејн и паметни договори", ThesisRole.MENTOR),
    ]


def test_theses_by_role_kind_and_year() -> None:
    result = find_theses(
        staff="Весна Димитрова",
        role=ThesisRole.MENTOR,
        kind=ThesisKind.BACHELOR,
        year=2025,
    )

    assert [t.title for t in result.items or []] == ["Блокчејн и паметни договори"]


def test_theses_by_title_in_latin() -> None:
    result = find_theses(query="pametni dogovori")

    assert [t.title for t in result.items or []] == ["Блокчејн и паметни договори"]
    assert result.items is not None
    assert result.items[0].role is None


def test_theses_limit_reports_truncation() -> None:
    result = find_theses(year=2026, limit=1)

    assert result.total == 2
    assert result.truncated is True
    assert [t.title for t in result.items or []] == ["Криптографски хеш функции"]


def test_theses_by_student_index_or_name() -> None:
    by_index = find_theses(student="201010")
    by_name = find_theses(student="anova ana")

    assert [t.title for t in by_index.items or []] == ["Блокчејн и паметни договори"]
    assert (by_index.items or [])[0].student_index == "0201010"
    assert [t.title for t in by_name.items or []] == ["Блокчејн и паметни договори"]


def test_student_name_words_must_start_name_words() -> None:
    # "ов" is inside "Стојанов" and "Боров" but starts neither name word.
    assert [t.student for t in find_theses(student="ана").items or []] == ["Ана Анова"]
    assert [t.student for t in find_theses(student="бор").items or []] == [
        "Борис Боров"
    ]


def test_misspelt_student_name_falls_back_to_fuzzy() -> None:
    result = find_theses(student="Борис Боорв")

    assert [t.student for t in result.items or []] == ["Борис Боров"]


def test_theses_need_a_filter_and_role_needs_staff() -> None:
    assert find_theses().error
    assert find_theses(role=ThesisRole.MENTOR, year=2025).error


def test_latest_theses_of_one_kind() -> None:
    result = find_theses(kind=ThesisKind.BACHELOR, limit=1)

    assert result.total == 2
    assert [t.title for t in result.items or []] == ["Веб апликација"]


def test_president_searches_master_theses_only() -> None:
    result = find_theses(staff="Весна Димитрова", role=ThesisRole.PRESIDENT)

    assert result.error is None
    assert result.items == []
    assert find_theses(
        staff="Весна Димитрова",
        role=ThesisRole.PRESIDENT,
        kind=ThesisKind.BACHELOR,
    ).error


def test_a_thesis_without_a_date_sorts_by_its_year() -> None:
    _BACHELOR.append(
        {"id": 3, "title": "Без датум", "year": 2027, "status": "Пријава"},
    )
    try:
        result = find_theses(kind=ThesisKind.BACHELOR)
    finally:
        _BACHELOR.pop()

    assert (result.items or [])[0].title == "Без датум"


def test_get_course_tool_returns_structured_content() -> None:
    async def call() -> CallToolResult:
        result = await app.call_tool(
            "get_course",
            {"name": "АПС", "include": ["enrollments"]},
        )
        assert isinstance(result, CallToolResult)
        return result

    structured = anyio.run(call).structured_content

    assert structured is not None
    assert structured["enrollments"] == {"2026/2027": 468, "2025/2026": 877}
