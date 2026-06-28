"""Idle-timeout watchdog for provider SSE streams.

Guards against an upstream provider that accepts a request but then sends no
data: instead of blocking on the socket until ``HTTP_READ_TIMEOUT``, abort fast
and emit a clean Anthropic SSE error sequence.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, AsyncIterator, Callable
from contextlib import suppress
from typing import Any

from core.anthropic.provider_stream_error import (
    iter_provider_stream_error_sse_events,
)


async def idle_timeout_stream(
    source: AsyncIterator[str],
    *,
    timeout_seconds: float,
    request: Any,
    input_tokens: int,
    log_raw_sse_events: bool,
    on_first_chunk: Callable[[], None] | None = None,
    on_idle_timeout: Callable[[], None] | None = None,
) -> AsyncGenerator[str]:
    """Yield chunks from ``source``, aborting if it stalls past ``timeout_seconds``.

    When no chunk arrives within ``timeout_seconds``, the upstream iterator is
    closed best-effort and a canonical Anthropic SSE error sequence is emitted.
    A non-positive ``timeout_seconds`` disables the watchdog (pass-through).

    ``on_first_chunk`` is invoked once, when the first chunk is yielded from
    ``source``. ``on_idle_timeout`` is invoked if the watchdog trips. These
    neutral callbacks let callers record stream health without coupling the core
    to any application registry.
    """
    if timeout_seconds <= 0:
        first = True
        async for chunk in source:
            if first:
                first = False
                if on_first_chunk is not None:
                    on_first_chunk()
            yield chunk
        return

    it = source.__aiter__()
    sent_any = False
    while True:
        try:
            chunk = await asyncio.wait_for(it.__anext__(), timeout_seconds)
        except StopAsyncIteration:
            return
        except TimeoutError:
            if on_idle_timeout is not None:
                on_idle_timeout()
            aclose = getattr(it, "aclose", None)
            if aclose is not None:
                with suppress(Exception):
                    await aclose()
            error_message = (
                f"Upstream provider sent no data for {timeout_seconds:g}s; "
                "aborting. The selected model may be unavailable or not "
                "responding — try a different model."
            )
            for ev in iter_provider_stream_error_sse_events(
                request=request,
                input_tokens=input_tokens,
                error_message=error_message,
                sent_any_event=sent_any,
                log_raw_sse_events=log_raw_sse_events,
            ):
                yield ev
            return
        if not sent_any and on_first_chunk is not None:
            on_first_chunk()
        sent_any = True
        yield chunk
