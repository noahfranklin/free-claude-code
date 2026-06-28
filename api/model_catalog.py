"""Model-list response construction for Claude-compatible clients."""

from __future__ import annotations

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


def build_models_list_response(
    settings: Settings,
    provider_runtime: ProviderRuntime | None,
    health: ModelHealth | None = None,
) -> ModelsListResponse:
    """Return configured, cached, and compatibility model ids.

    When ``health`` is provided and health tracking is enabled, discovered and
    configured provider models are filtered by their tracked health using
    ``settings.model_list_mode``. The static ``SUPPORTED_CLAUDE_MODELS`` are
    always included so routing and defaults keep working.
    """
    models: list[ModelResponse] = []
    seen: set[str] = set()

    health_filter = health if settings.model_health_enabled else None

    for ref in configured_chat_model_refs(settings):
        if not _ref_is_listable(health_filter, settings, ref.model_ref):
            continue
        supports_thinking = None
        if provider_runtime is not None:
            supports_thinking = provider_runtime.cached_model_supports_thinking(
                ref.provider_id, ref.model_id
            )
        _append_provider_model_variants(
            models,
            seen,
            ref.model_ref,
            supports_thinking=supports_thinking,
        )

    if provider_runtime is not None:
        for model_info in provider_runtime.cached_prefixed_model_infos():
            if not _ref_is_listable(health_filter, settings, model_info.model_id):
                continue
            _append_provider_model_variants(
                models,
                seen,
                model_info.model_id,
                supports_thinking=model_info.supports_thinking,
            )

    for model in SUPPORTED_CLAUDE_MODELS:
        _append_unique_model(models, seen, model)

    return ModelsListResponse(
        data=models,
        first_id=models[0].id if models else None,
        has_more=False,
        last_id=models[-1].id if models else None,
    )


def _ref_is_listable(
    health: ModelHealth | None, settings: Settings, provider_model_ref: str
) -> bool:
    if health is None:
        return True
    return health.is_listable(provider_model_ref, mode=settings.model_list_mode)


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
