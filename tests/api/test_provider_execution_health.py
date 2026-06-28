"""Reactive model-health recording in the shared provider execution service."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest

from api.model_health import ModelHealth, ModelHealthStatus
from api.model_router import ResolvedModel, RoutedMessagesRequest
from api.models.anthropic import Message, MessagesRequest
from api.provider_execution import ProviderExecutionService
from config.settings import Settings
from providers.base import BaseProvider, ProviderConfig
from providers.exceptions import ProviderError


class _FakeProvider(BaseProvider):
    """Minimal provider exposing the surface ProviderExecutionService calls."""

    def __init__(
        self, chunks: list[str] | None = None, raise_exc: Exception | None = None
    ) -> None:
        super().__init__(ProviderConfig(api_key="x"))
        self._chunks = chunks or []
        self._raise_exc = raise_exc

    async def cleanup(self) -> None:
        return None

    async def list_model_ids(self) -> frozenset[str]:
        return frozenset()

    async def stream_response(
        self,
        request: Any,
        input_tokens: int = 0,
        *,
        request_id: str | None = None,
        thinking_enabled: bool | None = None,
    ) -> AsyncIterator[str]:
        if self._raise_exc is not None:
            raise self._raise_exc
        for chunk in self._chunks:
            yield chunk


def _settings(*, enabled: bool = True) -> Settings:
    return Settings.model_construct(
        model="deepseek/deepseek-chat",
        anthropic_auth_token="",
        log_raw_api_payloads=False,
        log_raw_sse_events=False,
        http_stream_idle_timeout=5.0,
        model_health_enabled=enabled,
    )


def _routed() -> RoutedMessagesRequest:
    request = MessagesRequest(
        model="deepseek-chat",
        max_tokens=8,
        messages=[Message(role="user", content="hi")],
    )
    resolved = ResolvedModel(
        original_model="deepseek/deepseek-chat",
        provider_id="deepseek",
        provider_model="deepseek-chat",
        provider_model_ref="deepseek/deepseek-chat",
        thinking_enabled=False,
    )
    return RoutedMessagesRequest(request=request, resolved=resolved)


def _service(provider: _FakeProvider, settings: Settings, health: ModelHealth):
    return ProviderExecutionService(
        settings,
        provider_getter=lambda _pid: provider,
        token_counter=lambda *_args: 0,
        model_health=health,
    )


@pytest.mark.asyncio
async def test_successful_stream_marks_healthy() -> None:
    provider = _FakeProvider(chunks=["event: a\n\n", "event: b\n\n"])
    settings = _settings()
    health = ModelHealth(cooldown_seconds=600.0)
    service = _service(provider, settings, health)

    chunks = [
        chunk
        async for chunk in service.stream(
            _routed(),
            wire_api="messages",
            raw_log_label="X",
            raw_log_payload={},
        )
    ]

    assert chunks == ["event: a\n\n", "event: b\n\n"]
    assert health.status("deepseek/deepseek-chat") is ModelHealthStatus.HEALTHY


@pytest.mark.asyncio
async def test_provider_error_marks_unhealthy_and_reraises() -> None:
    provider = _FakeProvider(raise_exc=ProviderError("boom"))
    settings = _settings()
    health = ModelHealth(cooldown_seconds=600.0)
    service = _service(provider, settings, health)

    with pytest.raises(ProviderError):
        async for _chunk in service.stream(
            _routed(),
            wire_api="messages",
            raw_log_label="X",
            raw_log_payload={},
        ):
            pass

    status = health.status("deepseek/deepseek-chat")
    assert status is ModelHealthStatus.UNHEALTHY
    assert health.snapshot()["deepseek/deepseek-chat"]["reason"] == "ProviderError"


@pytest.mark.asyncio
async def test_disabled_health_records_nothing() -> None:
    provider = _FakeProvider(chunks=["event: a\n\n"])
    settings = _settings(enabled=False)
    health = ModelHealth(cooldown_seconds=600.0)
    service = _service(provider, settings, health)

    _ = [
        chunk
        async for chunk in service.stream(
            _routed(),
            wire_api="messages",
            raw_log_label="X",
            raw_log_payload={},
        )
    ]

    assert health.status("deepseek/deepseek-chat") is ModelHealthStatus.UNKNOWN
