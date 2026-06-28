"""Local admin UI routes and APIs."""

from __future__ import annotations

import inspect
import ipaddress
import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from config.model_refs import parse_provider_type
from config.settings import Settings
from config.settings import get_settings as get_cached_settings
from providers.exceptions import ProviderError
from providers.runtime import ProviderRuntime

from .admin_config.manifest import FIELD_BY_KEY
from .admin_config.persistence import validate_updates, write_managed_env
from .admin_config.status import provider_config_status
from .admin_config.values import load_config_response
from .admin_urls import local_admin_url
from .dependencies import maybe_model_health, maybe_provider_runtime, maybe_usage
from .model_catalog import build_models_list_response
from .model_health import ModelHealth
from .model_health_probe import probe_model_health
from .models.anthropic import MessagesRequest
from .response_streams import anthropic_sse_streaming_response
from .routes import build_messages_handler
from .usage import Usage

router = APIRouter()

STATIC_DIR = Path(__file__).resolve().parent / "admin_static"
LOCAL_PROVIDER_PATHS = {
    "lmstudio": "/models",
    "llamacpp": "/models",
    "ollama": "/api/tags",
}


DEFAULT_CHAT_MAX_TOKENS = 4096

USAGE_RANGE_SECONDS: dict[str, int] = {
    "1h": 60 * 60,
    "24h": 24 * 60 * 60,
    "7d": 7 * 24 * 60 * 60,
}
DEFAULT_USAGE_RANGE = "24h"


class AdminConfigPayload(BaseModel):
    """Partial config update submitted by the admin UI."""

    values: dict[str, Any] = Field(default_factory=dict)


class AdminChatMessage(BaseModel):
    """A single turn in the admin chat conversation."""

    role: Literal["user", "assistant"]
    content: str


class AdminChatPayload(BaseModel):
    """Chat request submitted by the local admin Chat view."""

    model: str
    messages: list[AdminChatMessage]
    max_tokens: int | None = None


def _is_loopback_host(host: str | None) -> bool:
    if host is None:
        return False
    normalized = host.strip().strip("[]").lower()
    if normalized == "localhost":
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def _origin_is_local(origin: str | None) -> bool:
    if not origin:
        return True
    parsed = urlsplit(origin)
    return _is_loopback_host(parsed.hostname)


def require_loopback_admin(request: Request) -> None:
    """Allow admin access only from the local machine."""

    client_host = request.client.host if request.client else None
    if not _is_loopback_host(client_host):
        raise HTTPException(status_code=403, detail="Admin UI is local-only")

    origin = request.headers.get("origin")
    if not _origin_is_local(origin):
        raise HTTPException(status_code=403, detail="Admin UI is local-only")


def _asset_response(filename: str) -> FileResponse:
    path = STATIC_DIR / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Admin asset not found")
    return FileResponse(path)


@router.get("/admin", include_in_schema=False)
async def admin_page(request: Request):
    require_loopback_admin(request)
    return _asset_response("index.html")


@router.get("/admin/assets/{filename}", include_in_schema=False)
async def admin_asset(filename: str, request: Request):
    require_loopback_admin(request)
    if filename not in {"admin.css", "admin.js"}:
        raise HTTPException(status_code=404, detail="Admin asset not found")
    return _asset_response(filename)


@router.get("/admin/assets/vendor/{filename}", include_in_schema=False)
async def admin_vendor_asset(filename: str, request: Request):
    require_loopback_admin(request)
    if filename != "chart.umd.min.js":
        raise HTTPException(status_code=404, detail="Admin asset not found")
    return _asset_response(f"vendor/{filename}")


@router.get("/admin/api/config")
async def get_admin_config(request: Request):
    require_loopback_admin(request)
    return load_config_response()


@router.post("/admin/api/config/validate")
async def validate_admin_config(payload: AdminConfigPayload, request: Request):
    require_loopback_admin(request)
    return validate_updates(_filtered_values(payload.values))


@router.post("/admin/api/config/apply")
async def apply_admin_config(
    payload: AdminConfigPayload,
    request: Request,
    background_tasks: BackgroundTasks,
):
    require_loopback_admin(request)
    result = write_managed_env(_filtered_values(payload.values))
    if not result["applied"]:
        return result

    get_cached_settings.cache_clear()
    restart = _restart_metadata(result["pending_fields"], request)
    result["restart"] = restart
    if restart["required"] and restart["automatic"]:
        callback = request.app.state.admin_restart_callback
        background_tasks.add_task(_invoke_admin_restart_callback, callback)
        request.app.state.admin_pending_fields = []
        return result

    old_runtime = getattr(request.app.state, "provider_runtime", None)
    if isinstance(old_runtime, ProviderRuntime):
        await old_runtime.cleanup()
    request.app.state.provider_runtime = ProviderRuntime(get_cached_settings())
    request.app.state.admin_pending_fields = result["pending_fields"]
    return result


@router.post("/admin/api/chat")
async def admin_chat(payload: AdminChatPayload, request: Request):
    require_loopback_admin(request)
    settings = get_cached_settings()
    handler = build_messages_handler(request, settings)
    messages_request = MessagesRequest.model_validate(
        {
            "model": payload.model,
            "messages": [
                {"role": message.role, "content": message.content}
                for message in payload.messages
            ],
            "max_tokens": payload.max_tokens or DEFAULT_CHAT_MAX_TOKENS,
            "stream": True,
        }
    )
    try:
        return handler.create(messages_request)
    except (ProviderError, HTTPException) as exc:
        return anthropic_sse_streaming_response(_chat_error_stream(exc))


def _chat_error_message(exc: Exception) -> str:
    if isinstance(exc, HTTPException):
        return str(exc.detail)
    message = getattr(exc, "message", None)
    return message if isinstance(message, str) and message else str(exc) or "error"


async def _chat_error_stream(exc: Exception) -> AsyncIterator[str]:
    payload = {
        "type": "error",
        "error": {"type": type(exc).__name__, "message": _chat_error_message(exc)},
    }
    yield f"event: error\ndata: {json.dumps(payload)}\n\n"


@router.get("/admin/api/status")
async def admin_status(request: Request):
    require_loopback_admin(request)
    settings = get_cached_settings()
    runtime = getattr(request.app.state, "provider_runtime", None)
    cached_models: dict[str, list[str]] = {}
    if isinstance(runtime, ProviderRuntime):
        cached_models = {
            provider_id: sorted(model_ids)
            for provider_id, model_ids in runtime.cached_model_ids().items()
        }
    return {
        "status": "running",
        "host": settings.host,
        "port": settings.port,
        "model": settings.model,
        "provider": parse_provider_type(settings.model),
        "pending_fields": getattr(request.app.state, "admin_pending_fields", []),
        "provider_status": provider_config_status(),
        "cached_models": cached_models,
    }


@router.get("/admin/api/providers/local-status")
async def local_provider_status(request: Request):
    require_loopback_admin(request)
    config = load_config_response()
    values = {field["key"]: field["value"] for field in config["fields"]}
    checks = []
    for provider_id, path in LOCAL_PROVIDER_PATHS.items():
        base_url = _local_provider_url(provider_id, values)
        checks.append(await _check_local_provider(provider_id, base_url, path))
    return {"providers": checks}


@router.post("/admin/api/providers/{provider_id}/test")
async def test_provider(provider_id: str, request: Request):
    require_loopback_admin(request)
    settings = get_cached_settings()
    runtime = _provider_runtime_for_admin(request, settings)
    try:
        provider = runtime.resolve_provider(provider_id)
        infos = await provider.list_model_infos()
    except Exception as exc:
        return {
            "provider_id": provider_id,
            "ok": False,
            "error_type": type(exc).__name__,
        }
    runtime.cache_model_infos(provider_id, infos)
    return {
        "provider_id": provider_id,
        "ok": True,
        "models": sorted(info.model_id for info in infos),
    }


@router.post("/admin/api/models/refresh")
async def refresh_models(request: Request):
    require_loopback_admin(request)
    settings = get_cached_settings()
    runtime = _provider_runtime_for_admin(request, settings)
    await runtime.refresh_model_list_cache()
    return {
        "cached_models": {
            provider_id: sorted(model_ids)
            for provider_id, model_ids in runtime.cached_model_ids().items()
        }
    }


@router.get("/admin/api/models")
async def admin_models(request: Request):
    """List advertised models for the loopback Admin UI.

    Mirrors ``GET /v1/models`` but is gated by loopback access instead of the
    client API key, so the dashboard and Chat model picker work even when
    ``ANTHROPIC_AUTH_TOKEN`` is set.
    """
    require_loopback_admin(request)
    settings = get_cached_settings()
    runtime = maybe_provider_runtime(request.app)
    health = maybe_model_health(request.app)
    return build_models_list_response(settings, runtime, health)


@router.get("/admin/api/models/health")
async def models_health(request: Request):
    require_loopback_admin(request)
    settings = get_cached_settings()
    health = _model_health_for_admin(request)
    return {
        "model_list_mode": settings.model_list_mode,
        "enabled": settings.model_health_enabled,
        "models": health.snapshot(),
    }


@router.post("/admin/api/models/health-check")
async def models_health_check(request: Request):
    require_loopback_admin(request)
    settings = get_cached_settings()
    runtime = _provider_runtime_for_admin(request, settings)
    health = _model_health_for_admin(request)
    return await probe_model_health(settings=settings, runtime=runtime, health=health)


@router.get("/admin/api/usage")
async def admin_usage(request: Request, range: str = DEFAULT_USAGE_RANGE):
    require_loopback_admin(request)
    settings = get_cached_settings()
    range_seconds = USAGE_RANGE_SECONDS.get(
        range, USAGE_RANGE_SECONDS[DEFAULT_USAGE_RANGE]
    )
    tracker = _usage_for_admin(request)
    snapshot = tracker.snapshot(range_seconds)
    snapshot["budget"] = _usage_budget(settings, snapshot["totals"])
    return snapshot


def _usage_budget(settings: Settings, totals: dict[str, Any]) -> dict[str, Any]:
    """Compute the dashboard token-budget gauge from settings + window totals."""
    limit = int(settings.usage_token_budget)
    used = int(totals.get("tokens_in", 0)) + int(totals.get("tokens_out", 0))
    percent = round(used / limit * 100, 1) if limit > 0 else 0.0
    return {"token_limit": limit, "tokens_used": used, "percent_used": percent}


def _usage_for_admin(request: Request) -> Usage:
    usage = maybe_usage(request.app)
    if usage is not None:
        return usage
    usage = Usage()
    request.app.state.usage = usage
    return usage


def _model_health_for_admin(request: Request) -> ModelHealth:
    health = maybe_model_health(request.app)
    if health is not None:
        return health
    settings = get_cached_settings()
    health = ModelHealth(cooldown_seconds=settings.model_health_cooldown_seconds)
    request.app.state.model_health = health
    return health


def _provider_runtime_for_admin(
    request: Request, settings: Settings
) -> ProviderRuntime:
    runtime = getattr(request.app.state, "provider_runtime", None)
    if isinstance(runtime, ProviderRuntime):
        return runtime
    runtime = ProviderRuntime(settings)
    request.app.state.provider_runtime = runtime
    return runtime


def _filtered_values(values: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in values.items() if key in FIELD_BY_KEY}


async def _invoke_admin_restart_callback(callback: Any) -> None:
    result = callback()
    if inspect.isawaitable(result):
        await result


def _restart_metadata(fields: list[str], request: Request) -> dict[str, Any]:
    callback = getattr(request.app.state, "admin_restart_callback", None)
    automatic = bool(fields and callable(callback))
    return {
        "required": bool(fields),
        "automatic": automatic,
        "admin_url": _next_admin_url() if automatic else None,
        "fields": fields,
    }


def _next_admin_url() -> str:
    fields = {
        field["key"]: field["value"] for field in load_config_response()["fields"]
    }
    settings = Settings.model_construct(
        host=fields.get("HOST") or "0.0.0.0",
        port=int(fields.get("PORT") or 8082),
    )
    return local_admin_url(settings)


def _local_provider_url(provider_id: str, values: dict[str, str]) -> str:
    if provider_id == "lmstudio":
        return values.get("LM_STUDIO_BASE_URL", "")
    if provider_id == "llamacpp":
        return values.get("LLAMACPP_BASE_URL", "")
    if provider_id == "ollama":
        return values.get("OLLAMA_BASE_URL", "")
    return ""


async def _check_local_provider(
    provider_id: str, base_url: str, path: str
) -> dict[str, Any]:
    clean_url = base_url.strip().rstrip("/")
    if not clean_url:
        return {
            "provider_id": provider_id,
            "status": "missing_url",
            "label": "Missing URL",
            "base_url": base_url,
        }

    url = f"{clean_url}{path}"
    try:
        async with httpx.AsyncClient(timeout=1.5) as client:
            response = await client.get(url)
        ok = 200 <= response.status_code < 300
        return {
            "provider_id": provider_id,
            "status": "reachable" if ok else "offline",
            "label": "Reachable" if ok else "Offline",
            "base_url": base_url,
            "status_code": response.status_code,
        }
    except Exception as exc:
        return {
            "provider_id": provider_id,
            "status": "offline",
            "label": "Offline",
            "base_url": base_url,
            "error_type": type(exc).__name__,
        }
