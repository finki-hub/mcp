import re
from collections.abc import Iterable

from app.schemas.course_details import CourseUnlock
from app.utils.http_client import get_directus_items

# Which courses name a course among their prerequisites. A prerequisite is
# the text the accreditation gives ("Оперативни системи и (Компјутерски
# мрежи или Компјутерски мрежи и безбедност)"), so the names in it are
# found as the longest known course name at each word, never by splitting
# on "и"/"или", which are also inside names.

_WORD = re.compile(r"\w+", re.UNICODE)


def _key(text: str) -> str:
    return " ".join(_WORD.findall(text.casefold()))


def named_courses(text: str, names: Iterable[str]) -> set[str]:
    """The known names in a prerequisite text, by their normalized key."""
    by_first: dict[str, list[list[str]]] = {}
    for name in {_key(name) for name in names if name}:
        words = name.split()
        if words:
            by_first.setdefault(words[0], []).append(words)
    for candidates in by_first.values():
        candidates.sort(key=len, reverse=True)

    words = _key(text).split()
    found: set[str] = set()
    index = 0
    while index < len(words):
        match = next(
            (
                candidate
                for candidate in by_first.get(words[index], ())
                if words[index : index + len(candidate)] == candidate
            ),
            None,
        )
        if match is None:
            index += 1
            continue
        found.add(" ".join(match))
        index += len(match)
    return found


def courses_unlocked_by(course_names: Iterable[str]) -> list[CourseUnlock]:
    """
    The subjects of the published accreditations whose prerequisites name
    one of these names (a course's name and its accreditation names), newest
    accreditation first.
    """
    targets = {_key(name) for name in course_names if name}
    entries = get_directus_items(
        "curriculum_entries",
        {
            "fields": (
                "name,prerequisites,generation.code,generation.published,"
                "course_links.course.name"
            ),
            "limit": -1,
        },
    )
    known = [entry.get("name") or "" for entry in entries]
    known += [
        link["course"]["name"]
        for entry in entries
        for link in entry.get("course_links") or []
        if isinstance(link.get("course"), dict) and link["course"].get("name")
    ]
    unlocks: dict[tuple[str, str], CourseUnlock] = {}
    for entry in entries:
        generation = entry.get("generation") or {}
        text = entry.get("prerequisites")
        if not text or not generation.get("published"):
            continue
        if _key(entry.get("name") or "") in targets:
            continue
        if not named_courses(text, known) & targets:
            continue
        linked = [
            link["course"]["name"]
            for link in entry.get("course_links") or []
            if isinstance(link.get("course"), dict) and link["course"].get("name")
        ]
        name = linked[0] if linked else entry["name"]
        unlocks.setdefault(
            (generation["code"], name),
            CourseUnlock(
                course=name, accreditation=generation["code"], prerequisites=text
            ),
        )
    return sorted(
        unlocks.values(), key=lambda row: (-int(row.accreditation), row.course)
    )
