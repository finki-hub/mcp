import json
import logging
import threading
import time
from typing import Final

import httpx

from app.schemas.syllabus import SubjectPayload
from app.utils.settings import Settings

logger = logging.getLogger(__name__)

_CACHE_TTL: Final = 24 * 60 * 60
_REQUEST_TIMEOUT: Final = 20.0
_RESPONSE_BYTE_LIMIT: Final = 1024 * 1024
_USER_AGENT: Final = "finki-hub-mcp (+https://github.com/finki-hub/mcp)"

_settings = Settings()
_cache: dict[str, tuple[float, SubjectPayload]] = {}
_cache_lock = threading.Lock()


class SyllabusUnavailableError(RuntimeError):
    def __str__(self) -> str:
        return "Официјалните податоци за предметите (pubapi) моментално не се достапни."


class SyllabusNotFoundError(LookupError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code

    def __str__(self) -> str:
        return f"Силабусот за предметот со код {self.code} не е пронајден во pubapi."


class _ResponseTooLargeError(ValueError):
    def __str__(self) -> str:
        return f"response exceeds {_RESPONSE_BYTE_LIMIT} bytes"


def _client(api_key: str) -> httpx.Client:
    headers = {
        "User-Agent": _USER_AGENT,
        "Accept": "application/json",
        "X-Api-Key": api_key,
    }
    return httpx.Client(headers=headers, timeout=_REQUEST_TIMEOUT)


def _get_json(url: str, api_key: str) -> object:
    with _client(api_key) as client, client.stream("GET", url) as response:
        response.raise_for_status()
        body = bytearray()
        for chunk in response.iter_bytes():
            body.extend(chunk)
            if len(body) > _RESPONSE_BYTE_LIMIT:
                raise _ResponseTooLargeError
    return json.loads(body)


def _load_subject(code: str) -> SubjectPayload:
    api_key = _settings.PUBAPI_API_KEY.get_secret_value()
    if not api_key:
        logger.warning("PUBAPI_API_KEY is not set; course syllabi are unavailable")
        raise SyllabusUnavailableError
    url = f"{_settings.PUBAPI_URL.rstrip('/')}/subjects/{code}"
    try:
        return SubjectPayload.model_validate(_get_json(url, api_key))
    except httpx.HTTPStatusError as error:
        status = error.response.status_code
        # pubapi answers an unknown code with 400 "Invalid subject id".
        if status in {httpx.codes.BAD_REQUEST, httpx.codes.NOT_FOUND}:
            raise SyllabusNotFoundError(code) from error
        logger.warning("pubapi returned %s for subject %s", status, code)
        raise SyllabusUnavailableError from error
    except (httpx.HTTPError, ValueError) as error:
        logger.warning("Failed to fetch subject %s: %s", code, type(error).__name__)
        raise SyllabusUnavailableError from error


def fetch_subject(code: str) -> SubjectPayload:
    """Return the pubapi subject details for a course code, cached for 24 hours."""
    now = time.monotonic()
    with _cache_lock:
        cached = _cache.get(code)
    if cached is not None and now - cached[0] < _CACHE_TTL:
        return cached[1]
    subject = _load_subject(code)
    with _cache_lock:
        _cache[code] = (now, subject)
    return subject
