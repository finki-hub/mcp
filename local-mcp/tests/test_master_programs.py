import json
from pathlib import Path

import pytest

from app.schemas.course_details import CourseInclude
from app.tools import course_details, directus_lookup, study_program
from app.tools.course_details import get_course
from app.tools.directus_lookup import find_course
from app.tools.study_program import list_study_programs

_COURSES = [
    {
        "id": 154,
        "name": "Работа со надарени ученици",
        "name_en": None,
        "abbreviation": None,
        "degree_cycle": "first",
    },
    {
        "id": 301,
        "name": "Работа со надарени ученици",
        "name_en": None,
        "abbreviation": None,
        "degree_cycle": "second",
    },
    {
        "id": 400,
        "name": "Применета криптографија",
        "name_en": "Applied Cryptography",
        "abbreviation": None,
        "degree_cycle": "second",
    },
]
_COURSE_400 = {
    "id": 400,
    "name": "Применета криптографија",
    "degree_cycle": "second",
    "degree_programs": [
        {
            "program": {"code": "SI23_2"},
            "kind": "elective",
            "semester": 3,
            "group": "faculty_winter",
            "code": "DCS-Z-01",
        },
        {
            "program": {"code": "BKK23_2"},
            "kind": "mandatory",
            "semester": 3,
            "group": None,
            "code": "DCS-Z-01",
        },
    ],
}
_PROGRAM_ROWS = [
    {
        "code": "DCS-Z-01",
        "kind": "mandatory",
        "semester": 3,
        "group": None,
        "course": {"name": "Применета криптографија"},
    },
    {
        "code": "F23L3W043",
        "kind": "mandatory",
        "semester": 1,
        "group": None,
        "course": {"name": "Информациска безбедност"},
    },
    {
        "code": "DCS-I-05",
        "kind": "elective",
        "semester": 3,
        "group": "named",
        "course": {"name": "Теорија на кодирање и примени"},
    },
    {
        "code": "DS003",
        "kind": "elective",
        "semester": 3,
        "group": "faculty_winter",
        "course": {"name": "Data Engineering"},
    },
]
_SLOTS = [
    {"semester": 1, "kind": "program_or_faculty", "count": 1},
    {"semester": 3, "kind": "program", "count": 2},
]
_DEGREE_PROGRAMS = json.loads(
    (Path(__file__).parent / "data" / "degree_programs.json").read_text(
        encoding="utf-8"
    ),
)


def _items(collection: str, params: dict[str, str | int]) -> list[dict]:
    if collection == "courses":
        return [_COURSE_400] if params.get("filter[id][_eq]") == 400 else _COURSES
    if collection == "degree_program_courses":
        return (
            _PROGRAM_ROWS if params["filter[program][code][_eq]"] == "BKK23_2" else []
        )
    if collection == "degree_program_slots":
        return _SLOTS
    raise AssertionError(collection)


@pytest.fixture(autouse=True)
def _data(monkeypatch: pytest.MonkeyPatch) -> None:
    for module in (course_details, directus_lookup, study_program):
        monkeypatch.setattr(module, "get_directus_items", _items)
    monkeypatch.setattr(study_program, "get_degree_programs", lambda: _DEGREE_PROGRAMS)


def test_same_named_courses_are_told_apart_by_cycle() -> None:
    both = find_course("Работа со надарени ученици")

    assert both.record is None
    assert both.suggestions == [
        "Работа со надарени ученици (прв циклус)",
        "Работа со надарени ученици (втор циклус)",
    ]
    master = find_course("Работа со надарени ученици (втор циклус)")
    assert master.record is not None
    assert master.record["id"] == 301


def test_a_course_lists_its_programs_mandatory_first() -> None:
    course = get_course("Applied Cryptography", [CourseInclude.PROGRAMS])

    assert course.cycle == "second"
    assert [(p.program, p.kind, p.group) for p in course.programs or []] == [
        ("BKK23_2", "mandatory", None),
        ("SI23_2", "elective", "faculty_winter"),
    ]


def test_a_masters_program_layout_with_details() -> None:
    (program,) = list_study_programs(query="BKK23_2", details=True)

    assert program.curriculum is not None
    assert [
        (s.semester, s.mandatory, s.electives) for s in program.curriculum.semesters
    ] == [
        (1, ["F23L3W043 Информациска безбедност"], ["1 од програмата или факултетот"]),
        (3, ["DCS-Z-01 Применета криптографија"], ["2 од програмата"]),
    ]
    assert [e.course for e in program.curriculum.program_electives or []] == [
        "DCS-I-05 Теорија на кодирање и примени",
    ]
    faculty = program.curriculum.faculty_electives or []
    assert [(e.course, e.term) for e in faculty] == [
        ("DS003 Data Engineering", "зимски")
    ]
    assert program.curriculum.faculty_elective_count == 1


def test_an_undergraduate_program_has_no_layout() -> None:
    (program,) = list_study_programs(query="KN23_3", details=True)

    assert program.curriculum is None
