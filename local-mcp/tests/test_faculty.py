import pytest

from app.schemas.leadership import LeadershipBody
from app.schemas.staff_details import StaffInclude
from app.tools import directus_lookup, faculty, staff_details
from app.tools.leadership import get_leadership
from app.tools.staff_details import get_staff

# Slices of the faculty structure collections, as `get_directus_items`
# returns them with the fields `app.tools.faculty` asks for.


def _person(staff_id: int, name: str) -> dict:
    return {
        "id": staff_id,
        "name": name,
        "title": "д-р",
        "position": "Редовен професор",
    }


_DIMITROVA = _person(24, "Весна Димитрова")
_LAMESKI = _person(95, "Петре Ламески")
_CORBEV = _person(53, "Иван Чорбев")

_INSTITUTES = [
    {
        "id": 9,
        "name": "Институт за теориски основи на информатика",
        "page": "https://finki.ukim.mk/institut-1/",
        "head": _DIMITROVA,
        "members": [
            {"staff": {"id": 24, "name": "Весна Димитрова"}},
            {"staff": {"id": 5, "name": "Александра Поповска Митровиќ"}},
            {"staff": None},
        ],
    },
    {
        "id": 10,
        "name": "Институт за софтверско инженерство",
        "page": None,
        "head": _CORBEV,
        "members": [{"staff": {"id": 53, "name": "Иван Чорбев"}}],
    },
]

_CENTERS = [
    {"id": 1, "name": "Центар за одржување", "page": None, "head": _CORBEV},
    {"id": 2, "name": "Центар без раководител", "page": None, "head": None},
]

_BODIES: dict[str, list[dict]] = {
    "management_board": [
        {"position": "Декан", "staff": _LAMESKI},
        {
            "position": "Раководител на институт за теориски основи на информатика",
            "staff": _DIMITROVA,
        },
    ],
    "council": [
        {"position": None, "staff": _DIMITROVA},
        {"position": None, "staff": _CORBEV},
        {"position": None, "staff": None},
    ],
}

_PROFILE = {
    "id": 24,
    "name": "Весна Димитрова",
    "active": True,
    "photo": "https://finki.ukim.mk/vesna.jpg",
    "bio": "Дипломирала на ПМФ.",
}


def _items(collection: str, params: dict[str, str | int]) -> list[dict]:
    if collection == "faculty_body_members":
        return _BODIES[str(params["filter[body][_eq]"])]
    if collection == "staff":
        return [_PROFILE]
    if collection == "institutes":
        return _INSTITUTES
    return _CENTERS


@pytest.fixture(autouse=True)
def _data(monkeypatch: pytest.MonkeyPatch) -> None:
    for module in (directus_lookup, faculty, staff_details):
        monkeypatch.setattr(module, "get_directus_items", _items)


def test_the_management_board_keeps_the_page_order() -> None:
    result = get_leadership(LeadershipBody.MANAGEMENT_BOARD)

    assert result.year is None
    assert result.years is None
    assert [(m.position, m.name) for m in result.members or []] == [
        ("Декан", "Петре Ламески"),
        (
            "Раководител на институт за теориски основи на информатика",
            "Весна Димитрова",
        ),
    ]
    assert result.members is not None
    assert result.members[0].title == "д-р"


def test_the_council_lists_its_members_without_positions() -> None:
    result = get_leadership(LeadershipBody.COUNCIL)

    assert [(m.position, m.name) for m in result.members or []] == [
        (None, "Весна Димитрова"),
        (None, "Иван Чорбев"),
    ]


def test_institutes_list_their_heads_and_members() -> None:
    result = get_leadership(LeadershipBody.INSTITUTES)

    assert result.members is None
    units = result.units or []
    assert [u.name for u in units] == [
        "Институт за теориски основи на информатика",
        "Институт за софтверско инженерство",
    ]
    assert units[0].head is not None
    assert units[0].head.name == "Весна Димитрова"
    assert units[0].members == ["Александра Поповска Митровиќ", "Весна Димитрова"]


def test_centers_list_their_heads_only() -> None:
    units = get_leadership(LeadershipBody.CENTERS).units or []

    assert [(u.name, u.head and u.head.name) for u in units] == [
        ("Центар за одржување", "Иван Чорбев"),
        ("Центар без раководител", None),
    ]
    assert all(u.members is None for u in units)


def test_staff_roles_name_an_institute_head_once() -> None:
    assert faculty.staff_roles(24) == [
        "Раководител на институт за теориски основи на информатика",
        "Член на Наставно-научниот совет (ННС)",
    ]
    assert faculty.staff_roles(53) == [
        "Раководител на институт за софтверско инженерство",
        "Раководител на центар за одржување",
        "Член на Наставно-научниот совет (ННС)",
    ]
    assert faculty.staff_roles(1) == []


def test_staff_institute_by_membership_or_headship() -> None:
    assert faculty.staff_institute(5) == "Институт за теориски основи на информатика"
    assert faculty.staff_institute(53) == "Институт за софтверско инженерство"
    assert faculty.staff_institute(95) is None


def test_get_staff_has_the_faculty_structure_and_bio_on_request() -> None:
    brief = get_staff("Весна Димитрова")

    assert brief.institute == "Институт за теориски основи на информатика"
    assert brief.roles is not None
    assert "Член на Наставно-научниот совет (ННС)" in brief.roles
    assert brief.staff is not None
    assert brief.staff.photo == "https://finki.ukim.mk/vesna.jpg"
    assert brief.bio is None

    assert get_staff("Весна Димитрова", [StaffInclude.BIO]).bio == "Дипломирала на ПМФ."
