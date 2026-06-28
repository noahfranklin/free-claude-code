"""Tests for GET /v1/models filtering by tracked model health."""

from __future__ import annotations

from api.model_catalog import build_models_list_response, is_free_model_ref
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


def test_is_free_model_ref_free_provider_and_suffix_vs_paid() -> None:
    # Free-provider ids (NVIDIA NIM integrate API, local runtimes) are free.
    assert is_free_model_ref("nvidia_nim/google/gemma-2-2b-it") is True
    assert is_free_model_ref("ollama/llama3") is True
    assert is_free_model_ref("lmstudio/qwen") is True
    assert is_free_model_ref("llamacpp/phi") is True
    # OpenRouter flags zero-cost models with a ":free" suffix.
    assert is_free_model_ref("deepseek/deepseek-r1:free") is True
    # Paid provider model is not free.
    assert is_free_model_ref("deepseek/deepseek-chat") is False


def test_healthy_only_is_strict_regardless_of_initial_probe_complete() -> None:
    settings = _settings(mode="healthy_only")
    runtime = _runtime(settings)
    health = ModelHealth(cooldown_seconds=600.0)
    health.mark_healthy("deepseek/deepseek-chat")
    # deepseek-reasoner stays UNKNOWN (never probed).

    # healthy_only is strict immediately: UNKNOWN provider models are hidden even
    # before the first probe sweep finishes. Static Claude models stay present.
    assert health.initial_probe_complete is False
    ids_before = _ids(settings, runtime, health)
    assert "anthropic/deepseek/deepseek-chat" in ids_before
    assert "anthropic/deepseek/deepseek-reasoner" not in ids_before
    assert "claude-sonnet-4-20250514" in ids_before

    # Marking the initial probe complete is a status flag only; it does not
    # change which models are listed.
    health.mark_initial_probe_complete()
    ids_after = _ids(settings, runtime, health)
    assert ids_after == ids_before


def _provider_ref_order(ids: list[str]) -> list[str]:
    """Return discovered provider refs in list order (ignoring Claude statics)."""
    order: list[str] = []
    for model_id in ids:
        prefix = "anthropic/"
        if not model_id.startswith(prefix):
            continue
        ref = model_id[len(prefix) :]
        if ref not in order:
            order.append(ref)
    return order


def test_ranking_healthy_then_free_then_alpha() -> None:
    # mode="all" keeps every model listable so we observe pure ranking order.
    settings = _settings(mode="all")
    runtime = ProviderRuntime(settings)
    runtime.cache_model_ids("deepseek", {"deepseek-chat", "deepseek-reasoner"})
    runtime.cache_model_ids("nvidia_nim", {"zeta"})
    runtime.cache_model_ids("open_router", {"alpha:free"})
    runtime.cache_model_ids("mistral", {"big"})

    health = ModelHealth(cooldown_seconds=600.0)
    health.mark_healthy("deepseek/deepseek-chat")  # paid but verified-healthy
    health.mark_unhealthy("mistral/big", "boom")  # cooldown; still listed under "all"

    ids = _ids(settings, runtime, health)
    order = _provider_ref_order(ids)
    assert order == [
        "deepseek/deepseek-chat",  # healthy leads, regardless of paid/free
        "nvidia_nim/zeta",  # then free models, alphabetical among themselves
        "open_router/alpha:free",
        "deepseek/deepseek-reasoner",  # then paid/unknown, alphabetical
        "mistral/big",
    ]


def test_disabled_health_lists_everything() -> None:
    settings = _settings(mode="healthy_only", enabled=False)
    runtime = _runtime(settings)
    health = ModelHealth(cooldown_seconds=600.0)
    health.mark_unhealthy("deepseek/deepseek-chat", "boom")

    ids = _ids(settings, runtime, health)
    # Health disabled -> no filtering regardless of mode or recorded health.
    assert "anthropic/deepseek/deepseek-chat" in ids
    assert "anthropic/deepseek/deepseek-reasoner" in ids
