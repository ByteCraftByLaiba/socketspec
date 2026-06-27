/**
 * SocketSpec Docs UI — main.js
 *
 * Swagger-style interactive event browser for WebSocket APIs.
 * Grouped by tag, collapsible tag sections, property tables,
 * exact Swagger-style Try-it-out flow, and live response blocks.
 *
 * Emojis are strictly forbidden in this UI.
 */

/* ─── State ──────────────────────────────────────────────────────────────── */
const DOCS_BASE = window.location.pathname.replace(/\/+$/, '');

let schema = { version: "", events: [] };
let socket = null;
let authToken = "";
let authApiKey = "";
let connId = null;

/** Maps event name → { editor, responseBody, tryItArea, tryItBtn, executeBtn } */
const tryItContexts = {};

/** Maps event name → set of "server sends" event names, for response routing. */
const responseEventIndex = {};

/* ─── DOM refs ───────────────────────────────────────────────────────────── */
const versionEl     = document.getElementById("version");
const sidebarEl     = document.getElementById("sidebar");
const contentEl     = document.getElementById("content");
const connectBtn    = document.getElementById("connect-btn");
const wsUrlInput    = document.getElementById("ws-url");
const logOutput     = document.getElementById("log-output");
const logFilter     = document.getElementById("log-filter");
const authModal     = document.getElementById("auth-modal");
const statusDot     = document.getElementById("status-dot");
const statusText    = document.getElementById("status-text");
const connIdDisplay = document.getElementById("conn-id-display");
const connHint      = document.getElementById("conn-hint");

/* ─── Logging ────────────────────────────────────────────────────────────── */
function logMessage(direction, data) {
  const timestamp = new Date().toTimeString().split(' ')[0];
  const text = typeof data === "string" ? data : JSON.stringify(data, null, 2);
  const line = `[${timestamp}] [${direction}] ${text}`;

  if (logFilter.value && !line.toLowerCase().includes(logFilter.value.toLowerCase())) {
    return;
  }

  const div = document.createElement("div");
  div.className = `log-line ${direction.toLowerCase()}`;
  div.textContent = line;
  logOutput.appendChild(div);
  logOutput.scrollTop = logOutput.scrollHeight;
}

/* ─── Schema helpers ─────────────────────────────────────────────────────── */
function exampleFromSchema(modelSchema) {
  if (!modelSchema || !modelSchema.properties) return {};
  const example = {};
  for (const [key, value] of Object.entries(modelSchema.properties)) {
    const t = value.type;
    if (t === "string")        example[key] = value.examples?.[0] ?? "";
    else if (t === "integer")  example[key] = 0;
    else if (t === "number")   example[key] = 0.0;
    else if (t === "boolean")  example[key] = false;
    else if (t === "array")    example[key] = [];
    else if (t === "object")   example[key] = {};
    else                       example[key] = null;
  }
  return example;
}

function buildSchemaTable(modelSchema) {
  if (!modelSchema || !modelSchema.properties) {
    const p = document.createElement("p");
    p.className = "schema-empty";
    p.textContent = "No payload schema defined.";
    return p;
  }

  const required = new Set(modelSchema.required || []);
  const table = document.createElement("table");
  table.className = "schema-table";

  const thead = table.createTHead();
  const hrow = thead.insertRow();
  for (const col of ["Name", "Type", "Required", "Description"]) {
    const th = document.createElement("th");
    th.textContent = col;
    hrow.appendChild(th);
  }

  const tbody = table.createTBody();
  for (const [name, def] of Object.entries(modelSchema.properties)) {
    const row = tbody.insertRow();

    const tdName = row.insertCell();
    tdName.className = "col-name";
    tdName.textContent = name;

    const tdType = row.insertCell();
    tdType.className = "col-type";
    tdType.textContent = def.type ?? (def.$ref ? "object" : "any");

    const tdReq = row.insertCell();
    tdReq.className = "col-req";
    if (required.has(name)) {
      tdReq.innerHTML = '<span class="required-asterisk">*</span>';
    } else {
      tdReq.textContent = "";
    }

    const tdDesc = row.insertCell();
    tdDesc.className = "col-desc";
    tdDesc.textContent = def.description ?? def.title ?? "";
  }

  return table;
}

/* ─── Card building ──────────────────────────────────────────────────────── */
function primaryDirection(event) {
  if (event.emits?.length || event.broadcasts?.length) return "emit";
  return "listen";
}

function makeBadge(cls, label) {
  const span = document.createElement("span");
  span.className = `badge ${cls}`;
  span.textContent = label;
  return span;
}

function makeSectionBlock(labelText, labelBadge, bodyEl) {
  const block = document.createElement("div");
  block.className = "section-block";

  const label = document.createElement("div");
  label.className = "section-label";
  label.textContent = labelText;
  if (labelBadge) label.appendChild(labelBadge);

  block.appendChild(label);
  block.appendChild(bodyEl);
  return block;
}

function showResponse(block, data, cls) {
  const responseBlock = block.closest('.response-block');
  responseBlock.style.display = "block";
  responseBlock.className = `response-block ${cls}`;
  block.textContent = JSON.stringify(data, null, 2);
}

/**
 * Build the Try-it-out section for an event card.
 * Implements the exact Swagger UI flow:
 * - A "Try it out" button is shown.
 * - Clicking it changes the button text to "Cancel".
 * - It displays the payload textarea editor and a blue "Execute" button.
 * - Clicking "Execute" sends the WebSocket event.
 * - Server responses are shown in a Response block below the editor.
 * - Clicking "Cancel" reverts all state.
 */
function buildTryItSection(event) {
  const wrapper = document.createElement("div");
  wrapper.className = "try-it-container";

  const tryItBtn = document.createElement("button");
  tryItBtn.className = "try-it-btn";
  tryItBtn.type = "button";
  tryItBtn.textContent = "Try it out";

  const tryItArea = document.createElement("div");
  tryItArea.className = "try-it-area";

  const editor = document.createElement("textarea");
  editor.className = "payload-editor";
  editor.rows = 8;
  editor.value = JSON.stringify(exampleFromSchema(event.payload), null, 2);

  const executeBtn = document.createElement("button");
  executeBtn.type = "button";
  executeBtn.className = "execute-btn";
  executeBtn.textContent = "Execute";

  const responseBlock = document.createElement("div");
  responseBlock.className = "response-block";
  responseBlock.style.display = "none";

  const responseLabel = document.createElement("div");
  responseLabel.className = "response-label";
  responseLabel.textContent = "Responses";

  const responseBody = document.createElement("pre");
  responseBody.className = "response-body";

  responseBlock.appendChild(responseLabel);
  responseBlock.appendChild(responseBody);

  tryItArea.appendChild(editor);
  tryItArea.appendChild(executeBtn);
  tryItArea.appendChild(responseBlock);

  // Try it out toggle flow
  tryItBtn.addEventListener("click", () => {
    if (tryItBtn.textContent === "Try it out") {
      tryItBtn.textContent = "Cancel";
      tryItBtn.classList.add("cancel-mode");
      tryItArea.style.display = "block";
    } else {
      tryItBtn.textContent = "Try it out";
      tryItBtn.classList.remove("cancel-mode");
      tryItArea.style.display = "none";
      responseBlock.style.display = "none";
    }
  });

  executeBtn.addEventListener("click", () => {
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      showResponse(responseBody, { error: "WebSocket is not connected." }, "error");
      return;
    }
    let payload;
    try {
      payload = JSON.parse(editor.value || "{}");
    } catch (err) {
      showResponse(responseBody, { error: `Invalid JSON: ${err.message}` }, "error");
      return;
    }
    const message = { event: event.name, payload };
    socket.send(JSON.stringify(message));
    logMessage("OUT", message);
    showResponse(responseBody, { status: "Sent event, waiting for response..." }, "success");
  });

  tryItContexts[event.name] = { editor, responseBody, tryItArea, tryItBtn, executeBtn };

  wrapper.appendChild(tryItBtn);
  wrapper.appendChild(tryItArea);
  return wrapper;
}

function buildCard(event) {
  const dir = primaryDirection(event);
  const isDeprecated = !!event.deprecated;

  const card = document.createElement("article");
  const dirClass = isDeprecated ? "deprecated" : dir;
  card.className = `card dir-${dirClass}`;
  card.id = `card-${event.name}`;

  // ── Header (Swagger operation row style) ──
  const header = document.createElement("div");
  header.className = "card-header";

  const badgeText = isDeprecated ? "DEPRECATED" : dir.toUpperCase();
  header.appendChild(makeBadge(dirClass, badgeText));

  const nameEl = document.createElement("span");
  nameEl.className = "event-name";
  nameEl.textContent = event.name;

  const descEl = document.createElement("span");
  descEl.className = "event-desc";
  descEl.textContent = event.description || "";

  const chevron = document.createElement("span");
  chevron.className = "chevron-card";
  chevron.textContent = "▼";

  header.appendChild(nameEl);
  header.appendChild(descEl);
  header.appendChild(chevron);

  header.addEventListener("click", () => card.classList.toggle("open"));
  card.appendChild(header);

  // ── Body ──
  const body = document.createElement("div");
  body.className = "card-body";

  // Section 1 — Parameters (Client sends)
  const parametersContainer = document.createElement("div");
  parametersContainer.className = "parameters-container";
  parametersContainer.appendChild(buildSchemaTable(event.payload));

  const section1 = makeSectionBlock("Parameters", null, parametersContainer);
  // Add Try-it-out flow at the top-right of the Parameters section
  section1.querySelector(".section-label").appendChild(buildTryItSection(event));
  body.appendChild(section1);

  // Section 2 — Server responds
  if (event.emits && event.emits.length > 0) {
    const emitsWrap = document.createElement("div");
    for (const emit of event.emits) {
      const subLabel = document.createElement("div");
      subLabel.className = "section-sub";
      subLabel.textContent = `socket.on("${emit.event}") ${emit.description ? "— " + emit.description : ""}`;
      emitsWrap.appendChild(subLabel);
      emitsWrap.appendChild(buildSchemaTable(emit.schema));
    }
    body.appendChild(
      makeSectionBlock("Server responds to sender", makeBadge("listen", "LISTEN"), emitsWrap)
    );

    responseEventIndex[event.name] = responseEventIndex[event.name] || new Set();
    for (const emit of event.emits) {
      responseEventIndex[event.name].add(emit.event);
    }
  }

  // Section 3 — Room broadcast
  if (event.broadcasts && event.broadcasts.length > 0) {
    const bcastWrap = document.createElement("div");
    for (const bcast of event.broadcasts) {
      const subLabel = document.createElement("div");
      subLabel.className = "section-sub";
      subLabel.textContent = `Room: ${bcast.room} — socket.on("${bcast.event}") ${bcast.description ? "— " + bcast.description : ""}`;
      bcastWrap.appendChild(subLabel);
      bcastWrap.appendChild(buildSchemaTable(bcast.schema));
    }
    body.appendChild(
      makeSectionBlock("Broadcast to room", makeBadge("broadcast", "BROADCAST"), bcastWrap)
    );
  }

  // Section 4 — Error responses (always shown)
  const errorTable = document.createElement("table");
  errorTable.className = "schema-table";

  const errorHead = errorTable.createTHead();
  const errorHeadRow = errorHead.insertRow();
  const errorH1 = document.createElement("th");
  errorH1.textContent = "Code";
  const errorH2 = document.createElement("th");
  errorH2.textContent = "When it occurs";
  errorHeadRow.appendChild(errorH1);
  errorHeadRow.appendChild(errorH2);

  const errorBody = errorTable.createTBody();
  const errorCodesMap = [
    { code: "VALIDATION_ERROR", desc: "Payload failed Pydantic validation constraints or JSON parsing failed." },
    { code: "RATE_LIMIT_ERROR", desc: "The connection exceeded its allowed rate limit." },
    { code: "UNKNOWN_EVENT", desc: "The sent event name has no registered handler." },
    { code: "PAYLOAD_TOO_LARGE", desc: "The incoming frame exceeded the maximum payload size." }
  ];
  for (const item of errorCodesMap) {
    const errorRow = errorBody.insertRow();
    const cellCode = errorRow.insertCell();
    cellCode.className = "col-name";
    cellCode.textContent = item.code;
    const cellDesc = errorRow.insertCell();
    cellDesc.className = "col-desc";
    cellDesc.textContent = item.desc;
  }

  body.appendChild(
    makeSectionBlock("Error responses", null, errorTable)
  );

  card.appendChild(body);
  return card;
}

/* ─── Render ──────────────────────────────────────────────────────────────── */
function renderEvents() {
  sidebarEl.innerHTML = "";
  contentEl.innerHTML = "";

  const groups = {};
  for (const event of schema.events) {
    const tag = event.tags?.[0] || event.namespace || "default";
    (groups[tag] = groups[tag] || []).push(event);
  }

  for (const [tag, events] of Object.entries(groups)) {
    // Sidebar Group Header
    const sidebarTagLabel = document.createElement("div");
    sidebarTagLabel.className = "sidebar-tag";
    sidebarTagLabel.textContent = tag;
    sidebarEl.appendChild(sidebarTagLabel);

    for (const event of events) {
      const dir = primaryDirection(event);
      const navBtn = document.createElement("button");
      navBtn.className = "sidebar-nav-btn";

      const navBadge = document.createElement("span");
      navBadge.className = `nav-badge ${dir}`;
      navBadge.textContent = dir === "emit" ? "E" : "L";

      navBtn.appendChild(navBadge);
      navBtn.appendChild(document.createTextNode(event.name));
      navBtn.type = "button";
      navBtn.addEventListener("click", () => {
        const card = document.getElementById(`card-${event.name}`);
        if (card) {
          card.classList.add("open");
          card.scrollIntoView({ behavior: "smooth", block: "start" });
        }
      });
      sidebarEl.appendChild(navBtn);
    }

    // Content tag group
    const group = document.createElement("div");
    group.className = "tag-group";

    const groupHeader = document.createElement("button");
    groupHeader.className = "tag-group-header";
    groupHeader.type = "button";
    groupHeader.innerHTML = `<span>${tag}</span><span class="tag-chevron">▼</span>`;
    groupHeader.addEventListener("click", () => {
      group.classList.toggle("collapsed");
    });

    const cardsWrapper = document.createElement("div");
    cardsWrapper.className = "tag-cards";

    for (const event of events) {
      cardsWrapper.appendChild(buildCard(event));
    }

    group.appendChild(groupHeader);
    group.appendChild(cardsWrapper);
    contentEl.appendChild(group);
  }
}

/* ─── Schema loading ─────────────────────────────────────────────────────── */
async function loadSchema() {
  try {
    const response = await fetch(`${DOCS_BASE}/schema`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    schema = await response.json();
    versionEl.textContent = `v${schema.version}`;
    renderEvents();
  } catch (err) {
    logMessage("SYS", { error: `Schema load failed: ${err.message}` });
  }
}

/* ─── Connection status ──────────────────────────────────────────────────── */
function setConnected(connected, id) {
  connId = id || null;
  statusDot.className = `status-dot ${connected ? "connected" : "disconnected"}`;
  statusText.textContent = connected ? "Connected" : "Disconnected";
  connIdDisplay.textContent = connected && id ? id : "";
  connHint.textContent = connected
    ? "Open another tab to test as a different user"
    : "";
  connectBtn.textContent = connected ? "Disconnect" : "Connect";
  connectBtn.classList.toggle("connected", connected);
}

/* ─── Incoming message routing ───────────────────────────────────────────── */
function routeIncomingToCard(data) {
  const serverEvent = data?.event;
  if (!serverEvent) return;

  for (const [triggerEvent, listenEvents] of Object.entries(responseEventIndex)) {
    if (listenEvents.has(serverEvent)) {
      const ctx = tryItContexts[triggerEvent];
      if (ctx && ctx.tryItArea.style.display !== "none") {
        showResponse(ctx.responseBody, data, "success");
      }
    }
  }

  if (serverEvent === "__error__") {
    for (const ctx of Object.values(tryItContexts)) {
      if (ctx.tryItArea.style.display !== "none") {
        showResponse(ctx.responseBody, data, "error");
      }
    }
  }
}

/* ─── WebSocket URL builder ──────────────────────────────────────────────── */
function buildWsUrl() {
  let url = wsUrlInput.value.trim();
  const params = new URLSearchParams();
  if (authToken)  params.set("token",   authToken);
  if (authApiKey) params.set("api_key", authApiKey);
  const query = params.toString();
  if (query) url += (url.includes("?") ? "&" : "?") + query;
  return url;
}

/* ─── Event listeners ────────────────────────────────────────────────────── */
connectBtn.addEventListener("click", () => {
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.close();
    return;
  }

  try {
    socket = new WebSocket(buildWsUrl());
  } catch (err) {
    logMessage("ERR", { error: `Invalid URL: ${err.message}` });
    return;
  }

  socket.onopen = () => {
    const shortId = "conn_" + Math.random().toString(36).slice(2, 7);
    setConnected(true, shortId);
    logMessage("SYS", { status: "connected", url: wsUrlInput.value });
  };

  socket.onclose = (ev) => {
    setConnected(false, null);
    logMessage("SYS", { status: "disconnected", code: ev.code, reason: ev.reason || "—" });
  };

  socket.onmessage = (ev) => {
    try {
      const parsed = JSON.parse(ev.data);
      if (parsed.event === '__ping__') {
        socket.send(JSON.stringify({ event: '__pong__', payload: {} }));
        return;
      }
      logMessage("IN", parsed);
      routeIncomingToCard(parsed);
    } catch {
      logMessage("IN", ev.data);
    }
  };

  socket.onerror = () => logMessage("ERR", { status: "WebSocket error" });
});

document.getElementById("auth-btn").addEventListener("click", () => authModal.showModal());

document.getElementById("auth-save").addEventListener("click", () => {
  authToken  = document.getElementById("auth-token").value.trim();
  authApiKey = document.getElementById("auth-api-key").value.trim();
  logMessage("SYS", { status: "credentials saved" });
});

document.getElementById("clear-log").addEventListener("click", () => {
  logOutput.innerHTML = "";
});

logFilter.addEventListener("input", () => {
  const val = logFilter.value.toLowerCase();
  for (const line of logOutput.children) {
    line.style.display = val && !line.textContent.toLowerCase().includes(val)
      ? "none"
      : "";
  }
});

/* ─── Boot ───────────────────────────────────────────────────────────────── */
setConnected(false, null);
loadSchema();
