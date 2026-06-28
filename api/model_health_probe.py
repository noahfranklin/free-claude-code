"""Proactive model health probing for the admin health-check endpoint.

Drives a tiny single-token generation against every discoverable model on each
credentialed provider, recording health so GET /v1/models can advertise only
verified-working models. Probing reuses the real provider generation primitives
(``preflight_stream`` + ``stream_response``) but bounds time per model and never
lets one model's failure abort the batch.
"""

from __future__ import annotations

import asyncio
from contextlib import suppress

from loguru import logger

from config.settings import Settings
from providers.runtime import ProviderRuntime, model_list_provider_ids_for_settings

from .model_health import ModelHealth
from .models.anthropic import Message, MessagesRequest


async def probe_model_health(
    *,
    settings: Settings,
    runtime: ProviderRuntime,
    health: ModelHealth,
) -> dict[str, object]:
    """Probe all discoverable provider models and record their health.

    Returns a per-provider ``{healthy, unhealthy, total}`` summary plus an
    overall total and the active ``model_list_mode``.
    """
    await runtime.refresh_model_list_cache(only_missing=True)
    provider_ids = model_list_provider_ids_for_settings(settings)
    cached = runtime.cached_model_ids()
    semaphore = asyncio.Semaphore(max(1, settings.model_health_probe_concurrency))

    async def probe_one(provider_id: str, model_id: str) -> tuple[str, bool]:
        async with semaphore:
            ok = await _probe_single(settings, runtime, health, provider_id, model_id)
        return provider_id, ok

    tasks: list[asyncio.Task[tuple[str, bool]]] = [
        asyncio.create_task(probe_one(provider_id, model_id))
        for provider_id in provider_ids
        for model_id in sorted(cached.get(provider_id, frozenset()))
    ]

    summary: dict[str, dict[str, int]] = {
        provider_id: {"healthy": 0, "unhealthy": 0, "total": 0}
        for provider_id in provider_ids
    }
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for result in results:
        if isinstance(result, BaseException):
            logger.warning(
                "Model health probe task failed: exc_type={}", type(result).__name__
            )
            continue
        provider_id, ok = result
        bucket = summary.setdefault(
            provider_id, {"healthy": 0, "unhealthy": 0, "total": 0}
        )
        bucket["total"] += 1
        bucket["healthy" if ok else "unhealthy"] += 1

    total = {
        "healthy": sum(bucket["healthy"] for bucket in summary.values()),
        "unhealthy": sum(bucket["unhealthy"] for bucket in summary.values()),
        "total": sum(bucket["total"] for bucket in summary.values()),
    }
    return {
        "providers": summary,
        "total": total,
        "model_list_mode": settings.model_list_mode,
    }


async def _probe_single(
    settings: Settings,
    runtime: ProviderRuntime,
    health: ModelHealth,
    provider_id: str,
    model_id: str,
) -> bool:
    """Probe one model; record and return its health. Never raises."""
    ref = f"{provider_id}/{model_id}"
    try:
        provider = runtime.resolve_provider(provider_id)
    except Exception as exc:
        health.mark_unhealthy(ref, type(exc).__name__)
        return False

    request = MessagesRequest(
        model=model_id,
        max_tokens=1,
        messages=[Message(role="user", content="ping")],
        stream=True,
    )
    try:
        provider.preflight_stream(request, thinking_enabled=False)
    except Exception as exc:
        health.mark_unhealthy(ref, type(exc).__name__)
        return False

    stream = provider.stream_response(request, input_tokens=1, thinking_enabled=False)
    try:
        async with asyncio.timeout(settings.model_health_probe_timeout):
            async for _chunk in stream:
                health.mark_healthy(ref)
                return True
        health.mark_unhealthy(ref, "empty_stream")
        return False
    except asyncio.CancelledError:
        raise
    except TimeoutError:
        health.mark_unhealthy(ref, "probe_timeout")
        return False
    except Exception as exc:
        health.mark_unhealthy(ref, type(exc).__name__)
        return False
    finally:
        aclose = getattr(stream, "aclose", None)
        if aclose is not None:
            with suppress(Exception):
                await aclose()
