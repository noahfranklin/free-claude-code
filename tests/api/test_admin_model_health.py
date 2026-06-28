"""Admin model-health endpoint tests (snapshot + proactive probe)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from fastapi.testclient import TestClient

from api.app import create_app
from api.model_health import ModelHealth
from config.settings import Settings
from providers.base import BaseProvider, ProviderConfig
from providers.exceptions import ProviderError
from providers.runtime import ProviderRuntime


class _FakeProbeProvider(BaseProvider):
    """Stream a chunk for healthy model ids, raise for the rest."""

    def __init__(self, healthy_models: set[str]) -> None:
        super().__init__(ProviderConfig(api_key="x"))
        self._healthy_models = healthy_models

    async def cleanup(self) -> None:
        return None

    async def list_model_ids(self) -> frozenset[str]:
        return frozenset(self._healthy_models)

    async def stream_response(
        self,
        request: Any,
        input_tokens: int = 0,
        *,
        request_id: str | None = None,
        thinking_enabled: bool | None = None,
    ) -> AsyncIterator[str]:
        if request.model not in self._healthy_models:
            raise ProviderError("model unavailable")
        yield "event: message_start\n\n"


def _settings() -> Settings:
    return Settings.model_construct(
        model="deepseek/good-model",
        deepseek_api_key="x",
        anthropic_auth_token="",
        model_health_enabled=True,
        model_list_mode="exclude_unhealthy",
        model_health_cooldown_seconds=600.0,
        model_health_probe_timeout=5.0,
        model_health_probe_concurrency=4,
    )


def _local_client(app) -> TestClient:
    return TestClient(app, client=("127.0.0.1", 50000))


def test_health_check_probes_and_records(monkeypatch) -> None:
    settings = _settings()
    monkeypatch.setattr("api.admin_routes.get_cached_settings", lambda: settings)

    provider = _FakeProbeProvider({"good-model"})
    runtime = ProviderRuntime(settings, providers={"deepseek": provider})
    runtime.cache_model_ids("deepseek", {"good-model", "bad-model"})

    app = create_app(lifespan_enabled=False)
    app.state.provider_runtime = runtime
    health = ModelHealth(cooldown_seconds=600.0)
    app.state.model_health = health

    response = _local_client(app).post("/admin/api/models/health-check", json={})

    assert response.status_code == 200
    body = response.json()
    assert body["providers"]["deepseek"] == {
        "healthy": 1,
        "unhealthy": 1,
        "total": 2,
    }
    assert body["total"] == {"healthy": 1, "unhealthy": 1, "total": 2}
    assert body["model_list_mode"] == "exclude_unhealthy"

    snapshot = health.snapshot()
    assert snapshot["deepseek/good-model"]["status"] == "healthy"
    assert snapshot["deepseek/bad-model"]["status"] == "unhealthy"
    assert snapshot["deepseek/bad-model"]["reason"] == "ProviderError"


def test_health_snapshot_endpoint(monkeypatch) -> None:
    settings = _settings()
    monkeypatch.setattr("api.admin_routes.get_cached_settings", lambda: settings)

    app = create_app(lifespan_enabled=False)
    health = ModelHealth(cooldown_seconds=600.0)
    health.mark_healthy("deepseek/good-model")
    health.mark_unhealthy("deepseek/bad-model", "idle_timeout")
    app.state.model_health = health

    response = _local_client(app).get("/admin/api/models/health")

    assert response.status_code == 200
    body = response.json()
    assert body["model_list_mode"] == "exclude_unhealthy"
    assert body["enabled"] is True
    assert body["models"]["deepseek/good-model"]["status"] == "healthy"
    assert body["models"]["deepseek/bad-model"]["status"] == "unhealthy"


def test_health_check_is_loopback_only() -> None:
    app = create_app(lifespan_enabled=False)
    remote = TestClient(app, client=("203.0.113.10", 50000))
    assert remote.post("/admin/api/models/health-check", json={}).status_code == 403
    assert remote.get("/admin/api/models/health").status_code == 403
