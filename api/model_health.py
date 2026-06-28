"""App-scoped in-memory model health registry.

Tracks which advertised models are in working condition so GET /v1/models can
hide broken ones from Claude Code's model picker. Health is recorded reactively
(real-use success/idle-timeout/error) and proactively (admin probe). A model
marked unhealthy is hidden until a cooldown elapses, after which it becomes
``UNKNOWN`` again and is eligible to be advertised and re-probed.

This module is import-light by design: it has no provider or settings imports so
it can be constructed and queried from any layer.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum


class ModelHealthStatus(StrEnum):
    """Effective health of a single ``provider/model`` ref."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class _HealthRecord:
    """Immutable last-known health entry for one model ref."""

    status: ModelHealthStatus
    reason: str
    updated_at: float


class ModelHealth:
    """In-memory health registry keyed by ``provider/model`` ref."""

    def __init__(
        self,
        *,
        cooldown_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._cooldown_seconds = cooldown_seconds
        self._clock = clock
        self._records: dict[str, _HealthRecord] = {}
        self._initial_probe_complete = False

    @property
    def initial_probe_complete(self) -> bool:
        """Whether at least one full proactive probe sweep has finished.

        Used to apply a cold-start grace period: ``healthy_only`` listing is only
        enforced once the first sweep has classified models, so the picker is not
        empty during the seconds between startup and the first probe completing.
        """
        return self._initial_probe_complete

    def mark_initial_probe_complete(self) -> None:
        """Record that the first proactive probe sweep has completed."""
        self._initial_probe_complete = True

    def is_healthy(self, ref: str) -> bool:
        """Return whether a model ref is currently verified-healthy."""
        return self.status(ref) is ModelHealthStatus.HEALTHY

    def mark_healthy(self, ref: str) -> None:
        """Record that a model streamed successfully."""
        self._records[ref] = _HealthRecord(ModelHealthStatus.HEALTHY, "", self._clock())

    def mark_unhealthy(self, ref: str, reason: str) -> None:
        """Record that a model failed (timeout, error, or empty stream)."""
        self._records[ref] = _HealthRecord(
            ModelHealthStatus.UNHEALTHY, reason, self._clock()
        )

    def status(self, ref: str) -> ModelHealthStatus:
        """Return the effective status, expiring stale UNHEALTHY entries."""
        record = self._records.get(ref)
        if record is None:
            return ModelHealthStatus.UNKNOWN
        if record.status is ModelHealthStatus.UNHEALTHY:
            if self._clock() - record.updated_at >= self._cooldown_seconds:
                return ModelHealthStatus.UNKNOWN
            return ModelHealthStatus.UNHEALTHY
        return record.status

    def is_listable(self, ref: str, *, mode: str) -> bool:
        """Return whether a model ref should appear in GET /v1/models."""
        if mode == "all":
            return True
        status = self.status(ref)
        if mode == "healthy_only":
            return status is ModelHealthStatus.HEALTHY
        # "exclude_unhealthy" (default): hide only currently-unhealthy models.
        return status is not ModelHealthStatus.UNHEALTHY

    def snapshot(self) -> dict[str, dict[str, object]]:
        """Return ref -> {status, reason, age_seconds} for admin inspection."""
        now = self._clock()
        return {
            ref: {
                "status": self.status(ref).value,
                "reason": record.reason,
                "age_seconds": now - record.updated_at,
            }
            for ref, record in self._records.items()
        }
