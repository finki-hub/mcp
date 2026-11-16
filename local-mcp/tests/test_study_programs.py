import json
from pathlib import Path

import pytest

from app.schemas.course import AccreditationYear, StudyProgram
from app.schemas.study_program import StudyCycle
from app.tools import study_program as study_program_tools
from app.tools.study_program import list_study_programs

# A slice of Directus `degree_programs`, as `get_degree_programs` returns it.
DEGREE_PROGRAMS = json.loads(
    (Path(__file__).parent / "data" / "degree_programs.json").read_text(
        encoding="utf-8",
    ),
)


@pytest.fixture(autouse=True)
def _data(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        study_program_tools,
        "get_degree_programs",
        lambda: DEGREE_PROGRAMS,
    )


def test_only_seis_is_marked_as_taught_in_english() -> None:
    languages = {p.code: p.language for p in list_study_programs()}

    assert {code for code, language in languages.items() if language} == {
        "SEIS23",
        "SEIS23_3",
        "SEIS18",
    }
    assert {languages[code] for code in ("SEIS23", "SEIS23_3", "SEIS18")} == {
        "англиски",
    }


def test_every_course_program_code_has_a_first_cycle_program() -> None:
    abbreviations = {
        p.abbreviation for p in list_study_programs(cycle=StudyCycle.FIRST)
    }

    assert set(StudyProgram) <= abbreviations


def test_cycle_and_accreditation_filters() -> None:
    programs = list_study_programs(
        cycle=StudyCycle.FIRST,
        accreditation=AccreditationYear.Y2023,
    )

    assert programs
    assert all(p.cycle == StudyCycle.FIRST for p in programs)
    assert all(p.accreditation == "2023" for p in programs)
    assert {p.duration_years for p in programs} == {2, 3, 4}
    assert {p.code for p in list_study_programs(cycle=StudyCycle.THIRD)} == {
        "ID",
        "KNID",
    }


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("seis", {"SEIS23", "SEIS23_3", "SEIS18"}),
        ("СИИС", {"SIIS23", "SIIS23_3", "SIIS18"}),
        ("биоинформатика", {"BI23_1", "BI23_2"}),
        ("bioinformatika", {"BI23_1", "BI23_2"}),
        ("Cloud Computing", {"CC23_1", "CC23_2"}),
    ],
)
def test_query_matches_code_abbreviation_and_names(
    query: str,
    expected: set[str],
) -> None:
    assert {p.code for p in list_study_programs(query=query)} == expected


def test_a_program_without_a_curriculum_column_has_no_abbreviation() -> None:
    (pet,) = list_study_programs(query="PET18")

    assert pet.abbreviation is None


def test_degree_title_credits_and_coordinator() -> None:
    (kn,) = list_study_programs(query="KN23_3")
    (bkk,) = list_study_programs(query="BKK23_2")

    assert kn.name_en == "Computer Science"
    assert kn.url == "https://finki.ukim.mk/program/KN23_3"
    assert kn.title_en == "Bachelor of Science in Computer Science"
    assert kn.ects == 180
    assert kn.coordinator is None
    assert bkk.coordinator == "Весна Димитрова"
    assert bkk.ects == 120


def test_description_and_rules_only_with_details() -> None:
    (brief,) = list_study_programs(query="KN23_3")
    (full,) = list_study_programs(query="KN23_3", details=True)

    assert brief.description is None
    assert brief.rules is None
    assert full.description
    assert full.rules
    assert full.rules.startswith("Во наставната програма")


def test_details_are_left_out_of_a_broad_list() -> None:
    programs = list_study_programs(cycle=StudyCycle.FIRST, details=True)

    assert len(programs) > study_program_tools.MAX_DETAILED_PROGRAMS
    assert all(p.description is None and p.rules is None for p in programs)
