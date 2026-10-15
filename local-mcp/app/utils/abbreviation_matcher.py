import re

import cyrtranslit  # type: ignore[import-untyped]

_SEPARATORS_RE = re.compile(r"[\s.\-]+")
# cyrtranslit's Macedonian table expects diacritics (š, č, ž), so ASCII digraphs
# typed by students would otherwise become two letters (sh -> сх).
_ASCII_DIGRAPHS = {
    "dzh": "џ",
    "zh": "ж",
    "sh": "ш",
    "ch": "ч",
    "kj": "ќ",
    "gj": "ѓ",
}
_DIGRAPH_RE = re.compile("|".join(_ASCII_DIGRAPHS), re.IGNORECASE)
_MAX_ABBREVIATION_LENGTH = 10
_MIN_CAPITALS = 2

type AbbreviationIndex = tuple[dict[str, list[str]], dict[str, list[str]]]


def _compact(text: str) -> str:
    return _SEPARATORS_RE.sub("", text.strip())


def _to_cyrillic(text: str) -> str:
    try:
        return cyrtranslit.to_cyrillic(text, "mk")
    except Exception:
        return text


def _replace_digraph(match: re.Match[str]) -> str:
    latin = match.group(0)
    cyrillic = _ASCII_DIGRAPHS[latin.casefold()]
    return cyrillic.upper() if latin[0].isupper() else cyrillic


def _capitals(text: str) -> str:
    return "".join(ch for ch in text if not ch.islower())


def _add(index: dict[str, list[str]], key: str, name: str) -> None:
    names = index.setdefault(key, [])
    if name not in names:
        names.append(name)


def build_abbreviation_index(courses: list[dict]) -> AbbreviationIndex:
    """
    Map normalized abbreviations to course names. The second map is keyed by the
    capitals-only form (БнП -> бп) for abbreviations that contain connector letters.
    """
    full: dict[str, list[str]] = {}
    capitals: dict[str, list[str]] = {}
    for record in courses:
        abbreviation = _compact(record.get("abbreviation") or "")
        name = record.get("name")
        if not abbreviation or not name:
            continue
        cyrillic = _to_cyrillic(abbreviation)
        _add(full, cyrillic.casefold(), name)
        caps = _capitals(cyrillic)
        if caps != cyrillic and sum(ch.isupper() for ch in caps) >= _MIN_CAPITALS:
            _add(capitals, caps.casefold(), name)
    return full, capitals


def _query_forms(query: str) -> list[str]:
    compact = _compact(query)
    if not compact:
        return []

    variants = [_to_cyrillic(compact)]
    with_digraphs = _to_cyrillic(_DIGRAPH_RE.sub(_replace_digraph, compact))
    if with_digraphs not in variants:
        variants.append(with_digraphs)

    forms = [variant.casefold() for variant in variants]
    if len(query.split()) == 1 and len(compact) <= _MAX_ABBREVIATION_LENGTH:
        for variant in variants:
            caps = _capitals(variant)
            if caps != variant and sum(ch.isupper() for ch in caps) >= _MIN_CAPITALS:
                forms.append(caps.casefold())
    return list(dict.fromkeys(forms))


def resolve_abbreviation(query: str, index: AbbreviationIndex) -> list[str]:
    """
    Return the course names whose abbreviation matches the query exactly, trying
    full abbreviations before capitals-only forms. Shared abbreviations return
    every course; no match returns an empty list.
    """
    full, capitals = index
    for form in _query_forms(query):
        for table in (full, capitals):
            if form in table:
                return list(table[form])
    return []
