"""Tests for AppRuntime's background model-health probe scheduling."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI

import api.runtime as api_runtime_mod
from api.model_health import ModelHealth
from api.runtime import AppRuntime
from config.settings import Settings
from providers.runtime import ProviderRuntime


def _probe_settings(
    *,
    enabled: bool = True,
    on_startup: bool = True,
    interval: float = 900.0,
) -> Settings:
    settings = SimpleNamespace(
        model_health_enabled=enabled,
        model_health_probe_on_startup=on_startup,
        model_health_probe_interval_seconds=interval,
        model_health_cooldown_seconds=600.0,
    )
    return cast(Settings, settings)


def _runtime(settings: Settings) -> AppRuntime:
    app = FastAPI()
    app.state.model_health = ModelHealth(cooldown_seconds=600.0)
    runtime = AppRuntime(app=app, settings=settings)
    runtime._provider_runtime = cast(ProviderRuntime, MagicMock())
    return runtime


@pytest.mark.asyncio
async def test_start_probe_skips_when_probe_on_startup_disabled() -> None:
    runtime = _runtime(_probe_settings(on_startup=False))
    runtime._start_model_health_probe()
    assert runtime._health_probe_task is None


@pytest.mark.asyncio
async def test_start_probe_skips_when_health_disabled() -> None:
    runtime = _runtime(_probe_settings(enabled=False))
    runtime._start_model_health_probe()
    assert runtime._health_probe_task is None


@pytest.mark.asyncio
async def test_start_probe_skips_when_no_provider_runtime() -> None:
    runtime = _runtime(_probe_settings())
    runtime._provider_runtime = None
    runtime._start_model_health_probe()
    assert runtime._health_probe_task is None


@pytest.mark.asyncio
async def test_start_probe_schedules_when_enabled(monkeypatch) -> None:
    async def _noop(self: AppRuntime) -> None:
        return None

    monkeypatch.setattr(AppRuntime, "_run_health_probe_loop", _noop)

    runtime = _runtime(_probe_settings())
    runtime._start_model_health_probe()
    assert runtime._health_probe_task is not None
    # Clean up the scheduled task so it does not leak across the test session.
    await runtime._stop_model_health_probe()


@pytest.mark.asyncio
async def test_run_loop_single_sweep_marks_initial_probe_complete(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    async def _fake_probe(**kwargs: object) -> dict[str, object]:
        calls.append(kwargs)
        return {}

    monkeypatch.setattr(api_runtime_mod, "probe_model_health", _fake_probe)

    runtime = _runtime(_probe_settings(interval=0.0))
    health = runtime.app.state.model_health
    assert health.initial_probe_complete is False

    await runtime._run_health_probe_loop()

    # interval <= 0 means exactly one sweep, and the flag flips afterwards.
    assert len(calls) == 1
    assert health.initial_probe_complete is True
