"""Shared provider execution primitive for API product handlers."""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator, Callable
from typing import Any

from loguru import logger

from config.settings import Settings
from core.anthropic import get_token_count
from core.anthropic.stream_watchdog import idle_timeout_stream
from core.trace import api_messages_request_snapshot, trace_event, traced_async_stream
from providers.base import BaseProvider

from .model_health import ModelHealth
from .model_router import RoutedMessagesRequest
from .usage import Usage

TokenCounter = Callable[[list[Any], str | list[Any] | None, list[Any] | None], int]
ProviderGetter = Callable[[str], BaseProvider]


class ProviderExecutionService:
    """Resolve a provider and execute one routed Anthropic Messages stream."""

    def __init__(
        self,
        settings: Settings,
        provider_getter: ProviderGetter,
        *,
        token_counter: TokenCounter = get_token_count,
        model_health: ModelHealth | None = None,
        usage: Usage | None = None,
    ) -> None:
        self._settings = settings
        self._provider_getter = provider_getter
        self._token_counter = token_counter
        self._model_health = model_health
        self._usage = usage

    def stream(
        self,
        routed: RoutedMessagesRequest,
        *,
        wire_api: str,
        raw_log_label: str,
        raw_log_payload: Any,
    ) -> AsyncIterator[str]:
        provider = self._provider_getter(routed.resolved.provider_id)
        provider.preflight_stream(
            routed.request,
            thinking_enabled=routed.resolved.thinking_enabled,
        )

        route_trace: dict[str, Any] = {
            "stage": "routing",
            "event": "api.route.resolved",
            "source": "api",
            "provider_id": routed.resolved.provider_id,
            "provider_model": routed.resolved.provider_model,
            "provider_model_ref": routed.resolved.provider_model_ref,
            "gateway_model": routed.request.model,
            "thinking_enabled": routed.resolved.thinking_enabled,
        }
        if wire_api == "responses":
            route_trace["wire_api"] = "responses"
        trace_event(**route_trace)

        request_id = f"req_{uuid.uuid4().hex[:12]}"
        trace_event(
            stage="ingress",
            event=(
                "api.responses.request.received"
                if wire_api == "responses"
                else "api.request.received"
            ),
            source="api",
            message_count=len(routed.request.messages),
            snapshot=api_messages_request_snapshot(routed.request),
            request_id=request_id,
        )

        if self._settings.log_raw_api_payloads:
            logger.debug(f"{raw_log_label} [{{}}]: {{}}", request_id, raw_log_payload)

        input_tokens = self._token_counter(
            routed.request.messages,
            routed.request.system,
            routed.request.tools,
        )

        health = self._model_health
        ref = routed.resolved.canonical_model_ref
        idle_state = {"hit": False}

        def _on_first_chunk() -> None:
            if self._settings.model_health_enabled and health is not None:
                health.mark_healthy(ref)

        def _on_idle_timeout() -> None:
            idle_state["hit"] = True
            if self._settings.model_health_enabled and health is not None:
                health.mark_unhealthy(ref, "idle_timeout")

        health_active = self._settings.model_health_enabled and health is not None
        needs_callbacks = health_active or self._usage is not None
        on_first_chunk: Callable[[], None] | None = (
            _on_first_chunk if needs_callbacks else None
        )
        on_idle_timeout: Callable[[], None] | None = (
            _on_idle_timeout if needs_callbacks else None
        )

        traced = traced_async_stream(
            idle_timeout_stream(
                provider.stream_response(
                    routed.request,
                    input_tokens=input_tokens,
                    request_id=request_id,
                    thinking_enabled=routed.resolved.thinking_enabled,
                ),
                timeout_seconds=self._settings.http_stream_idle_timeout,
                request=routed.request,
                input_tokens=input_tokens,
                log_raw_sse_events=self._settings.log_raw_sse_events,
                on_first_chunk=on_first_chunk,
                on_idle_timeout=on_idle_timeout,
            ),
            stage="egress",
            source="api",
            complete_event=(
                "api.responses.stream_completed"
                if wire_api == "responses"
                else "api.response.stream_completed"
            ),
            interrupted_event=(
                "api.responses.stream_interrupted"
                if wire_api == "responses"
                else "api.response.stream_interrupted"
            ),
            chunk_event=None,
            extra={
                "request_id": request_id,
                "provider_id": routed.resolved.provider_id,
                "gateway_model": routed.request.model,
            },
        )

        result: AsyncIterator[str] = traced
        if self._settings.model_health_enabled and health is not None:
            result = self._mark_unhealthy_on_error(result, health, ref)
        if self._usage is not None:
            result = self._record_usage(
                result,
                usage=self._usage,
                provider_id=routed.resolved.provider_id,
                model=routed.resolved.provider_model_ref,
                input_tokens=input_tokens,
                idle_state=idle_state,
            )
        return result

    @staticmethod
    async def _mark_unhealthy_on_error(
        source: AsyncIterator[str], health: ModelHealth, ref: str
    ) -> AsyncIterator[str]:
        """Demote a model when its provider stream raises before/while streaming."""
        try:
            async for chunk in source:
                yield chunk
        except Exception as exc:
            health.mark_unhealthy(ref, type(exc).__name__)
            raise

    @staticmethod
    async def _record_usage(
        source: AsyncIterator[str],
        *,
        usage: Usage,
        provider_id: str,
        model: str,
        input_tokens: int,
        idle_state: dict[str, bool],
    ) -> AsyncIterator[str]:
        """Record exactly one usage entry per request.

        ``tokens_out`` is a best-effort approximation: the total character length
        of all streamed SSE chunks divided by 4 (a rough chars-per-token ratio),
        since provider streams do not uniformly expose a usage event here.
        Latency is first-token latency (request start to first streamed chunk),
        falling back to total stream duration if nothing was streamed.
        """
        start = time.monotonic()
        first_latency_ms: float | None = None
        text_len = 0
        recorded = False

        def _elapsed_ms() -> float:
            if first_latency_ms is not None:
                return first_latency_ms
            return (time.monotonic() - start) * 1000.0

        try:
            async for chunk in source:
                if first_latency_ms is None:
                    first_latency_ms = (time.monotonic() - start) * 1000.0
                text_len += len(chunk)
                yield chunk
        except Exception as exc:
            usage.record(
                provider_id=provider_id,
                model=model,
                tokens_in=input_tokens,
                tokens_out=text_len // 4,
                status="error",
                latency_ms=_elapsed_ms(),
                error_reason=type(exc).__name__,
            )
            recorded = True
            raise
        finally:
            if not recorded:
                idle = idle_state["hit"]
                usage.record(
                    provider_id=provider_id,
                    model=model,
                    tokens_in=input_tokens,
                    tokens_out=text_len // 4,
                    status="error" if idle else "ok",
                    latency_ms=_elapsed_ms(),
                    error_reason="idle_timeout" if idle else "",
                )
