const state = {
  config: null,
  fields: new Map(),
  localStatus: new Map(),
  modelOptions: [],
  activeView: "dashboard",
};

const MASKED_SECRET = "********";

const ICONS = {
  dashboard:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="9"/><rect x="14" y="3" width="7" height="5"/><rect x="14" y="12" width="7" height="9"/><rect x="3" y="16" width="7" height="5"/></svg>',
  providers:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="4" width="20" height="6" rx="1.5"/><rect x="2" y="14" width="20" height="6" rx="1.5"/><line x1="6" y1="7" x2="6" y2="7"/><line x1="6" y1="17" x2="6" y2="17"/></svg>',
  models:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M19 5l-2 2M7 17l-2 2"/></svg>',
  chat:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 11.5a8.38 8.38 0 0 1-8.5 8.5 8.5 8.5 0 0 1-3.8-.9L3 21l1.9-5.7a8.5 8.5 0 0 1-.9-3.8A8.38 8.38 0 0 1 12.5 3 8.38 8.38 0 0 1 21 11.5z"/></svg>',
  model_config:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.6 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.6a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9c.36.86 1.2 1.4 2.1 1.5H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>',
  messaging:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 2 11 13"/><path d="M22 2 15 22l-4-9-9-4 20-7z"/></svg>',
};

const STAT_ICONS = {
  requests:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12h4l3 8 4-16 3 8h4"/></svg>',
  tokens:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M9 12h6M12 9v6"/></svg>',
  errors:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12" y2="17"/></svg>',
  latency:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="13" r="8"/><path d="M12 9v4l2 2M9 2h6"/></svg>',
  models:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2 2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5M2 12l10 5 10-5"/></svg>',
  active:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 3"/></svg>',
};

const SUN_ICON =
  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5 19 19M19 5l-1.5 1.5M6.5 17.5 5 19"/></svg>';
const MOON_ICON =
  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>';

const VIEW_GROUPS = [
  {
    id: "dashboard",
    label: "Dashboard",
    title: "Dashboard",
    subtitle: "Live usage, providers, and model health — all on your machine.",
    icon: ICONS.dashboard,
  },
  {
    id: "providers",
    label: "Providers",
    title: "Providers",
    subtitle: "Check provider reachability and edit credentials.",
    icon: ICONS.providers,
    sections: ["providers", "runtime"],
    containerId: "providersSections",
    config: true,
  },
  {
    id: "models",
    label: "Models",
    title: "Models",
    subtitle: "Discover working models and verify each provider's health.",
    icon: ICONS.models,
  },
  {
    id: "chat",
    label: "Chat",
    title: "Chat",
    subtitle: "Talk to any working model through the local proxy.",
    icon: ICONS.chat,
    chat: true,
  },
  {
    id: "model_config",
    label: "Config",
    title: "Config",
    subtitle: "Route the active model and tune thinking and web tools.",
    icon: ICONS.model_config,
    sections: ["models", "thinking", "web_tools"],
    containerId: "modelConfigSections",
    config: true,
  },
  {
    id: "messaging",
    label: "Messaging",
    title: "Messaging",
    subtitle: "Configure messaging and voice integrations.",
    icon: ICONS.messaging,
    sections: ["messaging", "voice"],
    containerId: "messagingSections",
    config: true,
  },
];

const byId = (id) => document.getElementById(id);

function sourceLabel(source) {
  const labels = {
    default: "default",
    template: "template",
    repo_env: "repo .env",
    managed_env: "",
    explicit_env_file: "FCC_ENV_FILE",
    process: "process env",
  };
  return Object.prototype.hasOwnProperty.call(labels, source) ? labels[source] : source;
}

function sourceText(field) {
  const parts = [];
  const label = sourceLabel(field.source);
  if (label) {
    parts.push(label);
  }
  if (field.locked) {
    parts.push("locked");
  }
  return parts.join(" ");
}

function statusClass(status) {
  if (["configured", "reachable", "running", "ok", "success"].includes(status)) return "ok";
  if (["missing_key", "missing_url", "unknown", "pending"].includes(status)) return "warn";
  if (["offline", "error", "failed"].includes(status)) return "error";
  return "neutral";
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return response.json();
}

/* --------------------------------------------------------------- Theme */

const THEME_KEY = "fcc-admin-theme";

function resolvedTheme() {
  const stored = document.documentElement.getAttribute("data-theme");
  if (stored === "light" || stored === "dark") return stored;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  document.documentElement.style.colorScheme = theme;
  const icon = byId("themeChipIcon");
  const label = byId("themeChipLabel");
  if (icon) icon.innerHTML = theme === "dark" ? MOON_ICON : SUN_ICON;
  if (label) label.textContent = theme === "dark" ? "Dark" : "Light";
}

function initTheme() {
  const stored = localStorage.getItem(THEME_KEY);
  applyTheme(stored === "light" || stored === "dark" ? stored : resolvedTheme());
  const chip = byId("themeChip");
  if (chip) {
    chip.addEventListener("click", () => {
      const next = resolvedTheme() === "dark" ? "light" : "dark";
      localStorage.setItem(THEME_KEY, next);
      applyTheme(next);
      if (state.activeView === "dashboard") renderDashboardCharts();
    });
  }
}

function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || "#888";
}

/* --------------------------------------------------------------- Bootstrap */

async function load() {
  showMessage("Loading admin config");
  const config = await api("/admin/api/config");
  state.config = config;
  state.fields = new Map(config.fields.map((field) => [field.key, field]));
  renderNav();
  renderProviders(config.provider_status);
  renderSections(config.sections, config.fields);
  byId("configPath").textContent = config.paths.managed;
  await validate(false);
  await refreshLocalStatus();
  updateDirtyState();
  showMessage("");
}

function renderNav() {
  const nav = byId("sectionNav");
  nav.innerHTML = "";
  VIEW_GROUPS.forEach((view) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "nav-link";
    button.dataset.view = view.id;
    const icon = document.createElement("span");
    icon.className = "nav-icon";
    icon.innerHTML = view.icon || "";
    const text = document.createElement("span");
    text.textContent = view.label;
    button.append(icon, text);
    button.addEventListener("click", () => setActiveView(view.id, { scroll: true }));
    nav.appendChild(button);
  });
  setActiveView(state.activeView, { scroll: false });
}

function setActiveView(viewId, { scroll = false } = {}) {
  const activeView = VIEW_GROUPS.find((view) => view.id === viewId) || VIEW_GROUPS[0];
  state.activeView = activeView.id;
  byId("pageTitle").textContent = activeView.title;
  byId("pageSubtitle").textContent = activeView.subtitle || "";

  document.querySelectorAll(".nav-link").forEach((link) => {
    const selected = link.dataset.view === activeView.id;
    link.classList.toggle("active", selected);
    if (selected) {
      link.setAttribute("aria-current", "page");
    } else {
      link.removeAttribute("aria-current");
    }
  });

  document.querySelectorAll(".admin-view").forEach((view) => {
    const selected = view.dataset.view === activeView.id;
    view.classList.toggle("active", selected);
    view.hidden = !selected;
  });

  const shell = document.querySelector(".app-shell");
  shell.classList.toggle("chat-mode", activeView.chat === true);
  shell.classList.toggle("show-actions", activeView.config === true);

  if (activeView.id === "dashboard") ensureDashboard();
  if (activeView.id === "models") ensureModels();
  if (activeView.chat === true) ensureChatInit();

  if (scroll) window.scrollTo({ top: 0, behavior: "smooth" });
}

/* --------------------------------------------------------------- Providers */

function renderProviders(providerStatus) {
  const grid = byId("providerGrid");
  grid.innerHTML = "";
  providerStatus.forEach((provider) => {
    const card = document.createElement("article");
    card.className = "provider-card";
    card.dataset.provider = provider.provider_id;

    const title = document.createElement("div");
    title.className = "provider-title";
    title.innerHTML = `<strong>${provider.display_name || provider.provider_id}</strong>`;

    const pill = document.createElement("span");
    pill.className = `status-pill ${statusClass(provider.status)}`;
    pill.textContent = provider.label;
    title.appendChild(pill);

    const meta = document.createElement("div");
    meta.className = "provider-meta";
    meta.textContent =
      provider.kind === "local"
        ? provider.base_url || "No local URL configured"
        : provider.credential_env;

    const button = document.createElement("button");
    button.type = "button";
    button.className = "test-button";
    button.textContent = provider.kind === "local" ? "Test" : "Refresh models";
    button.addEventListener("click", () => testProvider(provider.provider_id, button));

    card.append(title, meta, button);
    grid.appendChild(card);
  });
}

function updateProviderCard(providerId, status, label, metaText) {
  const card = document.querySelector(`[data-provider="${providerId}"]`);
  if (!card) return;
  const pill = card.querySelector(".status-pill");
  pill.className = `status-pill ${statusClass(status)}`;
  pill.textContent = label;
  if (metaText) {
    card.querySelector(".provider-meta").textContent = metaText;
  }
}

async function refreshLocalStatus() {
  const result = await api("/admin/api/providers/local-status");
  result.providers.forEach((provider) => {
    state.localStatus.set(provider.provider_id, provider);
    const meta = provider.status_code
      ? `${provider.base_url} returned HTTP ${provider.status_code}`
      : provider.base_url;
    updateProviderCard(provider.provider_id, provider.status, provider.label, meta);
  });
}

async function testProvider(providerId, button) {
  const original = button.textContent;
  button.disabled = true;
  button.textContent = "Testing";
  try {
    const result = await api(`/admin/api/providers/${providerId}/test`, {
      method: "POST",
      body: "{}",
    });
    if (result.ok) {
      updateProviderCard(
        providerId,
        "reachable",
        `${result.models.length} models`,
        result.models.slice(0, 3).join(", ") || "No models returned",
      );
      state.modelOptions = Array.from(
        new Set([
          ...state.modelOptions,
          ...result.models.map((model) => `${providerId}/${model}`),
        ]),
      ).sort();
      syncModelDatalist();
    } else {
      updateProviderCard(providerId, "offline", result.error_type, result.error_type);
    }
  } finally {
    button.disabled = false;
    button.textContent = original;
  }
}

/* --------------------------------------------------------------- Config forms */

function renderSections(sections, fields) {
  VIEW_GROUPS.forEach((view) => {
    if (!view.containerId) return;
    byId(view.containerId).innerHTML = "";
  });

  const sectionById = new Map(sections.map((section) => [section.id, section]));
  const bySection = new Map();
  sections.forEach((section) => bySection.set(section.id, []));
  fields.forEach((field) => {
    if (!bySection.has(field.section)) bySection.set(field.section, []);
    bySection.get(field.section).push(field);
  });

  VIEW_GROUPS.forEach((view) => {
    if (!view.containerId || !view.sections) return;
    const container = byId(view.containerId);
    view.sections.forEach((sectionId) => {
      const section = sectionById.get(sectionId);
      const sectionFields = bySection.get(sectionId) || [];
      if (!section || sectionFields.length === 0) return;

      const sectionEl = document.createElement("section");
      sectionEl.className = "settings-section";
      sectionEl.id = `section-${section.id}`;

      const heading = document.createElement("div");
      heading.className = "section-heading";
      heading.innerHTML = `<div><h3>${section.label}</h3><p>${section.description}</p></div>`;
      sectionEl.appendChild(heading);

      const grid = document.createElement("div");
      grid.className = "field-grid";
      sectionFields.forEach((field) => grid.appendChild(renderField(field)));
      sectionEl.appendChild(grid);

      if (sectionFields.some((field) => field.advanced)) {
        const toggle = document.createElement("button");
        toggle.type = "button";
        toggle.className = "ghost-button advanced-toggle";
        toggle.textContent = "Show advanced";
        toggle.addEventListener("click", () => {
          const showing = sectionEl.classList.toggle("show-advanced");
          toggle.textContent = showing ? "Hide advanced" : "Show advanced";
        });
        sectionEl.appendChild(toggle);
      }

      container.appendChild(sectionEl);
    });
  });
}

function renderField(field) {
  const wrapper = document.createElement("div");
  wrapper.className = `field${field.advanced ? " advanced-field" : ""}`;
  wrapper.dataset.key = field.key;

  const label = document.createElement("label");
  label.htmlFor = `field-${field.key}`;
  const labelText = document.createElement("span");
  labelText.textContent = field.label;
  label.appendChild(labelText);

  const source = sourceText(field);
  if (source) {
    const sourceEl = document.createElement("span");
    sourceEl.className = "field-source";
    sourceEl.textContent = source;
    label.appendChild(sourceEl);
  }

  const input = inputForField(field);
  input.id = `field-${field.key}`;
  input.dataset.key = field.key;
  input.dataset.original = field.value || "";
  input.dataset.secret = field.secret ? "true" : "false";
  input.dataset.configured = field.configured ? "true" : "false";
  input.disabled = field.locked;
  input.addEventListener("input", updateDirtyState);
  input.addEventListener("change", updateDirtyState);

  wrapper.append(label, input);
  if (field.description) {
    const description = document.createElement("div");
    description.className = "field-description";
    description.textContent = field.description;
    wrapper.appendChild(description);
  }
  return wrapper;
}

function inputForField(field) {
  if (field.type === "boolean") {
    const input = document.createElement("input");
    input.type = "checkbox";
    input.checked = String(field.value).toLowerCase() === "true";
    input.dataset.original = input.checked ? "true" : "false";
    return input;
  }

  if (field.type === "tri_boolean") {
    const select = document.createElement("select");
    [
      ["", "Inherit"],
      ["true", "Enabled"],
      ["false", "Disabled"],
    ].forEach(([value, label]) => select.appendChild(option(value, label)));
    select.value = field.value || "";
    return select;
  }

  if (field.type === "select") {
    const select = document.createElement("select");
    field.options.forEach((value) => select.appendChild(option(value, value)));
    select.value = field.value || field.options[0] || "";
    return select;
  }

  if (field.type === "textarea") {
    const textarea = document.createElement("textarea");
    textarea.value = field.value || "";
    return textarea;
  }

  const input = document.createElement("input");
  input.type = field.type === "number" ? "number" : "text";
  if (field.type === "secret") {
    input.type = "password";
    input.placeholder = field.configured
      ? "Configured - enter a new value to replace"
      : "Not configured";
    input.value = "";
    input.autocomplete = "off";
  } else {
    input.value = field.value || "";
  }
  if (field.key.startsWith("MODEL")) {
    input.setAttribute("list", "model-options");
  }
  return input;
}

function option(value, label) {
  const optionEl = document.createElement("option");
  optionEl.value = value;
  optionEl.textContent = label;
  return optionEl;
}

function readFieldValue(input) {
  if (input.type === "checkbox") return input.checked ? "true" : "false";
  if (input.dataset.secret === "true" && input.dataset.configured === "true") {
    return input.value ? input.value : MASKED_SECRET;
  }
  return input.value;
}

function changedValues() {
  const values = {};
  document.querySelectorAll("[data-key]").forEach((input) => {
    if (input.disabled || !input.matches("input, select, textarea")) return;
    const value = readFieldValue(input);
    if (value !== input.dataset.original) {
      values[input.dataset.key] = value;
    }
  });
  return values;
}

function updateDirtyState() {
  const count = Object.keys(changedValues()).length;
  byId("dirtyState").textContent =
    count === 0 ? "No changes" : `${count} unsaved change${count === 1 ? "" : "s"}`;
  byId("applyButton").disabled = count === 0;
}

async function validate(showResult = true) {
  const result = await api("/admin/api/config/validate", {
    method: "POST",
    body: JSON.stringify({ values: changedValues() }),
  });
  if (showResult) showValidationResult(result);
  return result;
}

function showValidationResult(result) {
  if (result.valid) {
    showMessage("Config shape is valid", "ok");
  } else {
    showMessage(result.errors.join("; "), "error");
  }
}

async function apply() {
  const result = await api("/admin/api/config/apply", {
    method: "POST",
    body: JSON.stringify({ values: changedValues() }),
  });
  if (!result.applied) {
    showValidationResult(result);
    return;
  }
  const restart = result.restart || {};
  if (restart.required && restart.automatic) {
    showMessage("Applied. Restarting server...", "ok");
    byId("applyButton").disabled = true;
    setTimeout(() => {
      window.location.href = restart.admin_url || "/admin";
    }, 1600);
    return;
  }
  const pending = restart.required ? restart.fields || [] : result.pending_fields || [];
  await load();
  showMessage(
    pending.length
      ? `Applied. Restart fcc-server to use: ${pending.join(", ")}`
      : "Applied",
    "ok",
  );
}

function syncModelDatalist() {
  let datalist = byId("model-options");
  if (!datalist) {
    datalist = document.createElement("datalist");
    datalist.id = "model-options";
    document.body.appendChild(datalist);
  }
  datalist.innerHTML = "";
  state.modelOptions.forEach((model) => datalist.appendChild(option(model, model)));
}

function showMessage(message, kind = "") {
  const area = byId("messageArea");
  area.textContent = message;
  area.className = `message-area ${kind}`.trim();
}

/* --------------------------------------------------------------- Models view */

const models = { initialized: false };

function ensureModels() {
  if (!models.initialized) {
    models.initialized = true;
    byId("checkModelsButton").addEventListener("click", (event) =>
      checkWorkingModels(event.currentTarget),
    );
    byId("refreshModelsButton").addEventListener("click", (event) =>
      refreshModelList(event.currentTarget),
    );
  }
  loadModelHealthMode();
  loadModelsStats();
}

async function loadModelsStats() {
  const row = byId("modelsStatRow");
  let working = 0;
  let providers = 0;
  try {
    const result = await api("/v1/models");
    const data = result.data || [];
    working = data.length;
    providers = new Set(
      data.map((model) => (model.id || "").split("/")[1]).filter(Boolean),
    ).size;
  } catch (error) {
    working = 0;
  }
  row.innerHTML = "";
  row.append(
    statCard({ icon: STAT_ICONS.models, label: "Working models", value: String(working) }),
    statCard({
      icon: STAT_ICONS.active,
      label: "Providers serving",
      value: String(providers),
    }),
  );
}

async function loadModelHealthMode() {
  try {
    const result = await api("/admin/api/models/health");
    renderModelHealthMode(result.model_list_mode, result.enabled);
  } catch (error) {
    /* health endpoint is best-effort */
  }
}

function renderModelHealthMode(mode, enabled) {
  const label = byId("modelHealthMode");
  if (!label) return;
  label.textContent = enabled === false ? "health off" : `mode: ${mode || "?"}`;
}

function renderModelHealthSummary(result) {
  const container = byId("modelHealthSummary");
  if (!container) return;
  container.innerHTML = "";
  const providers = result.providers || {};
  const ids = Object.keys(providers).sort();
  if (ids.length === 0) {
    container.textContent = "No discoverable models to check.";
    return;
  }
  ids.forEach((providerId) => {
    const bucket = providers[providerId];
    const row = document.createElement("div");
    row.className = "model-health-row";
    const ok = bucket.healthy || 0;
    const total = bucket.total || 0;
    row.textContent = `${providerId}: ${ok}/${total} working`;
    container.appendChild(row);
  });
  const total = result.total || {};
  const totalRow = document.createElement("div");
  totalRow.className = "model-health-row model-health-total";
  totalRow.textContent = `Total: ${total.healthy || 0}/${total.total || 0} working`;
  container.appendChild(totalRow);
  renderModelHealthMode(result.model_list_mode);
}

async function checkWorkingModels(button) {
  const original = button.textContent;
  button.disabled = true;
  button.textContent = "Checking…";
  const summary = byId("modelHealthSummary");
  if (summary) summary.textContent = "Checking models…";
  try {
    const result = await api("/admin/api/models/health-check", {
      method: "POST",
      body: "{}",
    });
    renderModelHealthSummary(result);
    loadModelsStats();
  } catch (error) {
    if (summary) summary.textContent = `Check failed: ${error.message}`;
  } finally {
    button.disabled = false;
    button.textContent = original;
  }
}

async function refreshModelList(button) {
  const original = button.textContent;
  button.disabled = true;
  button.textContent = "Refreshing…";
  try {
    await api("/admin/api/models/refresh", { method: "POST", body: "{}" });
    await loadModelsStats();
  } catch (error) {
    showMessage(`Refresh failed: ${error.message}`, "error");
  } finally {
    button.disabled = false;
    button.textContent = original;
  }
}

/* --------------------------------------------------------------- Dashboard */

const dashboard = { initialized: false, range: "24h", charts: {}, usage: null };

function ensureDashboard() {
  if (!dashboard.initialized) {
    dashboard.initialized = true;
    byId("rangeTabs")
      .querySelectorAll(".range-tab")
      .forEach((tab) =>
        tab.addEventListener("click", () => loadDashboard(tab.dataset.range)),
      );
    byId("dashRefresh").addEventListener("click", () => loadDashboard(dashboard.range));
  }
  loadDashboard(dashboard.range);
}

function setActiveRange(range) {
  dashboard.range = range;
  byId("rangeTabs")
    .querySelectorAll(".range-tab")
    .forEach((tab) => {
      const selected = tab.dataset.range === range;
      tab.classList.toggle("active", selected);
      if (selected) {
        tab.setAttribute("aria-selected", "true");
      } else {
        tab.removeAttribute("aria-selected");
      }
    });
}

async function loadDashboard(range) {
  setActiveRange(range);
  let usage = null;
  try {
    usage = await api(`/admin/api/usage?range=${encodeURIComponent(range)}`);
  } catch (error) {
    usage = null;
  }
  let workingModels = null;
  try {
    const result = await api("/v1/models");
    workingModels = (result.data || []).length;
  } catch (error) {
    workingModels = null;
  }
  dashboard.usage = usage;
  renderDashboard(usage, workingModels);
}

function formatNumber(value) {
  const num = Number(value) || 0;
  if (Math.abs(num) >= 1_000_000) return `${(num / 1_000_000).toFixed(1)}M`;
  if (Math.abs(num) >= 1_000) return `${(num / 1_000).toFixed(1)}k`;
  return String(Math.round(num));
}

function statCard({ icon, label, value, sub, tone = "brand" }) {
  const card = document.createElement("article");
  card.className = "stat-card";
  const iconBox = document.createElement("div");
  iconBox.className = `stat-icon tone-${tone}`;
  iconBox.innerHTML = icon || "";
  const body = document.createElement("div");
  body.className = "stat-body";
  const labelEl = document.createElement("div");
  labelEl.className = "stat-label";
  labelEl.textContent = label;
  const valueEl = document.createElement("div");
  valueEl.className = "stat-value";
  valueEl.textContent = value;
  body.append(labelEl, valueEl);
  if (sub) {
    const subEl = document.createElement("div");
    subEl.className = "stat-sub";
    subEl.textContent = sub;
    body.appendChild(subEl);
  }
  card.append(iconBox, body);
  return card;
}

function renderDashboard(usage, workingModels) {
  const totals = (usage && usage.totals) || {};
  const series = (usage && usage.series) || {};
  const hasData =
    usage && Array.isArray(series.labels) && series.labels.length > 0;
  byId("dashEmpty").hidden = Boolean(hasData);

  const row = byId("statRow");
  row.innerHTML = "";
  row.append(
    statCard({
      icon: STAT_ICONS.requests,
      label: "Total requests",
      value: formatNumber(totals.requests),
      sub: `in ${dashboard.range}`,
      tone: "brand",
    }),
    statCard({
      icon: STAT_ICONS.tokens,
      label: "Tokens (in + out)",
      value: formatNumber((totals.tokens_in || 0) + (totals.tokens_out || 0)),
      sub: `${formatNumber(totals.tokens_in)} in · ${formatNumber(totals.tokens_out)} out`,
      tone: "ok",
    }),
    statCard({
      icon: STAT_ICONS.errors,
      label: "Errors",
      value: formatNumber(totals.errors),
      sub: `in ${dashboard.range}`,
      tone: "error",
    }),
    statCard({
      icon: STAT_ICONS.latency,
      label: "Avg latency",
      value: `${formatNumber(totals.avg_latency_ms)} ms`,
      sub: "per request",
      tone: "warn",
    }),
    statCard({
      icon: STAT_ICONS.active,
      label: "Active models",
      value: formatNumber(totals.active_models),
      sub: `in ${dashboard.range}`,
      tone: "brand",
    }),
    statCard({
      icon: STAT_ICONS.models,
      label: "Working models",
      value: workingModels == null ? "—" : String(workingModels),
      sub: "available now",
      tone: "ok",
    }),
  );

  renderBudget((usage && usage.budget) || null);
  renderRecentTable((usage && usage.recent) || []);
  renderDashboardCharts();
}

function renderBudget(budget) {
  const card = byId("budgetCard");
  if (!card) return;
  const limit = budget && Number(budget.token_limit) > 0 ? Number(budget.token_limit) : 0;
  if (!limit) {
    card.hidden = true;
    return;
  }
  card.hidden = false;
  const used = Number(budget.tokens_used) || 0;
  const percent = Number(budget.percent_used) || 0;
  const clamped = Math.max(0, Math.min(100, percent));
  byId("budgetPercent").textContent = `${percent}%`;
  const fill = byId("budgetFill");
  fill.style.width = `${clamped}%`;
  fill.classList.toggle("over", percent >= 100);
  fill.classList.toggle("warn", percent >= 80 && percent < 100);
  byId("budgetMeta").textContent =
    `${formatNumber(used)} / ${formatNumber(limit)} tokens used in ${dashboard.range}`;
}

function renderRecentTable(recent) {
  const body = byId("recentBody");
  body.innerHTML = "";
  if (!recent.length) {
    const tr = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = 6;
    td.className = "table-empty";
    td.textContent = "No recent requests.";
    tr.appendChild(td);
    body.appendChild(tr);
    return;
  }
  recent.slice(0, 12).forEach((entry) => {
    const tr = document.createElement("tr");
    const time = document.createElement("td");
    time.textContent = formatTime(entry.ts);
    const model = document.createElement("td");
    model.className = "cell-strong";
    model.textContent = entry.model || "—";
    const provider = document.createElement("td");
    provider.textContent = entry.provider || "—";
    const status = document.createElement("td");
    const pill = document.createElement("span");
    pill.className = `status-pill ${statusClass(entry.status)}`;
    pill.textContent = entry.status || "—";
    status.appendChild(pill);
    const tokens = document.createElement("td");
    tokens.textContent = `${formatNumber(entry.tokens_in)} / ${formatNumber(entry.tokens_out)}`;
    const latency = document.createElement("td");
    latency.textContent = entry.latency_ms == null ? "—" : `${formatNumber(entry.latency_ms)} ms`;
    tr.append(time, model, provider, status, tokens, latency);
    body.appendChild(tr);
  });
}

function formatTime(ts) {
  if (!ts) return "—";
  const date = new Date(ts);
  if (Number.isNaN(date.getTime())) return String(ts);
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function chartPalette() {
  return [
    cssVar("--brand"),
    cssVar("--ok"),
    cssVar("--warn"),
    cssVar("--error"),
    cssVar("--brand-strong"),
    cssVar("--muted"),
  ];
}

function destroyDashboardCharts() {
  Object.values(dashboard.charts).forEach((chart) => chart && chart.destroy());
  dashboard.charts = {};
}

function renderDashboardCharts() {
  if (typeof Chart === "undefined") return;
  destroyDashboardCharts();

  const usage = dashboard.usage || {};
  const series = usage.series || {};
  const labels = series.labels || [];
  const text = cssVar("--text");
  const muted = cssVar("--muted");
  const line = cssVar("--line");
  const brand = cssVar("--brand");
  const ok = cssVar("--ok");

  Chart.defaults.color = muted;
  Chart.defaults.font.family =
    "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";

  const gridCfg = { color: line, drawBorder: false };

  const lineCanvas = byId("lineChart");
  if (lineCanvas) {
    dashboard.charts.line = new Chart(lineCanvas, {
      type: "line",
      data: {
        labels,
        datasets: [
          {
            label: "Requests",
            data: series.requests || [],
            borderColor: brand,
            backgroundColor: hexToRgba(brand, 0.14),
            fill: true,
            tension: 0.35,
            yAxisID: "y",
            pointRadius: 0,
            borderWidth: 2,
          },
          {
            label: "Output tokens",
            data: series.tokens_out || [],
            borderColor: ok,
            backgroundColor: "transparent",
            tension: 0.35,
            yAxisID: "y1",
            pointRadius: 0,
            borderWidth: 2,
          },
          {
            label: "Input tokens",
            data: series.tokens_in || [],
            borderColor: cssVar("--brand-strong"),
            backgroundColor: "transparent",
            tension: 0.35,
            yAxisID: "y1",
            pointRadius: 0,
            borderWidth: 2,
            borderDash: [5, 4],
          },
          {
            label: "Errors",
            data: series.errors || [],
            borderColor: cssVar("--error"),
            backgroundColor: "transparent",
            tension: 0.35,
            yAxisID: "y",
            pointRadius: 0,
            borderWidth: 2,
            hidden: true,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: { legend: { labels: { color: text, usePointStyle: true } } },
        scales: {
          x: { grid: { display: false }, ticks: { color: muted } },
          y: {
            beginAtZero: true,
            grid: gridCfg,
            ticks: { color: muted },
            title: { display: true, text: "Requests", color: muted },
          },
          y1: {
            beginAtZero: true,
            position: "right",
            grid: { display: false },
            ticks: { color: muted },
            title: { display: true, text: "Tokens", color: muted },
          },
        },
      },
    });
  }

  const byProvider = usage.by_provider || [];
  const doughnutCanvas = byId("doughnutChart");
  if (doughnutCanvas) {
    dashboard.charts.doughnut = new Chart(doughnutCanvas, {
      type: "doughnut",
      data: {
        labels: byProvider.map((entry) => entry.provider_id),
        datasets: [
          {
            data: byProvider.map((entry) => entry.requests || 0),
            backgroundColor: chartPalette(),
            borderColor: cssVar("--card"),
            borderWidth: 2,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "62%",
        plugins: {
          legend: { position: "bottom", labels: { color: text, usePointStyle: true } },
          tooltip: {
            callbacks: {
              label: (ctx) => {
                const row = byProvider[ctx.dataIndex] || {};
                return [
                  `Requests: ${formatNumber(row.requests)}`,
                  `Tokens: ${formatNumber(row.tokens)}`,
                  `Errors: ${formatNumber(row.errors)}`,
                ];
              },
            },
          },
        },
      },
    });
  }

  const byModel = (usage.by_model || [])
    .slice()
    .sort((a, b) => (b.requests || 0) - (a.requests || 0))
    .slice(0, 6);
  const barCanvas = byId("barChart");
  if (barCanvas) {
    dashboard.charts.bar = new Chart(barCanvas, {
      type: "bar",
      data: {
        labels: byModel.map((entry) => entry.model),
        datasets: [
          {
            label: "Requests",
            data: byModel.map((entry) => entry.requests || 0),
            backgroundColor: hexToRgba(brand, 0.85),
            borderRadius: 6,
            maxBarThickness: 38,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (ctx) => {
                const row = byModel[ctx.dataIndex] || {};
                return [
                  `Requests: ${formatNumber(row.requests)}`,
                  `Tokens: ${formatNumber(row.tokens)}`,
                  `Errors: ${formatNumber(row.errors)}`,
                  `Avg latency: ${formatNumber(row.avg_latency_ms)} ms`,
                ];
              },
            },
          },
        },
        scales: {
          x: { grid: { display: false }, ticks: { color: muted } },
          y: { beginAtZero: true, grid: gridCfg, ticks: { color: muted } },
        },
      },
    });
  }
}

function hexToRgba(hex, alpha) {
  const value = hex.trim();
  if (!value.startsWith("#")) return value;
  let h = value.slice(1);
  if (h.length === 3) h = h.split("").map((c) => c + c).join("");
  const int = parseInt(h, 16);
  const r = (int >> 16) & 255;
  const g = (int >> 8) & 255;
  const b = int & 255;
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

/* --------------------------------------------------------------- Chat */

const chat = {
  threads: new Map(),
  models: [],
  model: null,
  meta: null,
  streaming: false,
  initialized: false,
  controller: null,
};

function ensureChatInit() {
  if (chat.initialized) return;
  chat.initialized = true;
  wireChat();
  loadChatModels();
}

function wireChat() {
  const form = byId("chatForm");
  const input = byId("chatInput");
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    if (chat.streaming) {
      if (chat.controller) chat.controller.abort();
      return;
    }
    sendChat();
  });
  byId("chatNew").addEventListener("click", newChat);
  byId("chatSearch").addEventListener("input", (event) =>
    renderChatList(event.target.value),
  );
  input.addEventListener("input", () => autoGrow(input));
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (!chat.streaming) sendChat();
    }
  });
}

function modelMeta(model) {
  const id = model.id || "";
  const parts = id.split("/");
  const provider = parts.length >= 3 ? parts[1] : parts[0] || "model";
  const name = model.display_name || parts[parts.length - 1] || id;
  return { id, provider, name, initial: (provider[0] || "?").toUpperCase() };
}

async function loadChatModels() {
  try {
    const result = await api("/v1/models");
    chat.models = (result.data || []).map(modelMeta);
  } catch (error) {
    chat.models = [];
  }
  renderChatList("");

  if (chat.models.length && !chat.model) {
    const configured = state.fields.get("MODEL");
    const preferred = configured ? configured.value : "";
    const match =
      (preferred &&
        chat.models.find(
          (model) => model.id === `anthropic/${preferred}` || model.id.endsWith(`/${preferred}`),
        )) ||
      chat.models[0];
    selectModel(match);
  }
  renderChat();
}

function renderChatList(filter) {
  const list = byId("chatModelList");
  list.innerHTML = "";
  const needle = (filter || "").trim().toLowerCase();
  const matches = chat.models.filter(
    (model) =>
      !needle ||
      model.name.toLowerCase().includes(needle) ||
      model.provider.toLowerCase().includes(needle),
  );
  if (!matches.length) {
    const empty = document.createElement("div");
    empty.className = "chat-list-empty";
    empty.textContent = chat.models.length ? "No models match." : "No models available.";
    list.appendChild(empty);
    return;
  }
  matches.forEach((model) => {
    const row = document.createElement("button");
    row.type = "button";
    row.className = "chat-model-row";
    row.setAttribute("role", "option");
    if (chat.model === model.id) {
      row.classList.add("active");
      row.setAttribute("aria-selected", "true");
    }
    const avatar = document.createElement("div");
    avatar.className = "chat-avatar";
    avatar.textContent = model.initial;
    const text = document.createElement("div");
    text.className = "chat-row-text";
    const name = document.createElement("strong");
    name.textContent = model.name;
    const sub = document.createElement("span");
    sub.textContent = model.provider;
    text.append(name, sub);
    row.append(avatar, text);
    row.addEventListener("click", () => selectModel(model));
    list.appendChild(row);
  });
}

function selectModel(model) {
  if (!model) return;
  chat.model = model.id;
  chat.meta = model;
  byId("chatPeerAvatar").textContent = model.initial;
  byId("chatPeerName").textContent = model.name;
  byId("chatPeerSub").textContent = model.provider;
  renderChatList(byId("chatSearch").value);
  renderChat();
  byId("chatInput").focus();
}

function currentMessages() {
  if (!chat.model) return [];
  if (!chat.threads.has(chat.model)) chat.threads.set(chat.model, []);
  return chat.threads.get(chat.model);
}

function autoGrow(el) {
  el.style.height = "auto";
  el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
}

function setChatStreaming(streaming) {
  chat.streaming = streaming;
  const send = byId("chatSend");
  send.textContent = streaming ? "Stop" : "Send";
  send.classList.toggle("is-streaming", streaming);
}

function newChat() {
  if (chat.controller) chat.controller.abort();
  if (chat.model) chat.threads.set(chat.model, []);
  renderChat();
  const input = byId("chatInput");
  input.value = "";
  autoGrow(input);
  input.focus();
}

async function sendChat() {
  const input = byId("chatInput");
  const text = input.value.trim();
  const model = chat.model;
  if (!text || chat.streaming || !model) return;

  const messages = currentMessages();
  messages.push({ role: "user", content: text });
  input.value = "";
  autoGrow(input);
  const assistant = { role: "assistant", content: "" };
  messages.push(assistant);
  setChatStreaming(true);
  renderChat();

  chat.controller = new AbortController();
  try {
    const response = await fetch("/admin/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      signal: chat.controller.signal,
      body: JSON.stringify({
        model,
        messages: messages
          .slice(0, -1)
          .map((message) => ({ role: message.role, content: message.content })),
        max_tokens: 4096,
      }),
    });
    if (!response.ok || !response.body) {
      throw new Error(`${response.status} ${response.statusText}`);
    }
    await readChatStream(response.body, assistant);
  } catch (error) {
    if (error.name !== "AbortError") {
      appendChatError(assistant, error.message);
    }
  } finally {
    chat.controller = null;
    setChatStreaming(false);
    renderChat();
  }
}

async function readChatStream(body, assistant) {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const blocks = buffer.split("\n\n");
    buffer = blocks.pop();
    blocks.forEach((block) => handleSseBlock(block, assistant));
  }
  if (buffer.trim()) handleSseBlock(buffer, assistant);
}

function handleSseBlock(block, assistant) {
  block.split("\n").forEach((line) => {
    const trimmed = line.trimStart();
    if (!trimmed.startsWith("data:")) return;
    const data = trimmed.slice(5).trim();
    if (!data || data === "[DONE]") return;
    let payload;
    try {
      payload = JSON.parse(data);
    } catch (error) {
      return;
    }
    if (
      payload.type === "content_block_delta" &&
      payload.delta &&
      payload.delta.type === "text_delta"
    ) {
      assistant.content += payload.delta.text || "";
      updateStreamingMessage(assistant);
    } else if (payload.type === "error") {
      const message = (payload.error && payload.error.message) || "Unknown error";
      appendChatError(assistant, message);
    }
  });
}

function appendChatError(assistant, message) {
  assistant.content += `${assistant.content ? "\n\n" : ""}**Error:** ${message}`;
  assistant.error = true;
  updateStreamingMessage(assistant);
}

function renderChat() {
  const log = byId("chatLog");
  log.innerHTML = "";
  const messages = currentMessages();
  messages.forEach((message) => log.appendChild(renderMessage(message)));
  const empty = byId("chatEmpty");
  empty.hidden = messages.length > 0;
  const emptyTitle = empty.querySelector("h3");
  const emptyText = empty.querySelector("p");
  if (emptyTitle && emptyText) {
    if (chat.model) {
      emptyTitle.textContent = "Start the conversation";
      emptyText.textContent = `Messaging ${chat.meta ? chat.meta.name : "the selected model"}, fully local.`;
    } else {
      emptyTitle.textContent = "Pick a model to start";
      emptyText.textContent = "Chat through your configured free providers, fully local.";
    }
  }
  scrollChatToBottom();
}

function updateStreamingMessage(assistant) {
  const log = byId("chatLog");
  const last = log.lastElementChild;
  if (!last) return;
  const bubble = last.querySelector(".chat-bubble");
  if (bubble) {
    bubble.classList.toggle("error", Boolean(assistant.error));
    bubble.innerHTML = renderMarkdown(assistant.content) || "<span class='chat-cursor'></span>";
  }
  scrollChatToBottom();
}

function renderMessage(message) {
  const row = document.createElement("div");
  row.className = `chat-msg ${message.role}`;
  if (message.role === "assistant") {
    const role = document.createElement("div");
    role.className = "chat-role";
    role.textContent = chat.meta ? chat.meta.name : "Assistant";
    row.appendChild(role);
  }
  const bubble = document.createElement("div");
  bubble.className = `chat-bubble${message.error ? " error" : ""}`;
  if (message.role === "assistant") {
    bubble.innerHTML =
      renderMarkdown(message.content) ||
      (chat.streaming ? "<span class='chat-cursor'></span>" : "");
  } else {
    bubble.textContent = message.content;
  }
  row.appendChild(bubble);
  return row;
}

function scrollChatToBottom() {
  const scroll = byId("chatScroll");
  if (scroll) scroll.scrollTop = scroll.scrollHeight;
}

/* ----------------------------------------------------- Offline markdown */

function escapeHtml(text) {
  return text.replace(
    /[&<>"']/g,
    (char) =>
      ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      })[char],
  );
}

function renderInline(text) {
  let html = escapeHtml(text);
  html = html.replace(/`([^`]+)`/g, (_, code) => `<code>${code}</code>`);
  html = html.replace(
    /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
    (_, label, url) =>
      `<a href="${url}" target="_blank" rel="noopener noreferrer">${label}</a>`,
  );
  html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/(^|[^*])\*([^*\s][^*]*)\*/g, "$1<em>$2</em>");
  return html;
}

function renderMarkdown(src) {
  if (!src) return "";
  const blocks = [];
  let text = src.replace(/```(\w*)\n?([\s\S]*?)```/g, (_, _lang, code) => {
    const index = blocks.length;
    blocks.push(`<pre><code>${escapeHtml(code.replace(/\n$/, ""))}</code></pre>`);
    return ` ${index} `;
  });

  const out = [];
  let para = [];
  let list = null;
  const flushPara = () => {
    if (para.length) {
      out.push(`<p>${para.map(renderInline).join("<br>")}</p>`);
      para = [];
    }
  };
  const flushList = () => {
    if (list) {
      const items = list.items
        .map((item) => `<li>${renderInline(item)}</li>`)
        .join("");
      out.push(`<${list.type}>${items}</${list.type}>`);
      list = null;
    }
  };

  text.split("\n").forEach((line) => {
    const placeholder = line.match(/^ (\d+) $/);
    if (placeholder) {
      flushPara();
      flushList();
      out.push(blocks[Number(placeholder[1])]);
      return;
    }
    const heading = line.match(/^(#{1,6})\s+(.*)$/);
    if (heading) {
      flushPara();
      flushList();
      const level = heading[1].length;
      out.push(`<h${level}>${renderInline(heading[2])}</h${level}>`);
      return;
    }
    const unordered = line.match(/^\s*[-*+]\s+(.*)$/);
    const ordered = line.match(/^\s*\d+\.\s+(.*)$/);
    if (unordered) {
      flushPara();
      if (!list || list.type !== "ul") {
        flushList();
        list = { type: "ul", items: [] };
      }
      list.items.push(unordered[1]);
      return;
    }
    if (ordered) {
      flushPara();
      if (!list || list.type !== "ol") {
        flushList();
        list = { type: "ol", items: [] };
      }
      list.items.push(ordered[1]);
      return;
    }
    if (line.trim() === "") {
      flushPara();
      flushList();
      return;
    }
    para.push(line);
  });
  flushPara();
  flushList();
  return out.join("\n");
}

/* --------------------------------------------------------------- Wire-up */

initTheme();
byId("validateButton").addEventListener("click", () => validate(true));
byId("applyButton").addEventListener("click", apply);

load().catch((error) => {
  showMessage(error.message, "error");
});
