# Changelog

All notable changes to this fork are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

This fork was branched from upstream
[Alishahryar1/free-claude-code](https://github.com/Alishahryar1/free-claude-code)
at base version **2.3.20**.

## [2.8.0] - 2026-06-28

### Added

- **Configurable token budget** (`USAGE_TOKEN_BUDGET`; env var, default `0` =
  disabled): a display-only soft budget over input + output tokens. When set, the
  Analytics dashboard renders a **"% of budget"** gauge for the selected range.
  It is editable from the admin Config / Runtime settings and is **never
  enforced**.
  - The `GET /admin/api/usage` response now includes a `budget` block
    (`token_limit`, `tokens_used`, `percent_used`).
- **Expanded dashboard visualizations** that surface previously-unvisualized
  usage data already returned by the endpoint:
  - Input-token and error time series charts (alongside requests and output
    tokens).
  - Per-provider doughnut tooltips now show tokens and errors.
  - Per-model bar tooltips now show tokens, errors, and average latency.

### Fixed

- **Admin model picker is no longer empty when `ANTHROPIC_AUTH_TOKEN` is set.**
  The dashboard and Chat view fetched the auth-protected `GET /v1/models` from
  the browser without the token, so a configured token made every model list
  return `401` ("No models available", Chat could not send). Added a
  loopback-only `GET /admin/api/models` (gated by local access, like
  `/admin/api/chat`) and pointed the Admin UI at it; it advertises every model
  from credentialed providers plus the static Claude models.
- **Dashboard charts now render.** The vendored Chart.js
  (`/admin/assets/vendor/chart.umd.min.js`) was returning **404** because the
  admin asset route did not match the `vendor/` subpath, leaving every chart
  blank. Added a loopback-only route that serves the bundled Chart.js (and
  rejects any other vendor filename).

## [2.7.0] - 2026-06-28

### Added

- **Analytics dashboard** (default Admin UI view): a DashWind-style admin shell
  with stat cards (total requests, tokens in/out, errors, average latency, and
  active/working models) and charts (requests-over-time line chart,
  requests-by-provider doughnut, top-models bar chart) plus a recent-activity
  table.
  - New loopback usage endpoint `GET /admin/api/usage?range=1h|24h|7d` backs the
    cards, charts, and recent-activity table from local request tracking.
- **Working navigation tabs** in the redesigned shell: Dashboard, Providers,
  Models (working-model health), Chat, Config, and Messaging.
- **apps-chats-style chat UI**: a left list of your configured models as
  conversation "contacts" and a right-hand chat thread that streams replies from
  your free providers via `POST /admin/api/chat`, with offline markdown
  rendering and a model picker.
- **Vendored offline Chart.js** at `api/admin_static/vendor/chart.umd.min.js` so
  the dashboard renders charts with no CDN, web fonts, or other network access.

### Changed

- The Admin UI now opens on the Analytics dashboard by default; everything stays
  fully offline and local-only (`127.0.0.1/admin`).

## [2.6.0] - 2026-06-28

### Added

- **Admin UI redesign**: a refreshed local Admin UI layout for editing proxy
  settings, validating changes, and checking providers (loopback access only).
- **In-browser chat**: an Admin UI chat surface to talk to your configured free
  models directly from the browser, backed by the loopback endpoint
  `POST /admin/api/chat`.

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

[2.7.0]: https://github.com/noahfranklin/free-claude-code/releases/tag/v2.7.0
[2.6.0]: https://github.com/noahfranklin/free-claude-code/releases/tag/v2.6.0
[2.5.0]: https://github.com/noahfranklin/free-claude-code/releases/tag/v2.5.0
