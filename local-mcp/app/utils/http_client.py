import logging
import time

import httpx

from app.utils.settings import Settings

logger = logging.getLogger(__name__)

_CACHE_TTL = 3600  # 1 hour in seconds

_settings = Settings()


class _JsonCache[JsonDocument]:
    """
    Time-bounded in-memory cache for a single upstream JSON document. On a
    failed refresh, the stale cache is returned when available.
    """

    def __init__(self, filename: str, base_url: str | None = None) -> None:
        self._filename = filename
        self._base_url = base_url
        self._data: JsonDocument | None = None
        self._timestamp = 0.0

    def get(self) -> JsonDocument:
        now = time.monotonic()
        if self._data is not None and (now - self._timestamp) < _CACHE_TTL:
            return self._data

        base_url = self._base_url or _settings.DATA_STORAGE_URL
        url = f"{base_url.rstrip('/')}/{self._filename}"
        try:
            response = httpx.get(url, timeout=30)
            response.raise_for_status()
            self._data = response.json()
            self._timestamp = now
            logger.info("Refreshed %s", url)
        except Exception:
            logger.exception("Failed to fetch %s", url)
            if self._data is None:
                raise

        return self._data


_courses_cache = _JsonCache[list[dict]]("courses.json")
_staff_cache = _JsonCache[list[dict]]("staff.json")
_rooms_cache = _JsonCache[list[dict]]("rooms.json")
_sessions_cache = _JsonCache[dict[str, str]]("sessions.json")
_anto_quotes_cache = _JsonCache[list[str]]("anto.json")
_timetables_cache = _JsonCache[list[dict]](
    "timetables",
    base_url=_settings.TIMETABLES_API_URL,
)
_timetable_detail_caches: dict[str, _JsonCache[dict]] = {}


def get_courses() -> list[dict]:
    """
    Fetch courses from R2 storage, returning a cached copy if it is less than
    one hour old.
    """
    return _courses_cache.get()


def get_staff() -> list[dict]:
    """
    Fetch staff from R2 storage, returning a cached copy if it is less than
    one hour old.
    """
    return _staff_cache.get()


def get_rooms() -> list[dict]:
    """
    Fetch rooms from R2 storage, returning a cached copy if it is less than
    one hour old.
    """
    return _rooms_cache.get()


def get_exam_sessions() -> dict[str, str]:
    """
    Fetch exam session schedule filenames from R2 storage, returning a cached
    copy if it is less than one hour old.
    """
    return _sessions_cache.get()


def get_anto_quotes() -> list[str]:
    """
    Fetch Anto quotes from R2 storage, returning a cached copy if it is less
    than one hour old.
    """
    return _anto_quotes_cache.get()


def get_timetables() -> list[dict]:
    """
    Fetch timetable summaries, returning a cached copy if it is less than one
    hour old.
    """
    return _timetables_cache.get()


def get_timetable_detail(id: str) -> dict:
    """
    Fetch a timetable by ID, returning a cached copy if it is less than one
    hour old.
    """
    timetable_id = id.strip()
    if not timetable_id:
        raise ValueError("Timetable ID is required")

    cache = _timetable_detail_caches.setdefault(
        timetable_id,
        _JsonCache[dict](
            f"timetables/{timetable_id}",
            base_url=_settings.TIMETABLES_API_URL,
        ),
    )
    return cache.get()
