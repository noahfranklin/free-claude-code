"""Tests for GET /v1/models filtering by tracked model health."""

from __future__ import annotations

from api.model_catalog import build_models_list_response
from api.model_health import ModelHealth
from config.settings import Settings
from providers.runtime import ProviderRuntime


def _settings(*, mode: str = "exclude_unhealthy", enabled: bool = True) -> Settings:
    return Settings.model_construct(
        model="deepseek/deepseek-chat",
        model_opus=None,
        model_sonnet=None,
        model_haiku=None,
        anthropic_auth_token="",
        model_health_enabled=enabled,
        model_list_mode=mode,
    )


def _runtime(settings: Settings) -> ProviderRuntime:
    runtime = ProviderRuntime(settings)
    runtime.cache_model_ids("deepseek", {"deepseek-chat", "deepseek-reasoner"})
    return runtime


def _ids(
    settings: Settings, runtime: ProviderRuntime, health: ModelHealth
) -> list[str]:
    response = build_models_list_response(settings, runtime, health)
    return [item.id for item in response.data]


def test_unhealthy_ref_excluded_under_exclude_unhealthy() -> None:
    settings = _settings(mode="exclude_unhealthy")
    runtime = _runtime(settings)
    health = ModelHealth(cooldown_seconds=600.0)
    health.mark_unhealthy("deepseek/deepseek-reasoner", "idle_timeout")

    ids = _ids(settings, runtime, health)
    assert "anthropic/deepseek/deepseek-reasoner" not in ids
    assert "claude-3-freecc-no-thinking/deepseek/deepseek-reasoner" not in ids
    # Healthy/unknown sibling still listed.
    assert "anthropic/deepseek/deepseek-chat" in ids


def test_unhealthy_ref_included_under_all() -> None:
    settings = _settings(mode="all")
    runtime = _runtime(settings)
    health = ModelHealth(cooldown_seconds=600.0)
    health.mark_unhealthy("deepseek/deepseek-reasoner", "idle_timeout")

    ids = _ids(settings, runtime, health)
    assert "anthropic/deepseek/deepseek-reasoner" in ids


def test_only_healthy_under_healthy_only() -> None:
    settings = _settings(mode="healthy_only")
    runtime = _runtime(settings)
    health = ModelHealth(cooldown_seconds=600.0)
    health.mark_healthy("deepseek/deepseek-chat")
    # deepseek-reasoner is UNKNOWN (never probed) -> hidden under healthy_only.

    ids = _ids(settings, runtime, health)
    assert "anthropic/deepseek/deepseek-chat" in ids
    assert "anthropic/deepseek/deepseek-reasoner" not in ids


def test_supported_claude_models_always_present_even_when_unhealthy() -> None:
    settings = _settings(mode="healthy_only")
    runtime = _runtime(settings)
    health = ModelHealth(cooldown_seconds=600.0)
    # Nothing marked healthy: every discovered model is hidden under healthy_only.
    ids = _ids(settings, runtime, health)
    assert "anthropic/deepseek/deepseek-chat" not in ids
    assert "claude-sonnet-4-20250514" in ids
    assert "claude-opus-4-20250514" in ids


def test_disabled_health_lists_everything() -> None:
    settings = _settings(mode="healthy_only", enabled=False)
    runtime = _runtime(settings)
    health = ModelHealth(cooldown_seconds=600.0)
    health.mark_unhealthy("deepseek/deepseek-chat", "boom")

    ids = _ids(settings, runtime, health)
    # Health disabled -> no filtering regardless of mode or recorded health.
    assert "anthropic/deepseek/deepseek-chat" in ids
    assert "anthropic/deepseek/deepseek-reasoner" in ids
