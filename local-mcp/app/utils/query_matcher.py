from typing import TypedDict

import cyrtranslit  # type: ignore[import-untyped]
from thefuzz import fuzz  # type: ignore[import-untyped]


class QueryResolution(TypedDict):
    status: str
    match: str | None
    score: int
    match_type: str
    candidates: list[str]


def transliterate_and_normalize(text: str) -> str:
    try:
        return cyrtranslit.to_cyrillic(text, "mk").casefold().strip()
    except Exception:
        return text.casefold().strip()


def match_query_to_group(
    query: str,
    candidates: list[str],
    fuzzy_threshold: int = 80,
) -> list[str] | None:
    if not candidates:
        return None

    norm_query = transliterate_and_normalize(query)
    scored = [
        (fuzz.WRatio(norm_query, transliterate_and_normalize(candidate)), candidate)
        for candidate in candidates
    ]
    top_score = max(score for score, _ in scored)
    if top_score < fuzzy_threshold:
        return None

    return [candidate for score, candidate in scored if score == top_score]


def resolve_query(
    query: str,
    candidates: list[str],
    fuzzy_threshold: int = 80,
    ambiguity_margin: int = 5,
    suggestion_floor: int = 50,
) -> QueryResolution:
    pairs = [(c, transliterate_and_normalize(c)) for c in candidates]
    norm_query = transliterate_and_normalize(query)

    for candidate, norm_candidate in pairs:
        if norm_candidate == norm_query:
            return {
                "status": "matched",
                "match": candidate,
                "score": 100,
                "match_type": "exact",
                "candidates": [],
            }

    scored = sorted(
        ((fuzz.WRatio(norm_query, nc), c) for c, nc in pairs),
        key=lambda pair: (-pair[0], pair[1]),
    )
    if not scored:
        return {
            "status": "not_found",
            "match": None,
            "score": 0,
            "match_type": "none",
            "candidates": [],
        }

    top_score = scored[0][0]
    if top_score < fuzzy_threshold:
        return {
            "status": "not_found",
            "match": None,
            "score": top_score,
            "match_type": "none",
            "candidates": [name for score, name in scored if score >= suggestion_floor],
        }

    cluster = [name for score, name in scored if score >= top_score - ambiguity_margin]
    if len(cluster) == 1:
        return {
            "status": "matched",
            "match": cluster[0],
            "score": top_score,
            "match_type": "fuzzy",
            "candidates": [],
        }
    return {
        "status": "ambiguous",
        "match": None,
        "score": top_score,
        "match_type": "ambiguous",
        "candidates": cluster,
    }
