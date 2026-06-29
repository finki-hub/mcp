import re
from typing import NamedTuple

from thefuzz import fuzz  # type: ignore[import-untyped]

from app.schemas.room import Room, RoomData, RoomLocation, RoomMatch, RoomType
from app.utils.http_client import get_rooms
from app.utils.query_matcher import transliterate_and_normalize

_ROOM_FUZZY_THRESHOLD = 88
_SHORT_ROOM_FUZZY_THRESHOLD = 92
_ROOM_AMBIGUITY_MARGIN = 2
_ROOM_SUGGESTION_FLOOR = 70
_MIN_FUZZY_QUERY_LENGTH = 2

_SEPARATORS_RE = re.compile(r"[\s._-]+")
_DIGIT_RE = re.compile(r"\d")

_LATIN_MULTI = (
    ("dzh", "џ"),
    ("dz", "ѕ"),
    ("gj", "ѓ"),
    ("kj", "ќ"),
    ("zh", "ж"),
    ("ch", "ч"),
    ("sh", "ш"),
)
_LATIN_SINGLE = str.maketrans(
    {
        "a": "а",
        "b": "б",
        "c": "ц",
        "d": "д",
        "e": "е",
        "f": "ф",
        "g": "г",
        "h": "х",
        "i": "и",
        "j": "ј",
        "k": "к",
        "l": "л",
        "m": "м",
        "n": "н",
        "o": "о",
        "p": "п",
        "r": "р",
        "s": "с",
        "t": "т",
        "u": "у",
        "v": "в",
        "z": "з",
    },
)


class _RoomResolution(NamedTuple):
    status: str
    match: str | None
    score: int
    match_type: str
    candidates: list[str]


class _Lookup(NamedTuple):
    records: list[dict] | None
    match_info: dict | None
    error: str | None
    suggestions: list[str] | None


def _clean(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _manual_mk_normalize(text: str) -> str:
    value = text.casefold().strip()
    for latin, cyrillic in _LATIN_MULTI:
        value = value.replace(latin, cyrillic)
    return value.translate(_LATIN_SINGLE)


def _normalized_variants(text: str) -> set[str]:
    return {
        variant
        for variant in {
            transliterate_and_normalize(text),
            _manual_mk_normalize(text),
        }
        if variant
    }


def _compact_variants(text: str) -> set[str]:
    return {
        _SEPARATORS_RE.sub("", variant)
        for variant in _normalized_variants(text)
        if _SEPARATORS_RE.sub("", variant)
    }


def _to_int(value: object) -> int | None:
    try:
        return int(str(value))
    except TypeError, ValueError:
        return None


def _build_room(record: dict) -> Room:
    return Room(
        name=_clean(record.get("name")) or "",
        type=_clean(record.get("type")),
        location=_clean(record.get("location")),
        description=_clean(record.get("description")),
        floor=_clean(record.get("floor")),
        capacity=_clean(record.get("capacity")),
        mrbs=_clean(record.get("mrbs")),
    )


def _build_room_match(record: dict) -> RoomMatch:
    return RoomMatch(
        name=_clean(record.get("name")) or "",
        type=_clean(record.get("type")),
        location=_clean(record.get("location")),
    )


def _score_name(query: str, candidate: str) -> int:
    return max(
        fuzz.WRatio(query_variant, candidate_variant)
        for query_variant in _normalized_variants(query)
        for candidate_variant in _normalized_variants(candidate)
    )


def _threshold_for(query: str) -> int:
    compact_len = min((len(value) for value in _compact_variants(query)), default=0)
    if compact_len <= 3 or _DIGIT_RE.search(query):
        return _SHORT_ROOM_FUZZY_THRESHOLD
    return _ROOM_FUZZY_THRESHOLD


def _suggestions_from_scored(scored: list[tuple[int, str]]) -> list[str]:
    suggestions: list[str] = []
    for _score, name in scored:
        if name not in suggestions:
            suggestions.append(name)
    return suggestions


def _resolve_room_name(query: str, candidates: list[str]) -> _RoomResolution:
    names = sorted({name for name in candidates if name})
    query_variants = _normalized_variants(query)
    exact = [name for name in names if query_variants & _normalized_variants(name)]
    if len(exact) == 1:
        return _RoomResolution("matched", exact[0], 100, "exact", [])
    if len(exact) > 1:
        return _RoomResolution("ambiguous", None, 100, "ambiguous", exact)

    query_compact = _compact_variants(query)
    compact_exact = [name for name in names if query_compact & _compact_variants(name)]
    if len(compact_exact) == 1:
        return _RoomResolution("matched", compact_exact[0], 100, "compact", [])

    compact_len = min((len(value) for value in query_compact), default=0)
    if compact_len < _MIN_FUZZY_QUERY_LENGTH:
        return _RoomResolution("too_short", None, 0, "none", [])

    scored = sorted(
        ((_score_name(query, name), name) for name in names),
        key=lambda pair: (-pair[0], pair[1]),
    )
    if not scored:
        return _RoomResolution("not_found", None, 0, "none", [])

    top_score = scored[0][0]
    if top_score < _threshold_for(query):
        suggestions = _suggestions_from_scored(
            [pair for pair in scored if pair[0] >= _ROOM_SUGGESTION_FLOOR],
        )
        return _RoomResolution("not_found", None, top_score, "none", suggestions)

    cluster = [
        name for score, name in scored if score >= top_score - _ROOM_AMBIGUITY_MARGIN
    ]
    if len(cluster) == 1:
        return _RoomResolution("matched", cluster[0], top_score, "fuzzy", [])

    return _RoomResolution("ambiguous", None, top_score, "ambiguous", cluster)


def _not_found(name: str) -> str:
    return f"Просторијата „{name}“ не е пронајдена"


def _lookup_room(name: str) -> _Lookup:
    query = name.strip()
    if not query:
        return _Lookup(None, None, "Внесете име на просторијата.", None)

    rooms = get_rooms()
    names = [_clean(record.get("name")) or "" for record in rooms]
    resolution = _resolve_room_name(name, names)

    if resolution.status == "too_short":
        return _Lookup(
            None,
            None,
            f"Барањето е прекратко; внесете барем {_MIN_FUZZY_QUERY_LENGTH} знаци.",
            None,
        )

    if resolution.status == "matched" and resolution.match is not None:
        records = [
            record
            for record in rooms
            if (_clean(record.get("name")) or "") == resolution.match
        ]
        if records:
            match_info = {
                "original_query": name,
                "matched_room": resolution.match,
                "similarity_score": resolution.score,
                "match_type": resolution.match_type,
            }
            return _Lookup(records, match_info, None, None)

    if resolution.status == "ambiguous":
        return _Lookup(
            None,
            None,
            f"Повеќе простории одговараат на „{name}“",
            resolution.candidates,
        )

    return _Lookup(
        None,
        None,
        _not_found(name),
        resolution.candidates or None,
    )


def list_rooms(
    type: RoomType | None = None,
    location: RoomLocation | None = None,
    floor: str | None = None,
    min_capacity: int | None = None,
) -> list[RoomMatch]:
    matches: list[RoomMatch] = []
    for record in get_rooms():
        if type is not None and _clean(record.get("type")) != type:
            continue
        if location is not None and _clean(record.get("location")) != location:
            continue
        if floor is not None and (_clean(record.get("floor")) or "") != floor.strip():
            continue
        if min_capacity is not None:
            capacity = _to_int(record.get("capacity"))
            if capacity is None or capacity < min_capacity:
                continue

        matches.append(_build_room_match(record))

    return matches


def get_room_data(name: str) -> RoomData:
    found = _lookup_room(name)
    if found.records is None:
        return RoomData(
            name=name,
            error=found.error,
            suggestions=found.suggestions,
        )

    return RoomData(
        name=_clean(found.records[0].get("name")) or name,
        rooms=[_build_room(record) for record in found.records],
        match_info=found.match_info,
    )
