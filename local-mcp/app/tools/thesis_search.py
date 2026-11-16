from collections.abc import Callable

from app.schemas.thesis_search import (
    ThesisKind,
    ThesisMatch,
    ThesisRole,
    ThesisSearch,
)
from app.tools.directus_lookup import find_staff
from app.utils.http_client import get_directus_items
from app.utils.query_matcher import resolve_query, transliterate_and_normalize

# Bachelor's and master's theses from Directus, searched by any staff member
# of the committee (each name matched to staff by the thesis import), role,
# year and title.

DEFAULT_THESIS_LIMIT = 20

_ROLES = {role.value for role in ThesisRole}

# Per kind: the theses, their staff table and the date each one carries.
_KINDS = {
    ThesisKind.BACHELOR: ("bachelor_theses", "bachelor_thesis_staff", "submitted"),
    ThesisKind.MASTER: ("master_theses", "master_thesis_staff", "presented"),
}


def _theses(kind: ThesisKind) -> list[dict]:
    collection, _staff, date = _KINDS[kind]
    return get_directus_items(
        collection,
        {
            "fields": f"id,title,student_index,student_name,mentor,year,status,{date}",
            "limit": -1,
        },
    )


def _staff_roles(kind: ThesisKind, staff_id: int) -> dict[int, ThesisRole]:
    _collection, staff_collection, _date = _KINDS[kind]
    rows = get_directus_items(
        staff_collection,
        {"fields": "thesis,role", "filter[staff][_eq]": staff_id, "limit": -1},
    )
    # A staff member holds one role on a committee; mentor wins a tie.
    roles: dict[int, ThesisRole] = {}
    for row in rows:
        if row.get("role") not in _ROLES:
            continue
        role = ThesisRole(row["role"])
        if roles.get(row["thesis"]) != ThesisRole.MENTOR:
            roles[row["thesis"]] = role
    return roles


def _match(kind: ThesisKind, thesis: dict, role: ThesisRole | None) -> ThesisMatch:
    _collection, _staff, date = _KINDS[kind]
    return ThesisMatch(
        kind=kind,
        title=thesis["title"],
        student=thesis.get("student_name") or None,
        student_index=thesis.get("student_index") or None,
        mentor=thesis.get("mentor") or None,
        year=thesis.get("year"),
        date=thesis.get(date),
        status=thesis.get("status") or None,
        role=role,
    )


def _names_starting_with(words: list[str], names: set[str]) -> set[str]:
    # Every query word starts a word of the name, in any order: "ana an"
    # finds "Ана Анова" but "ана" does not find "Маријана".
    accepted: set[str] = set()
    for name in names:
        tokens = transliterate_and_normalize(name).split()
        if all(any(token.startswith(word) for token in tokens) for word in words):
            accepted.add(name)
    return accepted


def _student_matcher(
    student: str | None,
    theses: list[dict],
) -> Callable[[dict], bool]:
    if student is None:
        return lambda _thesis: True
    if student.isascii() and student.isdigit():
        # An index number, leading zeros aside.
        index = student.lstrip("0") or "0"
        return lambda thesis: (
            (str(thesis.get("student_index") or "").lstrip("0") or "0") == index
        )
    names = {thesis["student_name"] for thesis in theses if thesis.get("student_name")}
    accepted = _names_starting_with(transliterate_and_normalize(student).split(), names)
    if not accepted:
        # A misspelt name: the closest names, as the old student lookups did.
        resolution = resolve_query(student, sorted(names))
        if resolution["status"] == "matched" and resolution["match"]:
            accepted = {resolution["match"]}
        elif resolution["status"] == "ambiguous":
            accepted = set(resolution["candidates"])
    return lambda thesis: thesis.get("student_name") in accepted


def find_theses(
    *,
    kind: ThesisKind | None = None,
    staff: str | None = None,
    student: str | None = None,
    role: ThesisRole | None = None,
    year: int | None = None,
    query: str | None = None,
    limit: int = DEFAULT_THESIS_LIMIT,
) -> ThesisSearch:
    staff = staff.strip() if staff and staff.strip() else None
    query = query.strip() if query and query.strip() else None
    student = student.strip() if student and student.strip() else None
    if all(value is None for value in (staff, student, query, year, kind)):
        return ThesisSearch(
            error="Внесете вработен, студент, година, вид или дел од насловот.",
        )
    if role is not None and staff is None:
        return ThesisSearch(error="Улогата се задава заедно со вработен.")
    if role == ThesisRole.PRESIDENT:
        # Only a master's committee has a president.
        if kind == ThesisKind.BACHELOR:
            return ThesisSearch(
                error="Дипломските работи немаат претседател на комисија.",
            )
        kind = ThesisKind.MASTER

    staff_id: int | None = None
    staff_name: str | None = None
    if staff is not None:
        found = find_staff(staff)
        if found.record is None:
            return ThesisSearch(error=found.error, suggestions=found.suggestions)
        staff_id, staff_name = found.record["id"], found.record["name"]

    needle = transliterate_and_normalize(query) if query else None
    theses = {each: _theses(each) for each in ([kind] if kind else list(ThesisKind))}
    matches_student = _student_matcher(
        student,
        [thesis for rows in theses.values() for thesis in rows],
    )
    matches: list[tuple[tuple[int, str], ThesisMatch]] = []
    for each, rows in theses.items():
        roles = _staff_roles(each, staff_id) if staff_id is not None else None
        _collection, _staff, date = _KINDS[each]
        for thesis in rows:
            held = roles.get(thesis["id"]) if roles is not None else None
            if roles is not None and (held is None or (role and held != role)):
                continue
            if year is not None and thesis.get("year") != year:
                continue
            if needle and needle not in transliterate_and_normalize(thesis["title"]):
                continue
            if not matches_student(thesis):
                continue
            key = (thesis.get("year") or 0, thesis.get(date) or "")
            matches.append((key, _match(each, thesis, held)))

    # Newest first: by year, then by date within it.
    matches.sort(key=lambda pair: pair[0], reverse=True)
    return ThesisSearch(
        total=len(matches),
        truncated=len(matches) > limit,
        staff=staff_name,
        items=[thesis for _date, thesis in matches[:limit]],
    )
