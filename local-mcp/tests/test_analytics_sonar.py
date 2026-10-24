import asyncio
import inspect
from collections.abc import Awaitable, Callable
from typing import assert_type
from unittest.mock import Mock

import pytest

from app.utils import analytics


def test_track_tool_preserves_signature_result_and_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    capture = Mock()
    capture_error = Mock()
    monkeypatch.setattr(analytics, "capture_tool_called", capture)
    monkeypatch.setattr(analytics, "capture_exception", capture_error)
    monkeypatch.setattr(analytics.time, "perf_counter", Mock(side_effect=[1.0, 1.25]))

    async def original(count: int, *, query: str) -> int:
        """Original documentation."""
        return count + len(query)

    tracked = analytics.track_tool("lookup")(original)
    result = tracked(2, query="private")
    assert_type(result, Awaitable[int])
    assert asyncio.run(_await_result(result)) == 9
    assert tracked.__name__ == original.__name__
    assert tracked.__doc__ == original.__doc__
    assert inspect.signature(tracked) == inspect.signature(original)
    capture.assert_called_once_with(
        "lookup",
        250.0,
        success=True,
        properties={"arg_count": 2, "query_length": 7},
    )
    capture_error.assert_not_called()


async def _await_result[R](result: Awaitable[R]) -> R:
    return await result


def test_track_tool_reraises_original_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    capture = Mock()
    capture_error = Mock()
    monkeypatch.setattr(analytics, "capture_tool_called", capture)
    monkeypatch.setattr(analytics, "capture_exception", capture_error)
    monkeypatch.setattr(analytics.time, "perf_counter", Mock(side_effect=[2.0, 2.5]))
    error = ValueError("failure")

    @analytics.track_tool("failure")
    async def failing() -> None:
        raise error

    result = _await_result(failing())
    with pytest.raises(ValueError, match="failure") as caught:
        asyncio.run(result)
    assert caught.value is error
    capture_error.assert_called_once_with(error, properties={"tool": "failure"})
    capture.assert_called_once_with(
        "failure",
        500.0,
        success=False,
        properties={"arg_count": 0},
    )


def test_track_tool_generic_types() -> None:
    def preserves_types[**P, R](
        function: Callable[P, Awaitable[R]],
    ) -> Callable[P, Awaitable[R]]:
        return analytics.track_tool("typed")(function)

    assert callable(preserves_types)
    assert tuple(
        parameter.__name__ for parameter in analytics.track_tool.__type_params__
    ) == (
        "P",
        "R",
    )
