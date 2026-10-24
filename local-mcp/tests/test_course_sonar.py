import pytest

from app.schemas.course import AccreditationYear, CourseStatus, CourseTag, StudyProgram
from app.tools import course as tools
from app.tools.course import _build_course


@pytest.fixture
def records(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    data = [
        {
            "name": "First course",
            "tags": "AI,WEB",
            "professors": "Alice\nBob\nAlice",
            "assistants": "Carol",
            "2023-available": "TRUE",
            "2023-semester": "2",
            "2023-state-kn": "задолжителен (3 г.)",
            "2018-available": "FALSE",
            "2018-semester": "2",
            "2018-state-kn": "изборен",
        },
        {"name": "Second course", "tags": "AI", "professors": "Bob"},
    ]
    monkeypatch.setattr(tools, "get_courses", lambda: data)
    return data


def test_unscoped_empty_filters(records: list[dict]) -> None:
    matches = tools.list_courses(tags=[], professors=[], assistants=[]).items
    assert [m.name for m in matches] == [r["name"] for r in records]
    assert matches[0].tags == ["AI", "веб"]
    assert all(m.accreditations is None and m.professors is None for m in matches)


def test_accreditation_scope_without_reporting(records: list[dict]) -> None:
    matches = tools.list_courses(accreditation=AccreditationYear.Y2023).items
    assert [m.name for m in matches] == [records[0]["name"]]
    assert matches[0].accreditations is None
    assert tools.list_courses(accreditation=AccreditationYear.Y2018).items == []


def test_filters_share_available_accreditation(records: list[dict]) -> None:
    assert tools.list_courses(status=CourseStatus.ELECTIVE, semester=2).items == []
    (match,) = tools.list_courses(
        program=StudyProgram.KN, status=CourseStatus.MANDATORY, semester=2
    ).items
    assert match.name == records[0]["name"]
    assert match.accreditations is not None
    assert match.accreditations["2023"].offered_in == {"КН": "задолжителен (3 г.)"}
    assert match.accreditations["2023"].semester is None
    assert tools.list_courses(program=StudyProgram.KI).items == []


def test_staff_group_queries(
    records: list[dict], monkeypatch: pytest.MonkeyPatch
) -> None:
    groups = {"either": ["Alice", "Bob"], "alice": ["Alice"], "carol": ["Carol"]}
    monkeypatch.setattr(
        tools, "match_query_to_group", lambda name, pool: groups.get(name)
    )
    (match,) = tools.list_courses(
        professors=["either", "alice"], assistants=["carol"], tags=[CourseTag.WEB]
    ).items
    assert match.name == records[0]["name"]
    assert match.professors == ["Alice", "Bob", "Alice"]
    assert match.assistants == ["Carol"]
    assert tools.list_courses(professors=["missing"]).items == []
    assert tools.list_courses(assistants=["missing"]).items == []


def test_record_parsing() -> None:
    course = _build_course(
        {
            "name": "Example",
            "professors": "(неактивиран предмет)",
            "2024/2025": "bad",
            "2022/2023": "17",
            "2030-channel": "TRUE",
            "2023-available": "true",
            "2023-credits": "bad",
            "2023-level": "2",
            "2023-prerequisite": "",
            "2023-code": "CODE",
            "2023-name": "Renamed",
            "2023-state-unknown": "изборен",
            "2023-state-kn": "нема",
            "2023-state-ki": "",
            "unrelated": "ignored",
        }
    )
    assert course.staff.inactive
    assert course.staff.professors == []
    assert course.participants == {"2024/2025": 0, "2022/2023": 17}
    assert not course.accreditations["2030"].available
    acc = course.accreditations["2023"]
    assert acc.available
    assert acc.credits == 0
    assert acc.level == 2
    assert acc.prerequisite is None
    assert acc.offered_in is None
    assert acc.code == "CODE"
    assert acc.name == "Renamed"


def test_blank_short_queries(records: list[dict]) -> None:
    assert records
    assert tools.get_course_data("  ").error == "Внесете име на предметот."
    assert (
        tools.get_course_data("x").error
        == "Барањето е прекратко; внесете барем 3 знаци."
    )
