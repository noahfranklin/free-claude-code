# Admin Dashboard

The Admin UI ships a DashWind-style admin dashboard for Free Claude Code. It runs
**fully offline** and is served **local-only** at `http://127.0.0.1:8082/admin`
(loopback access only). This guide covers how to open it, a tour of each tab, how
usage metrics and the chat work, the loopback endpoints behind them, and the
offline/local-only guarantees.

Added in **2.7.0** (2026-06-28). The token-budget gauge and expanded usage
charts (input-token & error time series, per-provider and per-model tooltips)
arrived in **2.8.0**. See [../CHANGELOG.md](../CHANGELOG.md) for the full release
notes.

## Open the dashboard

1. Start the proxy:

   ```bash
   fcc-server
   ```

2. After startup, the app logs the admin URL:

   ```text
   INFO:     Admin UI: http://127.0.0.1:8082/admin (local-only)
   ```

   Many terminals make this clickable. Open it in your browser. If your `PORT`
   is not `8082`, use the address from your own terminal output.

3. The Admin UI opens on the **Analytics dashboard** (the default view).

The dashboard is reachable only from the same machine (loopback). It is not
exposed on your network.

## Tour of the tabs

The redesigned shell has working navigation tabs:

- **Dashboard** — the default Analytics view: stat cards, charts, and a
  recent-activity table (see [Usage metrics](#usage-metrics) below).
- **Providers** — enter API keys / local base URLs for your providers, then
  **Validate** and **Apply**. This is also where you set the NVIDIA NIM API key
  used by NVIDIA NIM voice transcription.
- **Models** — working-model health: review which models are currently healthy
  and run a proactive **"Check working models"** health-check across all
  credentialed providers. Models that error or time out in real use are hidden
  from the picker until a cooldown elapses.
- **Chat** — an apps-chats-style chat to talk to your configured free models (see
  [Chat](#chat) below).
- **Config** — edit supported proxy settings (such as `MODEL` and the model-tier
  overrides), validate changes, and apply them.
- **Messaging** — configure the optional Discord / Telegram bot wrapper and Voice
  Notes (platform, bot tokens, allowed channels/users, allowed directory, and
  Whisper / NVIDIA NIM transcription settings).

Use **Validate** then **Apply** when changing settings; restart the server if the
UI says a restart is required.

## Usage metrics

The Analytics dashboard summarizes local request activity.

**Stat cards:**

- Total requests
- Tokens in / tokens out
- Errors
- Average latency
- Active / working models
- **Token budget** — appears only when a budget is configured; shows the percent
  of the token budget used over the selected range (see
  [Token budget](#token-budget) below).

**Charts:**

- **Requests over time** — line chart of request volume across the selected
  range.
- **Tokens over time** — line chart of input and output tokens across the
  selected range.
- **Errors over time** — line chart of error volume across the selected range.
- **Requests by provider** — doughnut chart breaking down requests per provider;
  tooltips also show tokens and errors for each provider.
- **Top models** — bar chart of the most-used models; tooltips also show tokens,
  errors, and average latency for each model.

**Recent activity** — a table of recent requests for a quick at-a-glance view.

### Token budget

When a soft token budget is configured, the dashboard adds a **Token budget**
gauge that shows the percent of the budget consumed (input + output tokens) over
the selected range.

- Set the budget with the **`USAGE_TOKEN_BUDGET`** setting (environment variable
  `USAGE_TOKEN_BUDGET`). It is also editable from the admin **Config** /
  **Runtime settings**.
- `0` (the default) **disables** the gauge.
- The budget is **display-only**: it is a soft target for visibility and is
  **never enforced** — requests are never blocked or throttled when it is
  exceeded.

### Range selector

Use the range selector to choose the window for all cards, charts, and the
activity table:

- `1h` — last hour
- `24h` — last 24 hours
- `7d` — last 7 days

Switching the range re-queries `GET /admin/api/usage?range=1h|24h|7d` and updates
the view. All metrics come from local request tracking; nothing is sent off the
machine.

## Chat

The **Chat** tab is an apps-chats-style interface for talking to your own
configured free models:

- The **left** side lists your configured models as conversation
  "contacts."
- The **right** side is the chat thread for the selected model.

To use it:

1. Pick a model from the left list (each model is a "contact"). A model picker is
   also available to switch models.
2. Type a message and send it.
3. Replies **stream** in token by token from your configured free providers via
   the loopback endpoint `POST /admin/api/chat`.
4. Responses are rendered with **offline markdown** rendering (no network
   fetches).

This lets you sanity-check a provider/model directly from the browser without
launching a separate client.

## Endpoints

The dashboard is backed by loopback-only Admin API endpoints:

- `GET /admin/api/usage?range=1h|24h|7d` — usage metrics for the stat cards,
  charts, and recent-activity table over the selected range. The response also
  includes a `budget` block (`token_limit`, `tokens_used`, `percent_used`) that
  backs the Token budget gauge.
- `POST /admin/api/chat` — streams a chat completion from your configured free
  providers for the selected model; powers the Chat tab.
- `GET /admin/api/models/health` — current working-model health state.
- `POST /admin/api/models/health-check` — runs a proactive health-check across
  all credentialed providers (the **"Check working models"** action on the Models
  tab).

These endpoints are part of the Admin UI surface and are reachable only from the
local machine.

## Offline and local-only guarantees

- **No CDNs or web fonts.** The dashboard loads no remote stylesheets, scripts,
  or fonts.
- **Vendored Chart.js.** Charts render from a locally vendored copy of Chart.js
  at `api/admin_static/vendor/chart.umd.min.js` — no CDN.
- **Offline markdown.** Chat replies are rendered with offline markdown; no
  network access is required to display them.
- **Local-only serving.** The Admin UI and its API endpoints are served on
  `127.0.0.1` (loopback) at `/admin` and are not exposed to your network.

The only network traffic originates from the proxy itself when it forwards your
requests to the providers you have configured.
