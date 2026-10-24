import json
import logging
import threading
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Final

import httpx
from pydantic import TypeAdapter

from app.schemas.announcement import AnnouncementPayload
from app.utils.html_text import html_to_text
from app.utils.query_matcher import normalized_words
from app.utils.settings import Settings

logger = logging.getLogger(__name__)

_SNAPSHOT_TTL: Final = 15 * 60
_RETRY_DELAY: Final = 60
_SNAPSHOT_PAGES: Final = 2
_PAGE_SIZE: Final = 100
_REQUEST_TIMEOUT: Final = 20.0
_RESPONSE_BYTE_LIMIT: Final = 8 * 1024 * 1024
_USER_AGENT: Final = "finki-hub-mcp (+https://github.com/finki-hub/mcp)"
_FIELDS: Final = "id,date,modified,link,title,content"
_PAYLOADS: Final = TypeAdapter(list[AnnouncementPayload])

_settings = Settings()


class AnnouncementsUnavailableError(RuntimeError):
    def __str__(self) -> str:
        return "Огласната табла моментално не е достапна."


class _ResponseTooLargeError(ValueError):
    def __str__(self) -> str:
        return f"response exceeds {_RESPONSE_BYTE_LIMIT} bytes"


@dataclass(frozen=True, slots=True)
class AnnouncementRecord:
    id: int
    title: str
    text: str
    published: date
    modified: date
    url: str
    title_words: frozenset[str]
    body_words: frozenset[str]


@dataclass(frozen=True, slots=True)
class AnnouncementSnapshot:
    records: tuple[AnnouncementRecord, ...]
    fetched_at: datetime
    stale: bool


def _to_record(payload: AnnouncementPayload) -> AnnouncementRecord:
    title = " ".join(html_to_text(payload.title.rendered).split())
    text = html_to_text(payload.content.rendered)
    return AnnouncementRecord(
        id=payload.id,
        title=title,
        text=text,
        published=payload.date.date(),
        modified=payload.modified.date(),
        url=payload.link,
        title_words=frozenset(normalized_words(title)),
        body_words=frozenset(normalized_words(text)),
    )


def _get_json(url: str, params: dict[str, str | int]) -> object:
    headers = {"User-Agent": _USER_AGENT, "Accept": "application/json"}
    with (
        httpx.Client(headers=headers, timeout=_REQUEST_TIMEOUT) as client,
        client.stream("GET", url, params=params) as response,
    ):
        response.raise_for_status()
        body = bytearray()
        for chunk in response.iter_bytes():
            body.extend(chunk)
            if len(body) > _RESPONSE_BYTE_LIMIT:
                raise _ResponseTooLargeError
    return json.loads(body)


def _get_records(url: str, params: dict[str, str | int]) -> list[AnnouncementRecord]:
    return [
        _to_record(payload)
        for payload in _PAYLOADS.validate_python(_get_json(url, params))
    ]


def _load_snapshot() -> tuple[AnnouncementRecord, ...]:
    records: list[AnnouncementRecord] = []
    for page in range(_SNAPSHOT_PAGES):
        page_records = _get_records(
            _settings.FINKI_ANNOUNCEMENTS_API_URL,
            {"per_page": _PAGE_SIZE, "offset": page * _PAGE_SIZE, "_fields": _FIELDS},
        )
        records.extend(page_records)
        if len(page_records) < _PAGE_SIZE:
            break
    return tuple(records)


class AnnouncementSnapshotCache:
    def __init__(
        self, ttl: float = _SNAPSHOT_TTL, retry_delay: float = _RETRY_DELAY
    ) -> None:
        self._ttl = ttl
        self._retry_delay = retry_delay
        self._lock = threading.Lock()
        self._records: tuple[AnnouncementRecord, ...] | None = None
        self._fetched_at = datetime.min.replace(tzinfo=UTC)
        self._timestamp = 0.0
        self._retry_after = 0.0

    def get(self) -> AnnouncementSnapshot:
        with self._lock:
            now = time.monotonic()
            if self._records is not None and now - self._timestamp < self._ttl:
                return AnnouncementSnapshot(
                    self._records, self._fetched_at, stale=False
                )
            # Back off after a failed refresh so a slow upstream does not stall every call.
            if now >= self._retry_after:
                try:
                    records = _load_snapshot()
                except (httpx.HTTPError, ValueError) as error:
                    self._retry_after = now + self._retry_delay
                    logger.warning("Failed to refresh announcements: %s", error)
                else:
                    self._records = records
                    self._fetched_at = datetime.now(UTC)
                    self._timestamp = now
                    logger.info("Refreshed announcements snapshot")
                    return AnnouncementSnapshot(records, self._fetched_at, stale=False)
            if self._records is None:
                raise AnnouncementsUnavailableError
            return AnnouncementSnapshot(self._records, self._fetched_at, stale=True)


_snapshot_cache = AnnouncementSnapshotCache()


def get_announcement_snapshot() -> AnnouncementSnapshot:
    """
    Return the newest announcements, refreshed every 15 minutes. A failed
    refresh serves the previous snapshot marked as stale.
    """
    return _snapshot_cache.get()


def search_remote_announcements(
    query: str, after: date, limit: int
) -> list[AnnouncementRecord]:
    """
    Search older announcements with the WordPress full-text search, which is
    only reliable for Cyrillic queries.
    """
    try:
        return _get_records(
            _settings.FINKI_ANNOUNCEMENTS_API_URL,
            {
                "search": query,
                "after": f"{after.isoformat()}T00:00:00",
                "per_page": limit,
                "_fields": _FIELDS,
            },
        )
    except (httpx.HTTPError, ValueError) as error:
        raise AnnouncementsUnavailableError from error


def fetch_announcement(id: int) -> AnnouncementRecord | None:
    url = f"{_settings.FINKI_ANNOUNCEMENTS_API_URL.rstrip('/')}/{id}"
    try:
        payload = _get_json(url, {"_fields": _FIELDS})
        return _to_record(AnnouncementPayload.model_validate(payload))
    except httpx.HTTPStatusError as error:
        if error.response.status_code == httpx.codes.NOT_FOUND:
            return None
        raise AnnouncementsUnavailableError from error
    except (httpx.HTTPError, ValueError) as error:
        raise AnnouncementsUnavailableError from error
