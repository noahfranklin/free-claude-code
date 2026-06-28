const state = {
  config: null,
  fields: new Map(),
  localStatus: new Map(),
  modelOptions: [],
  activeView: "providers",
};

const MASKED_SECRET = "********";
const VIEW_GROUPS = [
  {
    id: "providers",
    label: "Providers",
    title: "Providers",
    sections: ["providers", "runtime"],
    containerId: "providersSections",
  },
  {
    id: "model_config",
    label: "Model Config",
    title: "Model Config",
    sections: ["models", "thinking", "web_tools"],
    containerId: "modelConfigSections",
  },
  {
    id: "messaging",
    label: "Messaging",
    title: "Messaging",
    sections: ["messaging", "voice"],
    containerId: "messagingSections",
  },
  {
    id: "chat",
    label: "Chat",
    title: "Chat",
    chat: true,
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
  if (["configured", "reachable", "running"].includes(status)) return "ok";
  if (["missing_key", "missing_url", "unknown"].includes(status)) return "warn";
  if (["offline", "error"].includes(status)) return "error";
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
  VIEW_GROUPS.forEach((view, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `nav-link${index === 0 ? " active" : ""}`;
    button.dataset.view = view.id;
    button.textContent = view.label;
    if (index === 0) {
      button.setAttribute("aria-current", "page");
    }
    button.addEventListener("click", () => {
      setActiveView(view.id, { scroll: true });
    });
    nav.appendChild(button);
  });
  setActiveView(state.activeView, { scroll: false });
}

function setActiveView(viewId, { scroll = false } = {}) {
  const activeView =
    VIEW_GROUPS.find((view) => view.id === viewId) || VIEW_GROUPS[0];
  state.activeView = activeView.id;
  byId("pageTitle").textContent = activeView.title;

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

  const isChat = activeView.chat === true;
  document.querySelector(".app-shell").classList.toggle("chat-mode", isChat);
  if (isChat) {
    ensureChatInit();
  }

  if (scroll) {
    window.scrollTo({ top: 0, behavior: "smooth" });
  }
}

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
      sectionFields.forEach((field) => {
        grid.appendChild(renderField(field));
      });
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
  if (showResult) {
    showValidationResult(result);
  }
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

async function loadModelHealthMode() {
  try {
    const result = await api("/admin/api/models/health");
    renderModelHealthMode(result.model_list_mode, result.enabled);
  } catch (error) {
    // Health endpoint is best-effort; ignore load failures.
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
  } catch (error) {
    if (summary) summary.textContent = `Check failed: ${error.message}`;
  } finally {
    button.disabled = false;
    button.textContent = original;
  }
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

/* ------------------------------------------------------------------- Chat */

const chat = {
  messages: [],
  streaming: false,
  initialized: false,
  controller: null,
};

function ensureChatInit() {
  if (chat.initialized) return;
  chat.initialized = true;
  wireChat();
  renderChat();
  refreshChatModels();
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
  input.addEventListener("input", () => autoGrow(input));
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (!chat.streaming) sendChat();
    }
  });
}

async function refreshChatModels() {
  const select = byId("chatModel");
  try {
    const result = await api("/v1/models");
    const models = result.data || [];
    select.innerHTML = "";
    models.forEach((model) =>
      select.appendChild(option(model.id, model.display_name || model.id)),
    );
    const configured = state.fields.get("MODEL");
    const preferred = configured ? configured.value : "";
    if (preferred && models.some((model) => model.id === preferred)) {
      select.value = preferred;
    } else if (models.length) {
      select.value = models[0].id;
    }
  } catch (error) {
    select.innerHTML = "";
    select.appendChild(option("", "No models available"));
  }
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
  chat.messages = [];
  renderChat();
  const input = byId("chatInput");
  input.value = "";
  autoGrow(input);
  input.focus();
}

async function sendChat() {
  const input = byId("chatInput");
  const text = input.value.trim();
  const model = byId("chatModel").value;
  if (!text || chat.streaming || !model) return;

  chat.messages.push({ role: "user", content: text });
  input.value = "";
  autoGrow(input);
  const assistant = { role: "assistant", content: "" };
  chat.messages.push(assistant);
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
        messages: chat.messages
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
  chat.messages.forEach((message) => log.appendChild(renderMessage(message)));
  byId("chatEmpty").hidden = chat.messages.length > 0;
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
    role.textContent = "FC";
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
    return ` ${index} `;
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
    const placeholder = line.match(/^ (\d+) $/);
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

byId("validateButton").addEventListener("click", () => validate(true));
byId("applyButton").addEventListener("click", apply);
byId("checkModelsButton").addEventListener("click", (event) =>
  checkWorkingModels(event.currentTarget),
);

load()
  .then(loadModelHealthMode)
  .catch((error) => {
    showMessage(error.message, "error");
  });
