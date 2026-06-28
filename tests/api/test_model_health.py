"""Unit tests for the in-memory model health registry."""

from __future__ import annotations

from api.model_health import ModelHealth, ModelHealthStatus


class _FakeClock:
    """Controllable monotonic clock for deterministic cooldown tests."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _registry(cooldown: float = 600.0) -> tuple[ModelHealth, _FakeClock]:
    clock = _FakeClock()
    return ModelHealth(cooldown_seconds=cooldown, clock=clock), clock


def test_unknown_for_unseen_ref() -> None:
    registry, _clock = _registry()
    assert registry.status("nvidia_nim/foo") is ModelHealthStatus.UNKNOWN


def test_mark_healthy_then_status_healthy() -> None:
    registry, _clock = _registry()
    registry.mark_healthy("nvidia_nim/foo")
    assert registry.status("nvidia_nim/foo") is ModelHealthStatus.HEALTHY


def test_unhealthy_expires_to_unknown_after_cooldown() -> None:
    registry, clock = _registry(cooldown=600.0)
    registry.mark_unhealthy("nvidia_nim/foo", "idle_timeout")
    assert registry.status("nvidia_nim/foo") is ModelHealthStatus.UNHEALTHY

    clock.advance(599.0)
    assert registry.status("nvidia_nim/foo") is ModelHealthStatus.UNHEALTHY

    clock.advance(2.0)
    assert registry.status("nvidia_nim/foo") is ModelHealthStatus.UNKNOWN


def test_healthy_does_not_expire() -> None:
    registry, clock = _registry(cooldown=10.0)
    registry.mark_healthy("nvidia_nim/foo")
    clock.advance(10_000.0)
    assert registry.status("nvidia_nim/foo") is ModelHealthStatus.HEALTHY


def test_mark_healthy_clears_unhealthy() -> None:
    registry, _clock = _registry()
    registry.mark_unhealthy("nvidia_nim/foo", "boom")
    registry.mark_healthy("nvidia_nim/foo")
    assert registry.status("nvidia_nim/foo") is ModelHealthStatus.HEALTHY


def test_is_listable_mode_all_always_true() -> None:
    registry, _clock = _registry()
    registry.mark_unhealthy("nvidia_nim/foo", "boom")
    assert registry.is_listable("nvidia_nim/foo", mode="all") is True


def test_is_listable_exclude_unhealthy() -> None:
    registry, _clock = _registry()
    registry.mark_unhealthy("nvidia_nim/bad", "boom")
    registry.mark_healthy("nvidia_nim/good")
    assert registry.is_listable("nvidia_nim/bad", mode="exclude_unhealthy") is False
    assert registry.is_listable("nvidia_nim/good", mode="exclude_unhealthy") is True
    # Unknown models remain listable under exclude_unhealthy.
    assert registry.is_listable("nvidia_nim/new", mode="exclude_unhealthy") is True


def test_is_listable_healthy_only() -> None:
    registry, _clock = _registry()
    registry.mark_unhealthy("nvidia_nim/bad", "boom")
    registry.mark_healthy("nvidia_nim/good")
    assert registry.is_listable("nvidia_nim/good", mode="healthy_only") is True
    assert registry.is_listable("nvidia_nim/bad", mode="healthy_only") is False
    assert registry.is_listable("nvidia_nim/new", mode="healthy_only") is False


def test_is_listable_uses_cooldown_expiry() -> None:
    registry, clock = _registry(cooldown=100.0)
    registry.mark_unhealthy("nvidia_nim/bad", "boom")
    assert registry.is_listable("nvidia_nim/bad", mode="exclude_unhealthy") is False
    clock.advance(101.0)
    # After cooldown the model is UNKNOWN and listable again under exclude_unhealthy.
    assert registry.is_listable("nvidia_nim/bad", mode="exclude_unhealthy") is True


def test_snapshot_shape() -> None:
    registry, clock = _registry()
    registry.mark_healthy("nvidia_nim/good")
    registry.mark_unhealthy("nvidia_nim/bad", "idle_timeout")
    clock.advance(5.0)

    snap = registry.snapshot()
    assert set(snap) == {"nvidia_nim/good", "nvidia_nim/bad"}
    assert snap["nvidia_nim/good"]["status"] == "healthy"
    assert snap["nvidia_nim/good"]["reason"] == ""
    assert snap["nvidia_nim/bad"]["status"] == "unhealthy"
    assert snap["nvidia_nim/bad"]["reason"] == "idle_timeout"
    assert snap["nvidia_nim/bad"]["age_seconds"] == 5.0
