import pytest

from app.schemas.course import AccreditationYear, StudyProgram
from app.schemas.study_program import StudyCycle
from app.tools.study_program import list_study_programs


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


def test_english_name_is_omitted_when_it_repeats_the_name() -> None:
    (seis,) = list_study_programs(query="SEIS23_3")
    (kn,) = list_study_programs(query="KN23_3")

    assert seis.name_en is None
    assert kn.name_en == "Computer Science"
    assert kn.url == "https://finki.ukim.mk/program/KN23_3"
