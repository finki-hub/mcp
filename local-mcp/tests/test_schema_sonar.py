import pytest
from pydantic import BaseModel

from app.schemas.course import (
    Accreditation,
    AccreditationMatch,
    Course,
    CourseMatch,
    CourseParticipants,
    CourseStaff,
    CourseStatus,
)
from app.schemas.room import Room, RoomData, RoomLocation, RoomMatch, RoomType
from app.schemas.staff import StaffMatch, StaffMember, StaffPosition, StaffProfile


@pytest.mark.parametrize("model", [Room, RoomMatch, RoomData])
def test_room_name_description(model: type[BaseModel]) -> None:
    assert (
        model.model_json_schema()["properties"]["name"]["description"]
        == "Име на просторијата"
    )


@pytest.mark.parametrize("model", [Room, RoomMatch])
def test_room_examples(model: type[BaseModel]) -> None:
    properties = model.model_json_schema()["properties"]
    assert properties["type"]["examples"] == ["Кабинет"]
    assert properties["location"]["examples"] == ["Анекс на ФЕИТ"]


def test_room_data_examples() -> None:
    properties = RoomData.model_json_schema()["properties"]
    assert properties["name"]["examples"] == ["Амфитеатар"]
    assert properties["suggestions"]["examples"] == [
        ["Амфитеатар", "Мал Амфитеатар", "Голем Амфитеатар"],
    ]


@pytest.mark.parametrize("model", [StaffMatch, StaffProfile])
def test_staff_position_examples(model: type[BaseModel]) -> None:
    assert model.model_json_schema()["properties"]["position"]["examples"] == ["Доцент"]


@pytest.mark.parametrize("model", [StaffMatch, StaffMember])
def test_staff_name_examples(model: type[BaseModel]) -> None:
    assert model.model_json_schema()["properties"]["name"]["examples"] == [
        "Александар Стојменски"
    ]


def test_staff_member_lookup_examples() -> None:
    properties = StaffMember.model_json_schema()["properties"]
    assert properties["suggestions"]["examples"] == [
        ["Александар Стојменски", "Александар Тенев"],
    ]
    assert (
        properties["match_info"]["examples"][0]["matched_staff"]
        == "Александар Стојменски"
    )


@pytest.mark.parametrize(
    "model",
    [Accreditation, Course, CourseStaff, CourseParticipants, CourseMatch],
)
def test_course_name_description(model: type[BaseModel]) -> None:
    assert (
        model.model_json_schema()["properties"]["name"]["description"]
        == "Име на предметот"
    )


def test_course_status_examples() -> None:
    assert Accreditation.model_json_schema()["properties"]["offered_in"][
        "examples"
    ] == [
        {"КН": "задолжителен", "СИИС": "изборен"},
    ]
    assert AccreditationMatch.model_json_schema()["properties"]["offered_in"][
        "examples"
    ] == [
        {"КН": "изборен"},
    ]


def test_enum_values_unchanged() -> None:
    assert RoomType("Амфитеатар") is RoomType.AMPHITHEATER
    assert RoomType("Кабинет") is RoomType.CABINET
    assert RoomLocation("Анекс на ФЕИТ") is RoomLocation.FEIT_ANNEX
    assert StaffPosition("Доцент") is StaffPosition.DOCENT
    assert CourseStatus("изборен") is CourseStatus.ELECTIVE
