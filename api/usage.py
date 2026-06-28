"""App-scoped in-memory API usage/metrics tracker.

Records one entry per provider request (tokens, latency, status) into a bounded
ring buffer and exposes :meth:`Usage.snapshot` which aggregates a trailing time
window into a dashboard-ready contract. The buffer is in-memory and process
local; it is not persisted across restarts.

This module is import-light by design: it has no provider or settings imports so
it can be constructed and queried from any layer. A ``clock`` is injectable so
tests can drive deterministic windows.
"""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

UsageStatus = Literal["ok", "error"]

_MAX_RECORDS = 5000
_BUCKET_COUNT = 12
_RECENT_CAP = 50
_BY_MODEL_CAP = 20
_TWO_DAYS_SECONDS = 2 * 24 * 60 * 60


@dataclass(frozen=True, slots=True)
class _UsageRecord:
    """Immutable record for a single completed (or failed) request."""

    ts: float
    provider_id: str
    model: str
    tokens_in: int
    tokens_out: int
    status: UsageStatus
    latency_ms: float
    error_reason: str


class Usage:
    """In-memory usage tracker backed by a bounded ring buffer."""

    def __init__(
        self,
        *,
        clock: Callable[[], float] = time.time,
        max_records: int = _MAX_RECORDS,
    ) -> None:
        self._clock = clock
        self._records: deque[_UsageRecord] = deque(maxlen=max_records)

    def record(
        self,
        *,
        provider_id: str,
        model: str,
        tokens_in: int,
        tokens_out: int,
        status: UsageStatus,
        latency_ms: float,
        error_reason: str = "",
    ) -> None:
        """Append one request record using the injected clock for its timestamp."""
        self._records.append(
            _UsageRecord(
                ts=self._clock(),
                provider_id=provider_id,
                model=model,
                tokens_in=int(tokens_in),
                tokens_out=int(tokens_out),
                status=status,
                latency_ms=float(latency_ms),
                error_reason=error_reason,
            )
        )

    def snapshot(self, range_seconds: float) -> dict[str, Any]:
        """Aggregate the trailing ``range_seconds`` window into the dashboard contract."""
        now = self._clock()
        window_start = now - range_seconds
        in_window = [r for r in self._records if r.ts >= window_start]

        return {
            "range_seconds": int(range_seconds),
            "totals": self._totals(in_window),
            "series": self._series(in_window, window_start, now, range_seconds),
            "by_provider": self._by_provider(in_window),
            "by_model": self._by_model(in_window),
            "recent": self._recent(in_window),
        }

    @staticmethod
    def _totals(records: list[_UsageRecord]) -> dict[str, Any]:
        requests = len(records)
        tokens_in = sum(r.tokens_in for r in records)
        tokens_out = sum(r.tokens_out for r in records)
        errors = sum(1 for r in records if r.status == "error")
        avg_latency = sum(r.latency_ms for r in records) / requests if requests else 0.0
        active_models = len({r.model for r in records})
        return {
            "requests": requests,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "errors": errors,
            "avg_latency_ms": round(avg_latency, 3),
            "active_models": active_models,
        }

    @staticmethod
    def _series(
        records: list[_UsageRecord],
        window_start: float,
        now: float,
        range_seconds: float,
    ) -> dict[str, list[Any]]:
        bucket_width = range_seconds / _BUCKET_COUNT if range_seconds > 0 else 1.0
        use_date_labels = range_seconds > _TWO_DAYS_SECONDS

        labels: list[str] = []
        for i in range(_BUCKET_COUNT):
            end_ts = window_start + (i + 1) * bucket_width
            labels.append(_format_label(end_ts, use_date_labels=use_date_labels))

        requests = [0] * _BUCKET_COUNT
        tokens_in = [0] * _BUCKET_COUNT
        tokens_out = [0] * _BUCKET_COUNT
        errors = [0] * _BUCKET_COUNT
        for r in records:
            idx = int((r.ts - window_start) / bucket_width)
            if idx < 0:
                idx = 0
            elif idx >= _BUCKET_COUNT:
                idx = _BUCKET_COUNT - 1
            requests[idx] += 1
            tokens_in[idx] += r.tokens_in
            tokens_out[idx] += r.tokens_out
            if r.status == "error":
                errors[idx] += 1

        return {
            "labels": labels,
            "requests": requests,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "errors": errors,
        }

    @staticmethod
    def _by_provider(records: list[_UsageRecord]) -> list[dict[str, Any]]:
        agg: dict[str, dict[str, int]] = {}
        for r in records:
            entry = agg.setdefault(
                r.provider_id, {"requests": 0, "tokens": 0, "errors": 0}
            )
            entry["requests"] += 1
            entry["tokens"] += r.tokens_in + r.tokens_out
            if r.status == "error":
                entry["errors"] += 1
        rows = [
            {
                "provider_id": provider_id,
                "requests": entry["requests"],
                "tokens": entry["tokens"],
                "errors": entry["errors"],
            }
            for provider_id, entry in agg.items()
        ]
        rows.sort(key=lambda row: row["requests"], reverse=True)
        return rows

    @staticmethod
    def _by_model(records: list[_UsageRecord]) -> list[dict[str, Any]]:
        agg: dict[str, dict[str, float]] = {}
        for r in records:
            entry = agg.setdefault(
                r.model,
                {"requests": 0, "tokens": 0, "errors": 0, "latency_sum": 0.0},
            )
            entry["requests"] += 1
            entry["tokens"] += r.tokens_in + r.tokens_out
            entry["latency_sum"] += r.latency_ms
            if r.status == "error":
                entry["errors"] += 1
        rows = [
            {
                "model": model,
                "requests": int(entry["requests"]),
                "tokens": int(entry["tokens"]),
                "errors": int(entry["errors"]),
                "avg_latency_ms": round(entry["latency_sum"] / entry["requests"], 3)
                if entry["requests"]
                else 0.0,
            }
            for model, entry in agg.items()
        ]
        rows.sort(key=lambda row: row["requests"], reverse=True)
        return rows[:_BY_MODEL_CAP]

    @staticmethod
    def _recent(records: list[_UsageRecord]) -> list[dict[str, Any]]:
        recent = records[-_RECENT_CAP:]
        recent.reverse()
        return [
            {
                "ts": r.ts,
                "model": r.model,
                "provider": r.provider_id,
                "status": r.status,
                "tokens_in": r.tokens_in,
                "tokens_out": r.tokens_out,
                "latency_ms": r.latency_ms,
            }
            for r in recent
        ]


def _format_label(end_ts: float, *, use_date_labels: bool) -> str:
    moment = datetime.fromtimestamp(end_ts)
    return moment.strftime("%m-%d") if use_date_labels else moment.strftime("%H:%M")
