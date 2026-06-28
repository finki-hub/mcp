import functools
import logging
import time
import traceback
from collections.abc import Awaitable, Callable
from typing import ParamSpec, TypeVar

from posthog import Posthog

from app.utils.settings import Settings

logger = logging.getLogger(__name__)

_SERVICE = "local-mcp"
_DISTINCT_ID = "local-mcp-server"

P = ParamSpec("P")
R = TypeVar("R")


class _AnalyticsState:
    client: Posthog | None = None


_state = _AnalyticsState()


def init_analytics(settings: Settings) -> None:
    if not settings.POSTHOG_KEY:
        logger.info("PostHog disabled (no POSTHOG_KEY); analytics is a no-op")
        _state.client = None
        return

    try:
        _state.client = Posthog(
            project_api_key=settings.POSTHOG_KEY,
            host=settings.POSTHOG_HOST,
            enable_exception_autocapture=False,
        )
    except Exception:
        logger.exception("Failed to initialise PostHog client; analytics is a no-op")
        _state.client = None


def shutdown_analytics() -> None:
    try:
        if _state.client is not None:
            _state.client.flush()
            _state.client.shutdown()
    except Exception:
        logger.exception("Failed to shut down PostHog client")
    finally:
        _state.client = None


def capture_lifecycle_event(
    event: str,
    *,
    properties: dict[str, object] | None = None,
) -> None:
    if _state.client is None:
        return

    event_properties: dict[str, object] = {"service": _SERVICE}
    if properties:
        event_properties.update(properties)

    try:
        _state.client.capture(
            event,
            distinct_id=_DISTINCT_ID,
            properties=event_properties,
        )
    except Exception:
        logger.exception("Failed to capture PostHog lifecycle event")


def capture_tool_called(
    tool: str,
    duration_ms: float,
    *,
    success: bool,
    properties: dict[str, object] | None = None,
) -> None:
    if _state.client is None:
        return

    event_properties: dict[str, object] = {
        "service": _SERVICE,
        "tool": tool,
        "duration_ms": round(duration_ms, 2),
        "success": success,
    }
    if properties:
        event_properties.update(properties)

    try:
        _state.client.capture(
            "tool_called",
            distinct_id=_DISTINCT_ID,
            properties=event_properties,
        )
    except Exception:
        logger.exception("Failed to capture PostHog event")


def capture_exception(
    exc: BaseException,
    *,
    properties: dict[str, object] | None = None,
) -> None:
    if _state.client is None:
        return

    event_properties: dict[str, object] = {
        "service": _SERVICE,
        "error_type": type(exc).__name__,
        "message": str(exc),
        "traceback": "".join(
            traceback.format_exception(type(exc), exc, exc.__traceback__),
        ),
    }
    if properties:
        event_properties.update(properties)

    try:
        _state.client.capture(
            "tool_error",
            distinct_id=_DISTINCT_ID,
            properties=event_properties,
        )
    except Exception:
        logger.exception("Failed to capture PostHog exception")


def _arg_metadata(
    args: tuple[object, ...],
    kwargs: dict[str, object],
) -> dict[str, object]:
    # Tool arguments may contain user query text, so emit only lengths and counts.
    metadata: dict[str, object] = {"arg_count": len(args) + len(kwargs)}
    for name, value in kwargs.items():
        if isinstance(value, str):
            metadata[f"{name}_length"] = len(value)

    return metadata


def track_tool(
    tool: str,
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            start = time.perf_counter()
            success = True
            try:
                return await func(*args, **kwargs)
            except Exception as exc:
                success = False
                capture_exception(exc, properties={"tool": tool})
                raise
            finally:
                duration_ms = (time.perf_counter() - start) * 1000
                capture_tool_called(
                    tool,
                    duration_ms,
                    success=success,
                    properties=_arg_metadata(args, kwargs),
                )

        return wrapper

    return decorator
