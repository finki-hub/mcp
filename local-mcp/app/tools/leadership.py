from app.schemas.leadership import (
    FacultyUnit,
    Leadership,
    LeadershipBody,
    LeadershipMember,
)
from app.tools import faculty
from app.utils.http_client import get_directus_items

# The Directus collection of each body and the fields of its members.
_QUERIES: dict[LeadershipBody, tuple[str, str]] = {
    LeadershipBody.DEANS_OFFICE: (
        "deans_office",
        "id,year,position,staff.name,staff.title,staff.position",
    ),
    LeadershipBody.STUDENT_COUNCIL: (
        "student_council",
        "id,year,position,student.name",
    ),
}

# The dean first, then the vice deans; the council's president first.
_LEADS = ("Декан", "Претседател")


def _member(body: LeadershipBody, row: dict) -> LeadershipMember | None:
    person = row.get("staff" if body is LeadershipBody.DEANS_OFFICE else "student")
    if not isinstance(person, dict) or not person.get("name"):
        return None
    staff = body is LeadershipBody.DEANS_OFFICE
    return LeadershipMember(
        position=row.get("position") or "",
        name=person["name"],
        title=person.get("title") if staff else None,
        staff_position=person.get("position") if staff else None,
    )


def _staff_member(
    person: object, position: str | None = None
) -> LeadershipMember | None:
    if not isinstance(person, dict) or not person.get("name"):
        return None
    return LeadershipMember(
        position=position or None,
        name=person["name"],
        title=person.get("title") or None,
        staff_position=person.get("position") or None,
    )


# The bodies FINKI lists on its site today, from the faculty import; they
# have no recorded terms, so `year` does not apply.
_FACULTY_BODIES = {
    LeadershipBody.MANAGEMENT_BOARD: "management_board",
    LeadershipBody.COUNCIL: "council",
}


def _current_body(body: LeadershipBody) -> Leadership:
    members = [
        member
        for row in faculty.body_members(_FACULTY_BODIES[body])
        if (member := _staff_member(row.get("staff"), row.get("position"))) is not None
    ]
    return Leadership(body=body, members=members)


def _unit(row: dict, *, with_members: bool) -> FacultyUnit:
    names = [
        member["staff"]["name"]
        for member in row.get("members") or []
        if isinstance(member.get("staff"), dict) and member["staff"].get("name")
    ]
    return FacultyUnit(
        name=row["name"],
        page=row.get("page") or None,
        head=_staff_member(row.get("head")),
        members=sorted(names) if with_members else None,
    )


def get_leadership(
    body: LeadershipBody = LeadershipBody.DEANS_OFFICE,
    year: int | None = None,
) -> Leadership:
    """
    The dean's office or the student council of one term: the latest one, or
    the one in office in `year` (the latest that started in it or before;
    the earliest when `year` precedes them all). The management board, the
    council (ННС), the institutes and the centers are the current ones.
    """
    if body in _FACULTY_BODIES:
        return _current_body(body)
    if body is LeadershipBody.INSTITUTES:
        units = [_unit(row, with_members=True) for row in faculty.institutes()]
        return Leadership(body=body, units=units)
    if body is LeadershipBody.CENTERS:
        units = [_unit(row, with_members=False) for row in faculty.centers()]
        return Leadership(body=body, units=units)

    collection, fields = _QUERIES[body]
    rows = get_directus_items(
        collection,
        {"fields": fields, "limit": -1, "sort": "-year,id"},
    )
    years = sorted({row["year"] for row in rows if row.get("year")}, reverse=True)
    if not years:
        raise ValueError(f"No {collection} members are recorded")
    chosen = (
        years[0] if year is None else next((y for y in years if y <= year), years[-1])
    )
    members = [
        member
        for row in rows
        if row.get("year") == chosen and (member := _member(body, row)) is not None
    ]
    members.sort(key=lambda member: member.position not in _LEADS)
    return Leadership(body=body, year=chosen, members=members, years=years)
