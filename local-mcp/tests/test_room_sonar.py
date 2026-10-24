import pytest

from app.schemas.room import RoomLocation, RoomType
from app.tools import room


def test_room_filters(monkeypatch: pytest.MonkeyPatch) -> None:
    records = [
        {
            "name": "first",
            "type": " Сала ",
            "location": " МФ ",
            "floor": " 1 ",
            "capacity": "40",
        },
        {
            "name": "second",
            "type": "Сала",
            "location": "МФ",
            "floor": "1",
            "capacity": "bad",
        },
        {
            "name": "third",
            "type": "Кабинет",
            "location": "ФЕИТ",
            "floor": None,
            "capacity": 0,
        },
        {"name": "empty"},
    ]
    monkeypatch.setattr(room, "get_rooms", lambda: records)
    assert [match.name for match in room.list_rooms()] == [
        "first",
        "second",
        "third",
        "empty",
    ]
    assert [
        match.name
        for match in room.list_rooms(
            type=RoomType.HALL,
            location=RoomLocation.MF,
            floor=" 1 ",
            min_capacity=40,
        )
    ] == ["first"]
    assert room.list_rooms(min_capacity=41) == []
    assert [match.name for match in room.list_rooms(min_capacity=0)] == [
        "first",
        "third",
    ]
    assert [match.name for match in room.list_rooms(floor=" ")] == ["third", "empty"]
    assert [match.name for match in room.list_rooms(type=RoomType.CABINET)] == ["third"]
    assert [match.name for match in room.list_rooms(location=RoomLocation.FEIT)] == [
        "third"
    ]
    monkeypatch.setattr(room, "get_rooms", list)
    assert room.list_rooms() == []
