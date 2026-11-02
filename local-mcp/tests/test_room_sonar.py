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
    assert [match.name for match in room.list_rooms().items] == [
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
        ).items
    ] == ["first"]
    assert room.list_rooms(min_capacity=41).items == []
    assert [match.name for match in room.list_rooms(min_capacity=0).items] == [
        "first",
        "third",
    ]
    assert [match.name for match in room.list_rooms(floor=" ").items] == [
        "third",
        "empty",
    ]
    assert [match.name for match in room.list_rooms(type=RoomType.CABINET).items] == [
        "third"
    ]
    assert [
        match.name for match in room.list_rooms(location=RoomLocation.FEIT).items
    ] == ["third"]
    monkeypatch.setattr(room, "get_rooms", list)
    assert room.list_rooms().items == []


_PREFIX_ROOMS = [
    {"name": "12", "type": "Лабораторија", "location": "ТМФ", "floor": "-1"},
    {"name": "13", "type": "Лабораторија", "location": "ТМФ", "floor": "-1"},
    {"name": "114", "type": "Кабинет", "location": "ТМФ", "floor": "1"},
    {"name": "114", "type": "Предавална", "location": "ТМФ", "floor": "1"},
    {"name": "М3", "type": "Кабинет", "location": "Анекс на МФ", "floor": "1"},
    {"name": "Голем Амфитеатар", "type": "Амфитеатар", "location": "ФИНКИ"},
]


@pytest.mark.parametrize(
    "query",
    ["Лаб 12", "лаб. 12", "Lab 12", "lab12", "лабораторија 12", "laboratorija 12"],
)
def test_room_data_strips_type_word(
    monkeypatch: pytest.MonkeyPatch,
    query: str,
) -> None:
    monkeypatch.setattr(room, "get_rooms", lambda: _PREFIX_ROOMS)
    data = room.get_room_data(query)
    assert data.error is None
    assert [r.name for r in data.rooms or []] == ["12"]


def test_room_data_type_word_picks_between_same_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(room, "get_rooms", lambda: _PREFIX_ROOMS)
    assert [r.type for r in room.get_room_data("114").rooms or []] == [
        "Кабинет",
        "Предавална",
    ]
    assert [r.type for r in room.get_room_data("кабинет 114").rooms or []] == [
        "Кабинет",
    ]
    # A type word that doesn't fit the data still finds the room.
    assert [r.name for r in room.get_room_data("лаб М3").rooms or []] == ["М3"]


def test_room_data_type_word_beats_fuzzy_full_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rooms = [
        {"name": "СОЦД", "type": "Лабораторија", "location": "ТМФ"},
        {"name": "СОЦД", "type": "Кабинет", "location": "ТМФ"},
    ]
    monkeypatch.setattr(room, "get_rooms", lambda: rooms)
    assert [r.type for r in room.get_room_data("кабинет СОЦД").rooms or []] == [
        "Кабинет",
    ]


def test_room_data_type_word_keeps_full_names_and_misses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(room, "get_rooms", lambda: _PREFIX_ROOMS)
    assert [r.name for r in room.get_room_data("Голем Амфитеатар").rooms or []] == [
        "Голем Амфитеатар",
    ]
    missing = room.get_room_data("Лаб 99")
    assert missing.rooms is None
    assert missing.error is not None


def test_list_rooms_query_strips_type_word(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(room, "get_rooms", lambda: _PREFIX_ROOMS)
    assert [r.name for r in room.list_rooms(query="Лаб 13").items] == ["13"]
    assert [(r.name, r.type) for r in room.list_rooms(query="кабинет 114").items] == [
        ("114", "Кабинет"),
    ]
