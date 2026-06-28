"""Unit tests for the provider stream idle-timeout watchdog."""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncGenerator

import pytest

from core.anthropic.stream_watchdog import idle_timeout_stream


class _FakeRequest:
    """Minimal stand-in carrying the ``model`` attribute the helper reads."""

    model = "google/gemma-4-31b-it"


async def _never_yields() -> AsyncGenerator[str]:
    """Yield nothing, then block far longer than any test timeout."""
    if False:
        yield ""  # pragma: no cover - marks this as an async generator
    await asyncio.sleep(100)


async def _yields_then_ends(chunks: list[str]) -> AsyncGenerator[str]:
    for chunk in chunks:
        yield chunk


async def _one_chunk_then_stalls(chunk: str) -> AsyncGenerator[str]:
    yield chunk
    await asyncio.sleep(100)


@pytest.mark.asyncio
async def test_stall_before_any_chunk_emits_error_with_message_start() -> None:
    request = _FakeRequest()
    started = time.monotonic()
    events = [
        event
        async for event in idle_timeout_stream(
            _never_yields(),
            timeout_seconds=0.05,
            request=request,
            input_tokens=7,
            log_raw_sse_events=False,
        )
    ]
    elapsed = time.monotonic() - started

    assert elapsed < 5.0
    joined = "".join(events)
    # sent_any_event was False, so a message_start must open the error sequence.
    assert "event: message_start" in joined
    # The abort reason text is surfaced to the client.
    assert "sent no data" in joined
    assert "event: message_stop" in joined


@pytest.mark.asyncio
async def test_normal_stream_passes_through_without_error_events() -> None:
    request = _FakeRequest()
    payload = ["event: a\n\n", "event: b\n\n", "event: c\n\n"]
    events = [
        event
        async for event in idle_timeout_stream(
            _yields_then_ends(payload),
            timeout_seconds=0.5,
            request=request,
            input_tokens=3,
            log_raw_sse_events=False,
        )
    ]

    assert events == payload
    joined = "".join(events)
    assert "sent no data" not in joined
    assert "message_stop" not in joined


@pytest.mark.asyncio
async def test_stall_after_first_chunk_does_not_reemit_message_start() -> None:
    request = _FakeRequest()
    first = "event: message_start\ndata: {}\n\n"
    events = [
        event
        async for event in idle_timeout_stream(
            _one_chunk_then_stalls(first),
            timeout_seconds=0.05,
            request=request,
            input_tokens=5,
            log_raw_sse_events=False,
        )
    ]

    assert events[0] == first
    # Error events were appended after the real first chunk.
    appended = "".join(events[1:])
    assert "sent no data" in appended
    # sent_any_event was True: no second message_start in the appended sequence.
    assert "message_start" not in appended


@pytest.mark.asyncio
async def test_on_first_chunk_fires_once_on_normal_stream() -> None:
    request = _FakeRequest()
    first_calls: list[int] = []
    idle_calls: list[int] = []
    payload = ["a", "b", "c"]
    events = [
        event
        async for event in idle_timeout_stream(
            _yields_then_ends(payload),
            timeout_seconds=0.5,
            request=request,
            input_tokens=1,
            log_raw_sse_events=False,
            on_first_chunk=lambda: first_calls.append(1),
            on_idle_timeout=lambda: idle_calls.append(1),
        )
    ]

    assert events == payload
    assert sum(first_calls) == 1
    assert idle_calls == []


@pytest.mark.asyncio
async def test_on_idle_timeout_fires_when_watchdog_trips() -> None:
    request = _FakeRequest()
    first_calls: list[int] = []
    idle_calls: list[int] = []
    _ = [
        event
        async for event in idle_timeout_stream(
            _never_yields(),
            timeout_seconds=0.05,
            request=request,
            input_tokens=1,
            log_raw_sse_events=False,
            on_first_chunk=lambda: first_calls.append(1),
            on_idle_timeout=lambda: idle_calls.append(1),
        )
    ]

    assert first_calls == []
    assert sum(idle_calls) == 1


@pytest.mark.asyncio
async def test_first_chunk_then_idle_timeout_fires_both_callbacks_once() -> None:
    request = _FakeRequest()
    first_calls: list[int] = []
    idle_calls: list[int] = []
    _ = [
        event
        async for event in idle_timeout_stream(
            _one_chunk_then_stalls("event: only\n\n"),
            timeout_seconds=0.05,
            request=request,
            input_tokens=1,
            log_raw_sse_events=False,
            on_first_chunk=lambda: first_calls.append(1),
            on_idle_timeout=lambda: idle_calls.append(1),
        )
    ]

    assert sum(first_calls) == 1
    assert sum(idle_calls) == 1


@pytest.mark.asyncio
async def test_callbacks_optional_when_omitted() -> None:
    request = _FakeRequest()
    payload = ["a", "b"]
    events = [
        event
        async for event in idle_timeout_stream(
            _yields_then_ends(payload),
            timeout_seconds=0.5,
            request=request,
            input_tokens=1,
            log_raw_sse_events=False,
        )
    ]
    assert events == payload


@pytest.mark.asyncio
async def test_zero_timeout_disables_watchdog() -> None:
    request = _FakeRequest()
    pulled: list[str] = []
    gen = idle_timeout_stream(
        _one_chunk_then_stalls("event: only\n\n"),
        timeout_seconds=0,
        request=request,
        input_tokens=1,
        log_raw_sse_events=False,
    )
    # With the watchdog disabled the stall is never interrupted, so only pull a
    # bounded number of items to keep the test from hanging.
    pulled.append(await gen.__anext__())
    with pytest.raises(TimeoutError):
        await asyncio.wait_for(gen.__anext__(), 0.1)
    await gen.aclose()

    assert pulled == ["event: only\n\n"]
    # No error sequence was injected by the (disabled) watchdog.
    assert "sent no data" not in "".join(pulled)
