"""# noqa: SIZE_OK - frozen plan/F4 scope keeps legacy and streamed caches in this module."""

import logging
import threading
import time
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from decimal import Decimal
from typing import Final, Literal, Protocol

import anyio
import httpx
import ijson
from pydantic import ValidationError

from app.schemas.defense import Diploma, DiplomaPayload, MasterDefense, MasterPayload
from app.utils.settings import Settings

logger = logging.getLogger(__name__)

_CACHE_TTL = 3600  # 1 hour in seconds
_STREAM_CHUNK_SIZE: Final = 65536
_STREAM_BYTE_LIMIT: Final = 16 * 1024 * 1024
_STREAM_ITEM_LIMIT: Final = 10_000
_STREAM_DEPTH_LIMIT: Final = 2
_STREAM_DEADLINE_SECONDS: Final = 30.0

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


type _JsonScalar = None | bool | int | float | Decimal | str
type _JsonValue = _JsonScalar | list[_JsonValue] | dict[str, _JsonValue]
type _DefenseDomain = Literal["diplomas", "masters"]
type _SafeRefreshIssue = tuple[tuple[str | int, ...], str]
type _SafeResourceIssue = Literal[
    "byte_limit", "content_encoding", "deadline", "depth_limit", "item_limit"
]


@dataclass(slots=True)  # MUTABLE_OK: CPython writes traceback metadata onto exceptions.
class DefenseSnapshotRefreshError(Exception):
    domain: _DefenseDomain
    ordinal: int
    issues: tuple[_SafeRefreshIssue, ...]

    def __str__(self) -> str:
        details = ",".join(
            f"{'.'.join(map(str, location)) or 'root'}:{code}"
            for location, code in self.issues
        )
        return f"{self.domain} refresh failed at item {self.ordinal}: {details}"


@dataclass(slots=True)  # MUTABLE_OK: CPython writes traceback metadata onto exceptions.
class _InvalidJsonRootError(ValueError):
    def __str__(self) -> str:
        return "invalid JSON array root"


@dataclass(slots=True)  # MUTABLE_OK: CPython writes traceback metadata onto exceptions.
class _ResourceLimitError(ValueError):
    issue: _SafeResourceIssue


@dataclass(frozen=True, slots=True)
class _StreamEndpoint[Record]:
    domain: _DefenseDomain
    url: str
    validate_item: Callable[[_JsonValue], Record]


class _ByteParser(Protocol):
    def send(self, chunk: bytes) -> None: ...

    def close(self) -> None: ...


class _AsyncByteResponse(Protocol):
    def aiter_bytes(self, *, chunk_size: int) -> AsyncIterator[bytes]: ...


class _TypedItemSink[Record]:
    __slots__ = ("endpoint", "records")

    def __init__(self, endpoint: _StreamEndpoint[Record]) -> None:
        self.endpoint = endpoint
        self.records: list[Record] = []

    @property
    def ordinal(self) -> int:
        return len(self.records)

    def send(self, item: _JsonValue) -> None:
        if self.ordinal >= _STREAM_ITEM_LIMIT:
            raise _ResourceLimitError("item_limit")
        self.records.append(self.endpoint.validate_item(item))


class _RootArrayValidator:
    __slots__ = ("_complete", "_depth", "_started")

    def __init__(self) -> None:
        self._started = False
        self._complete = False
        self._depth = 0

    def send(self, event: tuple[str, _JsonScalar]) -> None:
        event_name, _value = event
        if self._complete:
            raise _InvalidJsonRootError
        if not self._started:
            if event_name != "start_array":
                raise _InvalidJsonRootError
            self._started = True
            self._depth = 1
            return
        if event_name in {"start_array", "start_map"}:
            self._depth += 1
            if self._depth > _STREAM_DEPTH_LIMIT:
                raise _ResourceLimitError("depth_limit")
        elif event_name in {"end_array", "end_map"}:
            self._depth -= 1
            if self._depth == 0:
                if event_name != "end_array":
                    raise _InvalidJsonRootError
                self._complete = True

    def ensure_complete(self) -> None:
        if not self._complete or self._depth != 0:
            raise _InvalidJsonRootError


def _safe_validation_issues(error: ValidationError) -> tuple[_SafeRefreshIssue, ...]:
    return tuple(
        (tuple(detail["loc"]), detail["type"])
        for detail in error.errors(
            include_url=False, include_context=False, include_input=False
        )
    )


def _close_parsers(
    parsers: tuple[_ByteParser, _ByteParser],
) -> tuple[_SafeRefreshIssue, ...] | None:
    issues: tuple[_SafeRefreshIssue, ...] | None = None
    for parser in parsers:
        try:
            parser.close()
        except ValidationError as error:
            issues = issues or _safe_validation_issues(error)
        except _ResourceLimitError as error:
            issues = issues or (((), error.issue),)
        except ijson.JSONError, _InvalidJsonRootError:
            issues = issues or (((), "invalid_json"),)
    return issues


def _open_stream(
    client: httpx.AsyncClient, url: str
) -> AbstractAsyncContextManager[httpx.Response]:
    return client.stream("GET", url)


def _enforce_identity_encoding(response: httpx.Response) -> None:
    content_codings = (
        coding.strip().casefold()
        for coding in response.headers.get("Content-Encoding", "").split(",")
    )
    if any(coding and coding != "identity" for coding in content_codings):
        raise _ResourceLimitError("content_encoding")


def _enforce_stream_limits(total_bytes: int, deadline: float) -> None:
    if time.monotonic() > deadline:
        raise _ResourceLimitError("deadline")
    if total_bytes > _STREAM_BYTE_LIMIT:
        raise _ResourceLimitError("byte_limit")


async def _consume_response[Record](
    response: _AsyncByteResponse,
    sink: _TypedItemSink[Record],
    *,
    deadline: float,
) -> None:
    root_validator = _RootArrayValidator()
    item_parser: _ByteParser = ijson.items_coro(sink, "item", multiple_values=True)
    root_parser: _ByteParser = ijson.basic_parse_coro(
        root_validator, multiple_values=True
    )
    close_issues: tuple[_SafeRefreshIssue, ...] | None = None
    issues: tuple[_SafeRefreshIssue, ...] | None = None
    total_bytes = 0
    try:
        async for chunk in response.aiter_bytes(chunk_size=_STREAM_CHUNK_SIZE):
            total_bytes += len(chunk)
            _enforce_stream_limits(total_bytes, deadline)
            item_parser.send(chunk)
            root_parser.send(chunk)
    except _ResourceLimitError as error:
        issues = (((), error.issue),)
    finally:
        close_issues = _close_parsers((item_parser, root_parser))
    issues = issues or close_issues
    if issues is not None:
        raise DefenseSnapshotRefreshError(
            sink.endpoint.domain, sink.ordinal, issues
        ) from None
    root_validator.ensure_complete()


async def _load_snapshot_async[Record](
    endpoint: _StreamEndpoint[Record],
) -> list[Record]:
    sink = _TypedItemSink(endpoint)
    issues: tuple[_SafeRefreshIssue, ...] | None = None
    try:
        async with httpx.AsyncClient(
            headers={"Accept-Encoding": "identity"}, timeout=30
        ) as client:
            with anyio.fail_after(_STREAM_DEADLINE_SECONDS):
                async with _open_stream(client, endpoint.url) as response:
                    response.raise_for_status()
                    _enforce_identity_encoding(response)
                    await _consume_response(
                        response,
                        sink,
                        deadline=time.monotonic() + _STREAM_DEADLINE_SECONDS,
                    )
    except TimeoutError:
        issues = (((), "deadline"),)
    except ValidationError as error:
        issues = _safe_validation_issues(error)
    except httpx.HTTPStatusError as error:
        issues = (((), f"http_status_{error.response.status_code}"),)
    except httpx.HTTPError:
        issues = (((), "transport"),)
    except _ResourceLimitError as error:
        issues = (((), error.issue),)
    except ijson.JSONError, _InvalidJsonRootError:
        issues = (((), "invalid_json"),)
    if issues is not None:
        raise DefenseSnapshotRefreshError(
            endpoint.domain, sink.ordinal, issues
        ) from None
    return sink.records


def _load_snapshot[Record](endpoint: _StreamEndpoint[Record]) -> list[Record]:
    return anyio.run(_load_snapshot_async, endpoint)


class _StreamedDefenseCache[Record]:
    def __init__(self, endpoint: _StreamEndpoint[Record]) -> None:
        self._endpoint = endpoint
        self._data: list[Record] | None = None
        self._timestamp = 0.0
        self._refresh_lock = threading.Lock()
        self._refresh_generation = 0
        self._refresh_error: DefenseSnapshotRefreshError | None = None

    def get(self) -> list[Record]:
        generation = self._refresh_generation
        now = time.monotonic()
        if self._data is not None and (now - self._timestamp) < _CACHE_TTL:
            return self._data
        with self._refresh_lock:
            if generation != self._refresh_generation:
                if self._data is not None:
                    return self._data
                if self._refresh_error is not None:
                    raise self._refresh_error
            now = time.monotonic()
            if self._data is not None and (now - self._timestamp) < _CACHE_TTL:
                return self._data
            try:
                data = _load_snapshot(self._endpoint)
            except DefenseSnapshotRefreshError as error:
                self._refresh_error = error
                self._refresh_generation += 1
                logger.warning(
                    "Failed to refresh %s snapshot: %s",
                    self._endpoint.domain,
                    error,
                )
                if self._data is None:
                    raise
                return self._data
            self._data = data
            self._timestamp = now
            self._refresh_error = None
            self._refresh_generation += 1
            logger.info("Refreshed %s snapshot", self._endpoint.domain)
            return data


def _validate_diploma(item: _JsonValue) -> Diploma:
    return DiplomaPayload.model_validate(item).to_public()


def _validate_master(item: _JsonValue) -> MasterDefense:
    return MasterPayload.model_validate(item).to_public()


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
_diplomas_cache = _StreamedDefenseCache(
    _StreamEndpoint("diplomas", _settings.DIPLOMAS_API_URL, _validate_diploma)
)
_masters_cache = _StreamedDefenseCache(
    _StreamEndpoint("masters", _settings.MASTERS_API_URL, _validate_master)
)


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


def get_diplomas() -> list[Diploma]:
    return _diplomas_cache.get()


def get_masters() -> list[MasterDefense]:
    return _masters_cache.get()
