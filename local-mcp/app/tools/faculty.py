from app.utils.http_client import get_directus_items

# The faculty structure FINKI publishes, as the Directus import keeps it:
# the institutes and their members, the centers, and the members of the
# management board (деканатска управа) and the teaching and scientific
# council (ННС). Each read is the whole (small) collection, cached for an
# hour, so a lookup by staff member filters it here.


def _person(relation: str) -> str:
    """The fields of a related staff member: id, name, title and position."""
    return ",".join(
        f"{relation}.{field}" for field in ("id", "name", "title", "position")
    )


def institutes() -> list[dict]:
    """Each institute with its head and the staff of its members."""
    return get_directus_items(
        "institutes",
        {
            "fields": f"id,name,page,{_person('head')},members.staff.id,members.staff.name",
            "limit": -1,
            "sort": "id",
        },
    )


def centers() -> list[dict]:
    """Each center with its head, in the order the faculty lists them."""
    return get_directus_items(
        "faculty_centers",
        {
            "fields": f"id,name,page,{_person('head')}",
            "limit": -1,
            "sort": "id",
        },
    )


def body_members(body: str) -> list[dict]:
    """The members of one body (management_board or council), in page order."""
    return get_directus_items(
        "faculty_body_members",
        {
            "fields": f"position,{_person('staff')}",
            "filter[body][_eq]": body,
            "limit": -1,
            "sort": "sort,id",
        },
    )


def _lowered(name: str) -> str:
    return name[:1].lower() + name[1:]


def _person_id(person: object) -> int | None:
    return person.get("id") if isinstance(person, dict) else None


def staff_institute(staff_id: int) -> str | None:
    """The institute a staff member belongs to or heads."""
    for institute in institutes():
        members = institute.get("members") or []
        ids = {_person_id(member.get("staff")) for member in members}
        if staff_id in ids or _person_id(institute.get("head")) == staff_id:
            return institute["name"]
    return None


def staff_roles(staff_id: int) -> list[str]:
    """
    A staff member's functions in the faculty structure: their place in the
    management board, the institutes and centers they head, and ННС
    membership. A head of an institute is named once, though both the board
    and the institute record it.
    """
    roles: dict[str, str] = {}

    def add(role: str) -> None:
        roles.setdefault(role.casefold(), role)

    for row in body_members("management_board"):
        if _person_id(row.get("staff")) == staff_id and row.get("position"):
            add(row["position"])
    for institute in institutes():
        if _person_id(institute.get("head")) == staff_id:
            add(f"Раководител на {_lowered(institute['name'])}")
    for center in centers():
        if _person_id(center.get("head")) == staff_id:
            add(f"Раководител на {_lowered(center['name'])}")
    if any(_person_id(row.get("staff")) == staff_id for row in body_members("council")):
        add("Член на Наставно-научниот совет (ННС)")
    return list(roles.values())
