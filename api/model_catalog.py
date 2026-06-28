"""Model-list response construction for Claude-compatible clients."""

from __future__ import annotations

from dataclasses import dataclass

from config.model_refs import configured_chat_model_refs
from config.settings import Settings
from providers.runtime import ProviderRuntime

from .gateway_model_ids import gateway_model_id, no_thinking_gateway_model_id
from .model_health import ModelHealth
from .models.responses import ModelResponse, ModelsListResponse

DISCOVERED_MODEL_CREATED_AT = "1970-01-01T00:00:00Z"


SUPPORTED_CLAUDE_MODELS = [
    ModelResponse(
        id="claude-opus-4-20250514",
        display_name="Claude Opus 4",
        created_at="2025-05-14T00:00:00Z",
    ),
    ModelResponse(
        id="claude-sonnet-4-20250514",
        display_name="Claude Sonnet 4",
        created_at="2025-05-14T00:00:00Z",
    ),
    ModelResponse(
        id="claude-haiku-4-20250514",
        display_name="Claude Haiku 4",
        created_at="2025-05-14T00:00:00Z",
    ),
    ModelResponse(
        id="claude-3-opus-20240229",
        display_name="Claude 3 Opus",
        created_at="2024-02-29T00:00:00Z",
    ),
    ModelResponse(
        id="claude-3-5-sonnet-20241022",
        display_name="Claude 3.5 Sonnet",
        created_at="2024-10-22T00:00:00Z",
    ),
    ModelResponse(
        id="claude-3-haiku-20240307",
        display_name="Claude 3 Haiku",
        created_at="2024-03-07T00:00:00Z",
    ),
    ModelResponse(
        id="claude-3-5-haiku-20241022",
        display_name="Claude 3.5 Haiku",
        created_at="2024-10-22T00:00:00Z",
    ),
]


# Providers whose models are free to use (no per-token cost): NVIDIA NIM's
# integrate API and locally-hosted runtimes. OpenRouter flags zero-cost models
# with a ":free" model-id suffix instead.
_FREE_PROVIDER_IDS = frozenset({"nvidia_nim", "ollama", "lmstudio", "llamacpp"})


def is_free_model_ref(provider_model_ref: str) -> bool:
    """Return whether a ``provider/model`` ref is free to use."""
    provider_id = provider_model_ref.split("/", 1)[0]
    if provider_id in _FREE_PROVIDER_IDS:
        return True
    return provider_model_ref.endswith(":free")


@dataclass(frozen=True, slots=True)
class _ModelCandidate:
    """A unique listable provider model ref with thinking-capability metadata."""

    ref: str
    supports_thinking: bool | None


def build_models_list_response(
    settings: Settings,
    provider_runtime: ProviderRuntime | None,
    health: ModelHealth | None = None,
) -> ModelsListResponse:
    """Return configured, cached, and compatibility model ids.

    When ``health`` is provided and health tracking is enabled, discovered and
    configured provider models are filtered by their tracked health using
    ``settings.model_list_mode``. Under ``healthy_only`` the picker lists only
    verified-working models and fills in as the startup probe confirms them.
    Listable provider models are ranked so verified-working and free models lead
    the picker. The static ``SUPPORTED_CLAUDE_MODELS`` are always appended so
    routing and defaults keep working.
    """
    health_filter = health if settings.model_health_enabled else None
    mode = settings.model_list_mode

    candidates: list[_ModelCandidate] = []
    seen_refs: set[str] = set()

    def add_candidate(ref: str, supports_thinking: bool | None) -> None:
        if ref in seen_refs:
            return
        if health_filter is not None and not health_filter.is_listable(ref, mode=mode):
            return
        seen_refs.add(ref)
        candidates.append(_ModelCandidate(ref, supports_thinking))

    for ref in configured_chat_model_refs(settings):
        supports_thinking = None
        if provider_runtime is not None:
            supports_thinking = provider_runtime.cached_model_supports_thinking(
                ref.provider_id, ref.model_id
            )
        add_candidate(ref.model_ref, supports_thinking)

    if provider_runtime is not None:
        for model_info in provider_runtime.cached_prefixed_model_infos():
            add_candidate(model_info.model_id, model_info.supports_thinking)

    candidates.sort(key=lambda candidate: _rank_key(candidate.ref, health_filter))

    models: list[ModelResponse] = []
    seen: set[str] = set()
    for candidate in candidates:
        _append_provider_model_variants(
            models,
            seen,
            candidate.ref,
            supports_thinking=candidate.supports_thinking,
        )

    for model in SUPPORTED_CLAUDE_MODELS:
        _append_unique_model(models, seen, model)

    return ModelsListResponse(
        data=models,
        first_id=models[0].id if models else None,
        has_more=False,
        last_id=models[-1].id if models else None,
    )


def _rank_key(
    provider_model_ref: str, health: ModelHealth | None
) -> tuple[int, int, str]:
    """Sort key placing verified-working, then free, then alphabetical refs first."""
    healthy = health is not None and health.is_healthy(provider_model_ref)
    free = is_free_model_ref(provider_model_ref)
    return (0 if healthy else 1, 0 if free else 1, provider_model_ref)


def _discovered_model_response(model_id: str, *, display_name: str) -> ModelResponse:
    return ModelResponse(
        id=model_id,
        display_name=display_name,
        created_at=DISCOVERED_MODEL_CREATED_AT,
    )


def _append_unique_model(
    models: list[ModelResponse], seen: set[str], model: ModelResponse
) -> None:
    if model.id in seen:
        return
    seen.add(model.id)
    models.append(model)


def _append_provider_model_variants(
    models: list[ModelResponse],
    seen: set[str],
    provider_model_ref: str,
    *,
    supports_thinking: bool | None = None,
) -> None:
    if supports_thinking is not False:
        _append_unique_model(
            models,
            seen,
            _discovered_model_response(
                gateway_model_id(provider_model_ref),
                display_name=provider_model_ref,
            ),
        )
    _append_unique_model(
        models,
        seen,
        _discovered_model_response(
            no_thinking_gateway_model_id(provider_model_ref),
            display_name=f"{provider_model_ref} (no thinking)",
        ),
    )
