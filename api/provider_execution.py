"""Shared provider execution primitive for API product handlers."""

from __future__ import annotations

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
    ) -> None:
        self._settings = settings
        self._provider_getter = provider_getter
        self._token_counter = token_counter
        self._model_health = model_health

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
        on_first_chunk: Callable[[], None] | None = None
        on_idle_timeout: Callable[[], None] | None = None
        if self._settings.model_health_enabled and health is not None:
            registry = health

            def _mark_first() -> None:
                registry.mark_healthy(ref)

            def _mark_idle() -> None:
                registry.mark_unhealthy(ref, "idle_timeout")

            on_first_chunk = _mark_first
            on_idle_timeout = _mark_idle

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

        if self._settings.model_health_enabled and health is not None:
            return self._mark_unhealthy_on_error(traced, health, ref)
        return traced

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
