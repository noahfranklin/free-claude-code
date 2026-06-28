# Changelog

All notable changes to this fork are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

This fork was branched from upstream
[Alishahryar1/free-claude-code](https://github.com/Alishahryar1/free-claude-code)
at base version **2.3.20**.

## [2.5.0] - 2026-06-28

### Added

- **Stream idle-timeout watchdog** (`core/anthropic/stream_watchdog.py`): a per-request
  watchdog that aborts an upstream stream when no bytes arrive within a configurable
  idle window, surfacing a clean Anthropic error instead of a long silent hang.
  - New setting `HTTP_STREAM_IDLE_TIMEOUT` (default `60` seconds).
- **Working-models-only model picker**: model-health tracking that keeps the
  `/v1/models` catalog limited to models that actually respond.
  - Reactive auto-demotion: a model that errors or times out during real use is
    hidden from the picker until a cooldown elapses (`api/model_health.py`,
    `api/model_catalog.py`, hooked from `api/provider_execution.py`).
  - Proactive Admin UI **"Check working models"** health-check across all
    credentialed providers (`api/admin_routes.py`).
  - New settings: `FCC_MODEL_HEALTH_ENABLED`, `FCC_MODEL_LIST_MODE`
    (`all` | `exclude_unhealthy` | `healthy_only`), `FCC_MODEL_HEALTH_COOLDOWN`,
    `FCC_MODEL_HEALTH_PROBE_TIMEOUT`, `FCC_MODEL_HEALTH_PROBE_CONCURRENCY`.
  - New admin endpoints: `GET /admin/api/models/health` and
    `POST /admin/api/models/health-check`.

### Fixed

- **~5-minute silent hang on non-responding upstreams**: when a provider accepted a
  request but sent no data (observed when Claude Code auto-selected a non-responding
  NVIDIA NIM model), the proxy waited the full 300s read-timeout. It now aborts in
  ~`HTTP_STREAM_IDLE_TIMEOUT` seconds with a clean Anthropic error.
- **Malformed HTTP 500 on missing API key**: a provider configured without an API key
  now returns a proper Anthropic `401 authentication_error` that names the required
  environment variable and where to obtain a key, instead of an unhandled HTTP 500
  (`api/dependencies.py` plus the app-level `ProviderError` handler).

### Changed

- The `/v1/models` listing is now health-aware and governed by `FCC_MODEL_LIST_MODE`;
  with model-health disabled (`FCC_MODEL_HEALTH_ENABLED=false`) or `FCC_MODEL_LIST_MODE=all`,
  the catalog behaves as before.

[2.5.0]: https://github.com/noahfranklin/free-claude-code/releases/tag/v2.5.0
