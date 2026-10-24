import pytest

from app.schemas.course import StudyProgram
from app.tools import course as course_tools
from app.tools.course import list_courses

_THESIS = {
    "name": "Дипломска работа",
    "abbreviation": "ДР",
    "2023-available": "TRUE",
    "2023-semester": "8",
    "2023-state-kn": "задолжителен (3 г.)",
    "2023-state-ie": "задолжителен (сем. 8)",
    "2018-available": "TRUE",
    "2018-semester": "6",
    "2018-state-ke": "задолжителен (сем. 8)",
}


@pytest.fixture(autouse=True)
def _courses(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(course_tools, "get_courses", lambda: [_THESIS])


@pytest.mark.parametrize("program", [StudyProgram.KE, StudyProgram.IE])
def test_ke_and_ie_filters_match_the_renamed_program_in_both_accreditations(
    program: StudyProgram,
) -> None:
    (match,) = list_courses(program=program).items

    assert match.accreditations is not None
    assert match.accreditations["2023"].offered_in == {"ИЕ": "задолжителен (сем. 8)"}
    assert match.accreditations["2018"].offered_in == {"КЕ": "задолжителен (сем. 8)"}


def test_other_programs_do_not_alias() -> None:
    (match,) = list_courses(program=StudyProgram.KN).items

    assert match.accreditations is not None
    assert set(match.accreditations) == {"2023"}
