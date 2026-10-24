import logging
import re
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Final

from app.schemas.announcement import (
    AnnouncementDetail,
    AnnouncementMatch,
    AnnouncementSearchResult,
)
from app.utils.announcements_client import (
    AnnouncementRecord,
    AnnouncementsUnavailableError,
    fetch_announcement,
    get_announcement_snapshot,
    search_remote_announcements,
)
from app.utils.query_matcher import normalized_words, transliterate_and_normalize

logger = logging.getLogger(__name__)

DEFAULT_LOOKBACK: Final = timedelta(days=180)
MAX_TEXT_LENGTH: Final = 8000
_EXCERPT_LENGTH: Final = 400
_TITLE_WEIGHT: Final = 3.0
_BODY_WEIGHT: Final = 1.0
# A stem-only hit ("пријав" in "пријавени" for "пријавување") is weaker evidence.
_STEM_MATCH_WEIGHT: Final = 0.5
_HALF_LIFE_DAYS: Final = 30.0
# Keeps old but strongly matching announcements above recent incidental mentions.
_RECENCY_FLOOR: Final = 0.3
_MIN_STEM_LENGTH: Final = 3
_REMOTE_SEARCH_SIZE: Final = 20
_WORD_PATTERN: Final = re.compile(r"\w+")
_DATE_PATTERN: Final = re.compile(r"\d{1,2}\s?\.\s?\d{1,2}\s?\.\s?\d{2,4}")
_STOPWORDS: Final = frozenset(
    {
        "во",
        "да",
        "дали",
        "до",
        "за",
        "и",
        "или",
        "каде",
        "како",
        "кога",
        "на",
        "од",
        "по",
        "при",
        "се",
        "со",
        "што",
    },
)
# Common Macedonian inflectional endings, longest first, so that e.g.
# "пријавување" and "пријавувањето" share the stem "пријав".
_SUFFIXES: Final = tuple(
    sorted(
        {
            "ување",
            "увања",
            "ањето",
            "ењето",
            "ањата",
            "ање",
            "ања",
            "ење",
            "ења",
            "ија",
            "ии",
            "ите",
            "ето",
            "ата",
            "ови",
            "от",
            "та",
            "те",
            "то",
            "на",
            "ни",
            "но",
            "ен",
            "а",
            "е",
            "и",
            "о",
        },
        key=len,
        reverse=True,
    ),
)


class AnnouncementNotFoundError(LookupError):
    def __init__(self, id: int) -> None:
        super().__init__(id)
        self.id = id

    def __str__(self) -> str:
        return f"Огласот со ID {self.id} не е пронајден."


@dataclass(frozen=True, slots=True)
class QueryTerm:
    word: str
    stem: str


@dataclass(frozen=True, slots=True)
class _Ranked:
    record: AnnouncementRecord
    score: float


def _today() -> date:
    return datetime.now(UTC).date()


def _stem(word: str) -> str:
    for suffix in _SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= _MIN_STEM_LENGTH:
            return word[: -len(suffix)]
    return word


def query_terms(query: str | None) -> tuple[QueryTerm, ...]:
    if query is None:
        return ()
    words = (
        word
        for word in normalized_words(query)
        if len(word) > 1 and word not in _STOPWORDS
    )
    return tuple(QueryTerm(word, _stem(word)) for word in dict.fromkeys(words))


def _is_inflection(word: str, base: str) -> bool:
    return word.startswith(base) and (
        len(word) == len(base) or word[len(base) :] in _SUFFIXES
    )


def _has_full_match(words: Collection[str], term: QueryTerm) -> bool:
    return any(_is_inflection(word, term.word) for word in words)


def _term_weight(words: Collection[str], term: QueryTerm) -> float:
    if _has_full_match(words, term):
        return 1.0
    if any(word.startswith(term.stem) for word in words):
        return _STEM_MATCH_WEIGHT
    return 0.0


def _keyword_score(record: AnnouncementRecord, terms: Sequence[QueryTerm]) -> float:
    weights = [
        (
            _term_weight(record.title_words, term),
            _term_weight(record.body_words, term),
        )
        for term in terms
    ]
    # Stems alone ("пријав" in "пријавени" for "пријавување") are too loose to
    # carry a multi-word query: count them only next to a full-word match.
    if len(terms) > 1 and all(max(pair) < 1.0 for pair in weights):
        return 0.0
    return sum(
        max(_TITLE_WEIGHT * title, _BODY_WEIGHT * body) for title, body in weights
    )


def _has_title_match(record: AnnouncementRecord, terms: Sequence[QueryTerm]) -> bool:
    return any(_has_full_match(record.title_words, term) for term in terms)


def _recency(published: date, today: date) -> float:
    age_days = max((today - published).days, 0)
    decay = 0.5 ** (age_days / _HALF_LIFE_DAYS)
    return _RECENCY_FLOOR + (1 - _RECENCY_FLOOR) * decay


def _snap_to_words(text: str, start: int, end: int) -> tuple[int, int]:
    if start > 0 and not text[start - 1].isspace():
        space = text.find(" ", start, start + 40)
        if space != -1:
            start = space + 1
    if end < len(text) and not text[end].isspace():
        space = text.rfind(" ", end - 40, end)
        if space != -1:
            end = space
    for match in _DATE_PATTERN.finditer(text):
        if match.start() < start < match.end():
            start = match.start()
        if match.start() < end < match.end():
            end = match.end()
    return start, end


def _best_hit_center(text: str, stems: Sequence[str]) -> int | None:
    hits = [
        (match.start(), match.end(), stem)
        for match in _WORD_PATTERN.finditer(text)
        for stem in stems
        if transliterate_and_normalize(match.group()).startswith(stem)
    ]
    if not hits:
        return None
    dates = [match.start() for match in _DATE_PATTERN.finditer(text)]
    half = _EXCERPT_LENGTH // 2
    best: tuple[int, bool, int] | None = None
    best_center = None
    for start, end, _stem_hit in hits:
        center = (start + end) // 2
        low, high = center - half, center + half
        coverage = len(
            {stem for hit_start, _end, stem in hits if low <= hit_start < high}
        )
        has_date = any(low <= position < high for position in dates)
        key = (coverage, has_date, -center)
        if best is None or key > best:
            best = key
            best_center = center
    return best_center


def excerpt(text: str, stems: Sequence[str]) -> str:
    flat = " ".join(text.split())
    if len(flat) <= _EXCERPT_LENGTH:
        return flat
    center = _best_hit_center(flat, stems) if stems else None
    start = 0
    if center is not None:
        start = min(max(center - _EXCERPT_LENGTH // 2, 0), len(flat) - _EXCERPT_LENGTH)
    start, end = _snap_to_words(flat, start, start + _EXCERPT_LENGTH)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(flat) else ""
    return f"{prefix}{flat[start:end].strip()}{suffix}"


def _to_match(
    record: AnnouncementRecord, terms: Sequence[QueryTerm]
) -> AnnouncementMatch:
    return AnnouncementMatch(
        id=record.id,
        title=record.title,
        published=record.published,
        updated=record.modified if record.modified != record.published else None,
        url=record.url,
        excerpt=excerpt(record.text, [term.stem for term in terms]),
    )


def _rank(
    records: Sequence[AnnouncementRecord],
    terms: Sequence[QueryTerm],
    today: date,
    remote_ids: Collection[int] = (),
) -> list[_Ranked]:
    ranked = []
    for record in records:
        score = _keyword_score(record, terms)
        if record.id in remote_ids:
            # The upstream search matched it even if our stems did not.
            score = max(score, _BODY_WEIGHT)
        if score > 0:
            ranked.append(_Ranked(record, score * _recency(record.published, today)))
    ranked.sort(
        key=lambda item: (item.score, item.record.published, item.record.id),
        reverse=True,
    )
    return ranked


def search_announcements(
    query: str | None = None,
    since: date | None = None,
    limit: int = 5,
) -> AnnouncementSearchResult:
    snapshot = get_announcement_snapshot()
    today = _today()
    default_window = since is None
    since = since or today - DEFAULT_LOOKBACK
    records = [record for record in snapshot.records if record.published >= since]
    terms = query_terms(query)

    if not terms:
        newest = sorted(
            records, key=lambda record: (record.published, record.id), reverse=True
        )
        matches = [_to_match(record, terms) for record in newest[:limit]]
        return AnnouncementSearchResult(
            announcements=matches,
            fetched_at=snapshot.fetched_at,
            stale=snapshot.stale,
        )

    ranked = _rank(records, terms, today)
    if default_window and not any(
        _has_title_match(item.record, terms) for item in ranked
    ):
        # The default window is soft: with no title match in it, an older
        # announcement on the topic beats incidental mentions in recent ones.
        records = list(snapshot.records)
        ranked = _rank(records, terms, today)
    oldest = min((record.published for record in snapshot.records), default=None)
    if query and len(ranked) < limit and (oldest is None or since < oldest):
        known = {record.id for record in records}
        try:
            remote = search_remote_announcements(
                transliterate_and_normalize(query),
                since,
                _REMOTE_SEARCH_SIZE,
            )
        except AnnouncementsUnavailableError:
            logger.warning("Fallback announcement search failed", exc_info=True)
            remote = []
        extra = [
            record
            for record in remote
            if record.id not in known and record.published >= since
        ]
        ranked = _rank(
            [*records, *extra],
            terms,
            today,
            remote_ids={record.id for record in extra},
        )

    return AnnouncementSearchResult(
        announcements=[_to_match(item.record, terms) for item in ranked[:limit]],
        fetched_at=snapshot.fetched_at,
        stale=snapshot.stale,
    )


def _cap_text(text: str) -> tuple[str, bool]:
    if len(text) <= MAX_TEXT_LENGTH:
        return text, False
    cut = text.rfind("\n", 0, MAX_TEXT_LENGTH)
    if cut < MAX_TEXT_LENGTH // 2:
        cut = text.rfind(" ", 0, MAX_TEXT_LENGTH)
    if cut <= 0:
        cut = MAX_TEXT_LENGTH
    return f"{text[:cut].rstrip()}\n…", True


def get_announcement(id: int) -> AnnouncementDetail:
    record = None
    try:
        snapshot = get_announcement_snapshot()
    except AnnouncementsUnavailableError:
        logger.warning("Announcement snapshot unavailable, fetching %s directly", id)
    else:
        record = next((item for item in snapshot.records if item.id == id), None)
    if record is None:
        record = fetch_announcement(id)
    if record is None:
        raise AnnouncementNotFoundError(id)

    text, truncated = _cap_text(record.text)
    return AnnouncementDetail(
        id=record.id,
        title=record.title,
        published=record.published,
        updated=record.modified if record.modified != record.published else None,
        url=record.url,
        text=text,
        truncated=truncated,
    )
