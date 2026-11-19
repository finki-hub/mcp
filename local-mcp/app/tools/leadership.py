from app.schemas.leadership import Leadership, LeadershipBody, LeadershipMember
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


def get_leadership(
    body: LeadershipBody = LeadershipBody.DEANS_OFFICE,
    year: int | None = None,
) -> Leadership:
    """
    The dean's office or the student council of one term: the latest one, or
    the one in office in `year` (the latest that started in it or before;
    the earliest when `year` precedes them all).
    """
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
