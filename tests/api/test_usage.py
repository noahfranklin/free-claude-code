"""Tests for the app-scoped usage tracker and the admin usage endpoint."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from api.app import create_app
from api.usage import Usage
from config.settings import get_settings


class _Clock:
    """Mutable fake clock for deterministic windows."""

    def __init__(self, t: float = 0.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t


def _set_home(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.chdir(tmp_path)


def _populate(clock: _Clock) -> Usage:
    usage = Usage(clock=clock)

    clock.t = 235.0
    usage.record(
        provider_id="deepseek",
        model="m1",
        tokens_in=10,
        tokens_out=20,
        status="ok",
        latency_ms=100.0,
    )
    clock.t = 236.0
    usage.record(
        provider_id="deepseek",
        model="m1",
        tokens_in=5,
        tokens_out=5,
        status="ok",
        latency_ms=200.0,
    )
    clock.t = 238.0
    usage.record(
        provider_id="openrouter",
        model="m2",
        tokens_in=1,
        tokens_out=2,
        status="error",
        latency_ms=50.0,
        error_reason="boom",
    )
    clock.t = 130.0
    usage.record(
        provider_id="deepseek",
        model="m1",
        tokens_in=999,
        tokens_out=999,
        status="ok",
        latency_ms=999.0,
    )
    # Out of the 120s window (now=240 -> window_start=120); excluded.
    clock.t = 50.0
    usage.record(
        provider_id="deepseek",
        model="m1",
        tokens_in=7777,
        tokens_out=7777,
        status="ok",
        latency_ms=7777.0,
    )
    return usage


def test_totals_only_count_in_window() -> None:
    clock = _Clock()
    usage = _populate(clock)
    clock.t = 240.0

    snap = usage.snapshot(120)
    totals = snap["totals"]

    assert snap["range_seconds"] == 120
    assert totals["requests"] == 4
    assert totals["tokens_in"] == 1015
    assert totals["tokens_out"] == 1026
    assert totals["errors"] == 1
    assert totals["avg_latency_ms"] == 337.25
    assert totals["active_models"] == 2


def test_series_buckets_sum_to_totals() -> None:
    clock = _Clock()
    usage = _populate(clock)
    clock.t = 240.0

    snap = usage.snapshot(120)
    series = snap["series"]
    totals = snap["totals"]

    assert len(series["labels"]) == 12
    assert len(series["requests"]) == 12
    assert sum(series["requests"]) == totals["requests"]
    assert sum(series["tokens_in"]) == totals["tokens_in"]
    assert sum(series["tokens_out"]) == totals["tokens_out"]
    assert sum(series["errors"]) == totals["errors"]


def test_by_provider_aggregation_and_sorting() -> None:
    clock = _Clock()
    usage = _populate(clock)
    clock.t = 240.0

    by_provider = usage.snapshot(120)["by_provider"]

    assert [row["provider_id"] for row in by_provider] == ["deepseek", "openrouter"]
    deepseek = by_provider[0]
    assert deepseek["requests"] == 3
    assert deepseek["tokens"] == 2038
    assert deepseek["errors"] == 0
    openrouter = by_provider[1]
    assert openrouter["requests"] == 1
    assert openrouter["tokens"] == 3
    assert openrouter["errors"] == 1


def test_by_model_aggregation_sorting_and_avg_latency() -> None:
    clock = _Clock()
    usage = _populate(clock)
    clock.t = 240.0

    by_model = usage.snapshot(120)["by_model"]

    assert [row["model"] for row in by_model] == ["m1", "m2"]
    m1 = by_model[0]
    assert m1["requests"] == 3
    assert m1["tokens"] == 2038
    assert m1["errors"] == 0
    assert m1["avg_latency_ms"] == 433.0
    m2 = by_model[1]
    assert m2["avg_latency_ms"] == 50.0


def test_by_model_capped_at_20() -> None:
    clock = _Clock(t=1000.0)
    usage = Usage(clock=clock)
    for i in range(30):
        usage.record(
            provider_id="p",
            model=f"model-{i}",
            tokens_in=1,
            tokens_out=1,
            status="ok",
            latency_ms=1.0,
        )

    by_model = usage.snapshot(3600)["by_model"]
    assert len(by_model) == 20


def test_recent_ordering_newest_first() -> None:
    clock = _Clock()
    usage = _populate(clock)
    clock.t = 240.0

    recent = usage.snapshot(120)["recent"]

    assert len(recent) == 4
    # Record inserted last (the ts=130 deepseek entry) is newest.
    assert recent[0]["tokens_in"] == 999
    assert recent[0]["provider"] == "deepseek"
    assert recent[-1]["latency_ms"] == 100.0


def test_recent_capped_at_50() -> None:
    clock = _Clock(t=1000.0)
    usage = Usage(clock=clock)
    for i in range(60):
        usage.record(
            provider_id="p",
            model="m",
            tokens_in=i,
            tokens_out=i,
            status="ok",
            latency_ms=float(i),
        )

    recent = usage.snapshot(3600)["recent"]
    assert len(recent) == 50
    # Newest first: last recorded (i=59) leads.
    assert recent[0]["tokens_in"] == 59
    assert recent[-1]["tokens_in"] == 10


def test_ring_buffer_is_bounded() -> None:
    clock = _Clock(t=1000.0)
    usage = Usage(clock=clock, max_records=10)
    for _ in range(25):
        usage.record(
            provider_id="p",
            model="m",
            tokens_in=1,
            tokens_out=1,
            status="ok",
            latency_ms=1.0,
        )
    assert usage.snapshot(3600)["totals"]["requests"] == 10


def test_date_labels_for_wide_window() -> None:
    clock = _Clock(t=1_000_000.0)
    usage = Usage(clock=clock)
    labels = usage.snapshot(7 * 24 * 60 * 60)["series"]["labels"]
    # 7-day window (>2 days) uses MM-DD labels.
    assert all(len(label) == 5 and label[2] == "-" for label in labels)


def test_admin_usage_endpoint_loopback(monkeypatch, tmp_path) -> None:
    _set_home(monkeypatch, tmp_path)
    app = create_app(lifespan_enabled=False)
    client = TestClient(app, client=("127.0.0.1", 50000))

    response = client.get("/admin/api/usage", params={"range": "1h"})
    assert response.status_code == 200
    body = response.json()
    assert body["range_seconds"] == 3600
    assert set(body) == {
        "range_seconds",
        "totals",
        "series",
        "by_provider",
        "by_model",
        "recent",
        "budget",
    }
    assert set(body["totals"]) == {
        "requests",
        "tokens_in",
        "tokens_out",
        "errors",
        "avg_latency_ms",
        "active_models",
    }
    assert set(body["budget"]) == {"token_limit", "tokens_used", "percent_used"}
    # Default budget is 0 (disabled) -> percent stays 0.
    assert body["budget"]["token_limit"] == 0
    assert body["budget"]["percent_used"] == 0.0


def test_admin_usage_endpoint_budget_percent(monkeypatch, tmp_path) -> None:
    _set_home(monkeypatch, tmp_path)
    monkeypatch.setenv("USAGE_TOKEN_BUDGET", "100")
    # Settings are lru_cached; drop any cached instance so the new env is read.
    get_settings.cache_clear()
    app = create_app(lifespan_enabled=False)
    client = TestClient(app, client=("127.0.0.1", 50000))

    tracker = Usage()
    tracker.record(
        provider_id="p",
        model="m",
        tokens_in=10,
        tokens_out=15,
        status="ok",
        latency_ms=5.0,
    )
    app.state.usage = tracker

    body = client.get("/admin/api/usage", params={"range": "1h"}).json()
    assert body["budget"]["token_limit"] == 100
    assert body["budget"]["tokens_used"] == 25
    assert body["budget"]["percent_used"] == 25.0
    # Avoid leaking the configured budget into other tests via the cache.
    get_settings.cache_clear()


def test_admin_usage_endpoint_unknown_range_defaults_to_24h(
    monkeypatch, tmp_path
) -> None:
    _set_home(monkeypatch, tmp_path)
    app = create_app(lifespan_enabled=False)
    client = TestClient(app, client=("127.0.0.1", 50000))

    response = client.get("/admin/api/usage", params={"range": "bogus"})
    assert response.status_code == 200
    assert response.json()["range_seconds"] == 24 * 60 * 60


def test_admin_usage_endpoint_default_range(monkeypatch, tmp_path) -> None:
    _set_home(monkeypatch, tmp_path)
    app = create_app(lifespan_enabled=False)
    client = TestClient(app, client=("127.0.0.1", 50000))

    response = client.get("/admin/api/usage")
    assert response.status_code == 200
    assert response.json()["range_seconds"] == 24 * 60 * 60


def test_admin_usage_endpoint_rejects_remote(monkeypatch, tmp_path) -> None:
    _set_home(monkeypatch, tmp_path)
    app = create_app(lifespan_enabled=False)
    remote = TestClient(app, client=("203.0.113.10", 50000))

    assert remote.get("/admin/api/usage").status_code == 403
