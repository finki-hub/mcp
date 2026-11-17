from collections import Counter
from collections.abc import Callable
from typing import NamedTuple

from app.utils.abbreviation_matcher import (
    build_abbreviation_index,
    resolve_abbreviation,
)
from app.utils.http_client import get_directus_items
from app.utils.query_matcher import resolve_query, transliterate_and_normalize

# Names looked up in Directus: staff, courses and rooms, each read whole
# (a few hundred rows) and cached for an hour.

MIN_QUERY_LENGTH = 3

_STAFF_PARAMS: dict[str, str | int] = {"fields": "id,name", "limit": -1}
_COURSE_PARAMS: dict[str, str | int] = {
    "fields": "id,name,name_en,abbreviation,degree_cycle",
    "limit": -1,
}
_ROOM_PARAMS: dict[str, str | int] = {"fields": "id,name,location", "limit": -1}


class Found(NamedTuple):
    record: dict | None
    error: str | None = None
    suggestions: list[str] | None = None


def _by_label(
    query: str,
    records: list[dict],
    label: Callable[[dict], str],
    noun: str,
) -> Found:
    if len(query.strip()) < MIN_QUERY_LENGTH:
        return Found(
            None,
            f"Барањето „{query}“ е прекратко; внесете барем {MIN_QUERY_LENGTH} знаци.",
        )
    labels: dict[str, list[dict]] = {}
    for record in records:
        labels.setdefault(label(record), []).append(record)
    resolution = resolve_query(query, list(labels))
    if resolution["status"] == "matched" and resolution["match"] in labels:
        matches = labels[resolution["match"]]
        if len(matches) == 1:
            return Found(matches[0])
        # Two records with the same name: neither is chosen.
        return Found(
            None,
            f"Повеќе {noun} се викаат „{resolution['match']}“",
            [resolution["match"]],
        )
    if resolution["status"] == "ambiguous":
        return Found(
            None,
            f"Повеќе {noun} одговараат на „{query}“",
            resolution["candidates"],
        )
    return Found(
        None,
        f"„{query}“ не е пронајден ({noun})",
        resolution["candidates"] or None,
    )


def find_staff(query: str) -> Found:
    return _by_label(
        query,
        get_directus_items("staff", _STAFF_PARAMS),
        lambda record: record["name"],
        "вработени",
    )


_CYCLE_LABELS = {"first": "прв циклус", "second": "втор циклус", "third": "трет циклус"}


def course_labeller(courses: list[dict]) -> Callable[[dict], str]:
    # A name two courses share (an undergraduate and a master's course)
    # carries its cycle, so each can be named apart.
    shared = Counter(record["name"] for record in courses)

    def label(record: dict) -> str:
        cycle = _CYCLE_LABELS.get(record.get("degree_cycle") or "")
        if shared[record["name"]] > 1 and cycle:
            return f"{record['name']} ({cycle})"
        return record["name"]

    return label


def find_course(query: str) -> Found:
    courses = get_directus_items("courses", _COURSE_PARAMS)
    label = course_labeller(courses)
    normalized = transliterate_and_normalize(query)
    exact = [
        record
        for record in courses
        if normalized
        and normalized
        in {
            transliterate_and_normalize(value)
            for value in (
                record.get("abbreviation"),
                record.get("name"),
                record.get("name_en"),
                label(record),
            )
            if value
        }
    ]
    if len(exact) > 1:
        # The cycle in the query decides between same-named courses.
        labelled = [
            r for r in exact if transliterate_and_normalize(label(r)) == normalized
        ]
        exact = labelled or exact
    if len(exact) == 1:
        return Found(exact[0])
    names = resolve_abbreviation(query, build_abbreviation_index(courses))
    if len(names) == 1:
        return Found(next(record for record in courses if record["name"] == names[0]))
    if len(names) > 1 or len(exact) > 1:
        return Found(
            None,
            f"Повеќе предмети одговараат на „{query}“",
            names or [label(record) for record in exact],
        )
    return _by_label(query, courses, label, "предмети")


def room_label(record: dict) -> str:
    location = record.get("location")
    return f"{record['name']} ({location})" if location else record["name"]


def find_room(query: str) -> Found:
    rooms = get_directus_items("rooms", _ROOM_PARAMS)
    normalized = transliterate_and_normalize(query)
    exact = [
        record
        for record in rooms
        if normalized
        and normalized
        in {
            transliterate_and_normalize(record["name"]),
            transliterate_and_normalize(room_label(record)),
        }
    ]
    if len(exact) == 1:
        return Found(exact[0])
    if len(exact) > 1:
        # One name in several buildings, such as a lab in two of them.
        return Found(
            None,
            f"Повеќе простории се викаат „{query}“; наведете ја и локацијата",
            [room_label(record) for record in exact],
        )
    return _by_label(query, rooms, room_label, "простории")
