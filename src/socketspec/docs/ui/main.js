/**
 * SocketSpec Docs UI - main.js
 * Implements an exact Swagger UI replica with correct parameter schemas,
 * collapsible models, clean button states, and a responsive drawer layout.
 * No emojis are used in the UI or code.
 */

/* --- Constants --- */
const DOCS_BASE = window.location.pathname.replace(/\/+$/, '');

/* --- State --- */
let schema = { version: '', events: [] };
let socket = null;
let authToken = '';
let authApiKey = '';
let connId = null;
let isConnected = false;

/** Maps event name to try-it out context */
const tryItContexts = {};
/** Maps trigger event name to Set of server-sent event names */
const responseEventIndex = {};

/* --- DOM refs --- */
let statusDotEl = null;
let statusTextEl = null;
let statusConnIdEl = null;
let statusHintEl = null;
let connectBtn = null;
let wsUrlInput = null;
let logOutputEl = null;
let logFilterEl = null;
const authModal = document.getElementById('auth-modal');

/* --- Utility: build HH:MM:SS timestamp --- */
function timeStamp() {
  return new Date().toTimeString().slice(0, 8);
}

/* --- Logging --- */
function logMessage(direction, data) {
  if (!logOutputEl) return;
  const text = typeof data === 'string' ? data : JSON.stringify(data);
  const line = `[${timeStamp()}] ${direction} ${text}`;
  const filter = logFilterEl ? logFilterEl.value.toLowerCase() : '';
  if (filter && !line.toLowerCase().includes(filter)) return;

  const div = document.createElement('div');
  div.className = `log-${direction.toLowerCase()}`;
  div.textContent = line;
  logOutputEl.appendChild(div);
  logOutputEl.scrollTop = logOutputEl.scrollHeight;
}

/* --- Schema helpers --- */
function exampleFromSchema(s) {
  if (!s || !s.properties) return {};
  const out = {};
  for (const [k, v] of Object.entries(s.properties)) {
    const t = v.type;
    if (t === 'string')       out[k] = v.examples?.[0] ?? '';
    else if (t === 'integer') out[k] = 0;
    else if (t === 'number')  out[k] = 0.0;
    else if (t === 'boolean') out[k] = false;
    else if (t === 'array')   out[k] = [];
    else if (t === 'object')  out[k] = {};
    else                      out[k] = null;
  }
  return out;
}

/* --- Parameter / Schema Table (Swagger Style) --- */
function buildSchemaTable(s) {
  if (!s || !s.properties) {
    const p = document.createElement('p');
    p.style.cssText = 'color:#999;font-style:italic;margin:8px 0;font-size:0.85rem;';
    p.textContent = 'No payload schema';
    return p;
  }
  const required = new Set(s.required || []);
  const table = document.createElement('table');
  table.className = 'parameters-table';

  const thead = table.createTHead();
  const hrow = thead.insertRow();
  const thParam = document.createElement('th'); thParam.textContent = 'Parameter';
  const thDesc = document.createElement('th'); thDesc.textContent = 'Description';
  hrow.appendChild(thParam);
  hrow.appendChild(thDesc);

  const tbody = table.createTBody();
  for (const [name, def] of Object.entries(s.properties)) {
    const row = tbody.insertRow();

    // Column 1: Parameter name + metadata
    const tdParam = row.insertCell();
    tdParam.className = 'parameter__name';
    
    const nameSpan = document.createElement('span');
    nameSpan.textContent = name;
    tdParam.appendChild(nameSpan);

    if (required.has(name)) {
      const reqSpan = document.createElement('span');
      reqSpan.className = 'parameter__required';
      reqSpan.textContent = '* required';
      tdParam.appendChild(reqSpan);
    }

    const typeDiv = document.createElement('div');
    typeDiv.className = 'parameter__type';
    typeDiv.textContent = def.type ?? (def.$ref ? 'object' : 'any');
    tdParam.appendChild(typeDiv);

    const inDiv = document.createElement('div');
    inDiv.className = 'parameter__in';
    inDiv.textContent = '$(payload)';
    tdParam.appendChild(inDiv);

    // Column 2: Description
    const tdDesc = row.insertCell();
    const descDiv = document.createElement('div');
    descDiv.className = 'parameter__description';
    descDiv.textContent = def.description ?? def.title ?? '';
    tdDesc.appendChild(descDiv);
  }
  return table;
}

/* --- Collapsible Model Box (Swagger Style) --- */
function makeModelBox(title, schemaObj) {
  const box = document.createElement('div');
  box.className = 'model-box';

  const header = document.createElement('div');
  header.className = 'model-header';
  header.textContent = title || 'Model';

  const content = document.createElement('div');
  content.className = 'model-content';
  content.appendChild(buildSchemaTable(schemaObj));

  header.addEventListener('click', (e) => {
    e.stopPropagation(); // prevent parent card toggle
    box.classList.toggle('is-open');
  });

  box.appendChild(header);
  box.appendChild(content);
  return box;
}

/* --- Collapsible Opblock Container --- */
function makeOpblock(direction, eventName, descText, isSubcard) {
  // direction: 'emit' | 'listen' | 'broadcast'
  const block = document.createElement('div');
  block.className = `opblock opblock-${direction}`;
  if (!isSubcard) block.id = `card-${eventName}`;

  // Summary row
  const summary = document.createElement('div');
  summary.className = 'opblock-summary';

  const method = document.createElement('span');
  method.className = 'opblock-summary-method';
  method.textContent = direction.toUpperCase();

  const pathEl = document.createElement('div');
  pathEl.className = 'opblock-summary-path';
  const pathSpan = document.createElement('span');
  pathSpan.textContent = eventName;
  pathEl.appendChild(pathSpan);

  const descEl = document.createElement('div');
  descEl.className = 'opblock-summary-description';
  descEl.textContent = descText || '';

  summary.appendChild(method);
  summary.appendChild(pathEl);
  summary.appendChild(descEl);

  // Summary click collapses/expands the main card
  summary.addEventListener('click', () => {
    block.classList.toggle('is-open');
  });

  block.appendChild(summary);

  // Body
  const body = document.createElement('div');
  body.className = 'opblock-body';
  block.appendChild(body);

  return { block, body };
}

/* --- Error Table --- */
function buildErrorTable() {
  const errors = [
    { code: 'VALIDATION_ERROR',  desc: 'Payload failed Pydantic validation or JSON parsing failed.' },
    { code: 'RATE_LIMIT_ERROR',  desc: 'Connection exceeded the allowed rate limit.' },
    { code: 'UNKNOWN_EVENT',     desc: 'The sent event name has no registered handler.' },
    { code: 'PAYLOAD_TOO_LARGE', desc: 'Incoming frame exceeded the maximum payload size.' },
  ];
  const table = document.createElement('table');
  table.className = 'responses-table';
  
  const thead = table.createTHead();
  const hrow = thead.insertRow();
  const th1 = document.createElement('th'); th1.textContent = 'Code';
  const th2 = document.createElement('th'); th2.textContent = 'Description';
  hrow.appendChild(th1);
  hrow.appendChild(th2);

  const tbody = table.createTBody();
  for (const e of errors) {
    const row = tbody.insertRow();
    
    const tdCode = row.insertCell();
    tdCode.className = 'response-code';
    const strong = document.createElement('strong');
    strong.textContent = e.code;
    tdCode.appendChild(strong);

    const tdDesc = row.insertCell();
    tdDesc.className = 'parameter__description';
    tdDesc.textContent = e.desc;
  }
  return table;
}

/* --- Event Card --- */
function buildEventCard(event) {
  const { block, body } = makeOpblock('emit', event.name, event.description || '', false);

  // Try it out buttons
  const tryItBtn = document.createElement('button');
  tryItBtn.className = 'try-out__btn';
  tryItBtn.type = 'button';
  tryItBtn.textContent = 'Try it out';

  const cancelBtn = document.createElement('button');
  cancelBtn.className = 'btn-cancel-try';
  cancelBtn.type = 'button';
  cancelBtn.textContent = 'Cancel';
  cancelBtn.style.display = 'none';

  // Parameters Section Header
  const tryHeader = document.createElement('div');
  tryHeader.className = 'opblock-section-header';
  const tryLabel = document.createElement('h4');
  tryLabel.textContent = 'Parameters';
  tryHeader.appendChild(tryLabel);

  const btnWrapper = document.createElement('div');
  btnWrapper.appendChild(tryItBtn);
  btnWrapper.appendChild(cancelBtn);
  tryHeader.appendChild(btnWrapper);
  body.appendChild(tryHeader);

  // Parameters table container
  const paramInner = document.createElement('div');
  paramInner.className = 'table-container';
  paramInner.appendChild(buildSchemaTable(event.payload));
  body.appendChild(paramInner);

  // Editor wrapper
  const editorArea = document.createElement('div');
  editorArea.className = 'editor-wrapper';
  editorArea.style.display = 'none';

  const editorLabel = document.createElement('div');
  editorLabel.className = 'editor-title';
  editorLabel.textContent = 'Payload JSON';
  editorArea.appendChild(editorLabel);

  const editor = document.createElement('textarea');
  editor.className = 'payload-editor';
  editor.value = JSON.stringify(exampleFromSchema(event.payload), null, 2);
  editorArea.appendChild(editor);

  const execBtn = document.createElement('button');
  execBtn.className = 'btn-execute';
  execBtn.type = 'button';
  execBtn.textContent = 'Execute';
  editorArea.appendChild(execBtn);

  const responseBlock = document.createElement('pre');
  responseBlock.className = 'response-block';
  responseBlock.style.display = 'none';

  // Toggle behavior
  tryItBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    tryItBtn.style.display = 'none';
    cancelBtn.style.display = 'inline-block';
    editorArea.style.display = 'block';
  });

  cancelBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    tryItBtn.style.display = 'inline-block';
    cancelBtn.style.display = 'none';
    editorArea.style.display = 'none';
    responseBlock.style.display = 'none';
  });

  execBtn.addEventListener('click', () => {
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      responseBlock.style.display = 'block';
      responseBlock.textContent = 'Error: Connect first';
      return;
    }
    let payload;
    try { payload = JSON.parse(editor.value || '{}'); }
    catch (err) {
      responseBlock.style.display = 'block';
      responseBlock.textContent = `Invalid JSON: ${err.message}`;
      return;
    }
    const msg = { event: event.name, payload };
    socket.send(JSON.stringify(msg));
    logMessage('OUT', msg);
    responseBlock.style.display = 'block';
    responseBlock.textContent = 'Sent. Waiting for response...';
  });

  body.appendChild(editorArea);
  body.appendChild(responseBlock);

  tryItContexts[event.name] = { editor, responseBlock, editorArea, tryItBtn };

  // Responses section header
  const respSection = document.createElement('div');
  respSection.className = 'opblock-section';
  
  const respHeader = document.createElement('div');
  respHeader.className = 'opblock-section-header';
  const respLabel = document.createElement('h4');
  respLabel.textContent = 'Responses';
  respHeader.appendChild(respLabel);
  respSection.appendChild(respHeader);

  // Responses table
  const respTable = document.createElement('table');
  respTable.className = 'responses-table';
  
  const rthead = respTable.createTHead();
  const rhrow = rthead.insertRow();
  const rth1 = document.createElement('th'); rth1.textContent = 'Event / Code';
  const rth2 = document.createElement('th'); rth2.textContent = 'Description';
  rhrow.appendChild(rth1);
  rhrow.appendChild(rth2);

  const rtbody = respTable.createTBody();

  // Emits responses
  if (event.emits && event.emits.length > 0) {
    responseEventIndex[event.name] = responseEventIndex[event.name] || new Set();
    for (const em of event.emits) {
      const row = rtbody.insertRow();
      
      const tdEvent = row.insertCell();
      tdEvent.className = 'response-code';
      const badge = document.createElement('span');
      badge.className = 'resp-badge emit';
      badge.textContent = 'emit';
      const name = document.createElement('strong');
      name.textContent = em.event;
      tdEvent.appendChild(badge);
      tdEvent.appendChild(name);

      const tdDesc = row.insertCell();
      const descText = document.createElement('div');
      descText.className = 'parameter__description';
      descText.textContent = em.description || '';
      tdDesc.appendChild(descText);

      if (em.schema) {
        tdDesc.appendChild(makeModelBox('Model Schema', em.schema));
      }
      responseEventIndex[event.name].add(em.event);
    }
  }

  // Broadcasts responses
  if (event.broadcasts && event.broadcasts.length > 0) {
    responseEventIndex[event.name] = responseEventIndex[event.name] || new Set();
    for (const bc of event.broadcasts) {
      const row = rtbody.insertRow();

      const tdEvent = row.insertCell();
      tdEvent.className = 'response-code';
      const badge = document.createElement('span');
      badge.className = 'resp-badge broadcast';
      badge.textContent = 'broadcast';
      const name = document.createElement('strong');
      name.textContent = bc.event;
      
      const room = document.createElement('div');
      room.className = 'response-room';
      room.textContent = `Room: ${bc.room || '?'}`;

      tdEvent.appendChild(badge);
      tdEvent.appendChild(name);
      tdEvent.appendChild(room);

      const tdDesc = row.insertCell();
      const descText = document.createElement('div');
      descText.className = 'parameter__description';
      descText.textContent = bc.description || '';
      tdDesc.appendChild(descText);

      if (bc.schema) {
        tdDesc.appendChild(makeModelBox('Model Schema', bc.schema));
      }
      responseEventIndex[event.name].add(bc.event);
    }
  }

  // Standard errors list inside the responses table
  const stdErrors = [
    { code: 'VALIDATION_ERROR',  desc: 'Payload failed Pydantic validation.' },
    { code: 'RATE_LIMIT_ERROR',  desc: 'Connection exceeded the allowed rate limit.' },
    { code: 'UNKNOWN_EVENT',     desc: 'Sent event has no registered handler.' },
    { code: 'PAYLOAD_TOO_LARGE', desc: 'Incoming frame exceeded the maximum payload size.' },
  ];
  for (const err of stdErrors) {
    const row = rtbody.insertRow();
    
    const tdEvent = row.insertCell();
    tdEvent.className = 'response-code';
    const badge = document.createElement('span');
    badge.className = 'resp-badge error';
    badge.textContent = 'error';
    const name = document.createElement('strong');
    name.textContent = err.code;
    tdEvent.appendChild(badge);
    tdEvent.appendChild(name);

    const tdDesc = row.insertCell();
    const descText = document.createElement('div');
    descText.className = 'parameter__description';
    descText.textContent = err.desc;
    tdDesc.appendChild(descText);
  }

  respSection.appendChild(respTable);
  body.appendChild(respSection);

  return block;
}

/* --- Render all events --- */
function renderEvents() {
  const root = document.getElementById('socketspec-ui');
  root.innerHTML = '';

  const ui = document.createElement('div');
  ui.className = 'swagger-ui';

  // Topbar
  const topbar = document.createElement('div');
  topbar.className = 'socketspec-topbar';

  const brandDiv = document.createElement('div');
  brandDiv.style.cssText = 'display:flex;align-items:center;gap:8px;';
  const titleEl = document.createElement('h1');
  titleEl.className = 'title';
  titleEl.textContent = 'SocketSpec';
  const verEl = document.createElement('span');
  verEl.className = 'version';
  verEl.id = 'ver-badge';
  verEl.textContent = schema.version ? `v${schema.version}` : '';
  brandDiv.appendChild(titleEl);
  brandDiv.appendChild(verEl);

  const ctrlDiv = document.createElement('div');
  ctrlDiv.className = 'ws-controls';

  wsUrlInput = document.createElement('input');
  wsUrlInput.type = 'text';
  wsUrlInput.value = `ws://${location.host}/ws`;
  wsUrlInput.placeholder = 'ws://localhost:8000/ws';

  connectBtn = document.createElement('button');
  connectBtn.className = 'btn-connect';
  connectBtn.type = 'button';
  connectBtn.textContent = 'Connect';
  connectBtn.addEventListener('click', handleConnect);

  const authBtnEl = document.createElement('button');
  authBtnEl.className = 'btn-authorize';
  authBtnEl.type = 'button';
  authBtnEl.textContent = 'Authorize';
  authBtnEl.addEventListener('click', () => authModal.showModal());

  // Theme selector dropdown
  const themeSelect = document.createElement('select');
  themeSelect.id = 'theme-selector';
  themeSelect.style.cssText = 'padding:6px 12px; font-size:0.875rem; border:1px solid #444; border-radius:4px; background:#333; color:#fff; cursor:pointer; font-weight:700;';
  const optLight = document.createElement('option'); optLight.value = 'light'; optLight.textContent = 'Light Mode';
  const optDark = document.createElement('option'); optDark.value = 'dark'; optDark.textContent = 'Dark Mode';
  themeSelect.appendChild(optLight);
  themeSelect.appendChild(optDark);

  const savedTheme = localStorage.getItem('socketspec-theme') || 'light';
  themeSelect.value = savedTheme;
  document.body.className = `theme-${savedTheme}`;

  themeSelect.addEventListener('change', () => {
    const selected = themeSelect.value;
    document.body.className = `theme-${selected}`;
    localStorage.setItem('socketspec-theme', selected);
  });

  ctrlDiv.appendChild(wsUrlInput);
  ctrlDiv.appendChild(connectBtn);
  ctrlDiv.appendChild(authBtnEl);
  ctrlDiv.appendChild(themeSelect);
  topbar.appendChild(brandDiv);
  topbar.appendChild(ctrlDiv);
  ui.appendChild(topbar);

  // Status bar
  const statusBar = document.createElement('div');
  statusBar.className = 'socketspec-status-bar';
  statusDotEl = document.createElement('span');
  statusDotEl.className = 'status-dot';
  statusTextEl = document.createElement('span');
  statusTextEl.textContent = 'Disconnected';
  statusConnIdEl = document.createElement('span');
  statusConnIdEl.className = 'status-conn-id';
  statusHintEl = document.createElement('span');
  statusHintEl.className = 'status-hint';
  statusBar.appendChild(statusDotEl);
  statusBar.appendChild(statusTextEl);
  statusBar.appendChild(statusConnIdEl);
  statusBar.appendChild(statusHintEl);
  ui.appendChild(statusBar);

  // Info block
  const infoContainer = document.createElement('div');
  infoContainer.className = 'information-container wrapper';
  const infoDiv = document.createElement('div');
  infoDiv.className = 'info';
  const infoTitle = document.createElement('h2');
  infoTitle.className = 'title';
  infoTitle.textContent = 'SocketSpec';
  const infoVersion = document.createElement('span');
  infoVersion.className = 'version';
  infoVersion.textContent = schema.version ? `v${schema.version}` : '';
  infoTitle.appendChild(infoVersion);
  infoDiv.appendChild(infoTitle);
  infoContainer.appendChild(infoDiv);
  ui.appendChild(infoContainer);

  // Group by tag
  const groups = {};
  for (const ev of schema.events) {
    const tag = ev.tags?.[0] || ev.namespace || 'default';
    (groups[tag] = groups[tag] || []).push(ev);
  }

  const wrapper = document.createElement('div');
  wrapper.className = 'wrapper';

  for (const [tag, events] of Object.entries(groups)) {
    const tagSection = document.createElement('div');
    tagSection.className = 'opblock-tag-section';

    const tagHeader = document.createElement('div');
    tagHeader.className = 'opblock-tag';
    const tagH4 = document.createElement('h4');
    tagH4.className = 'opblock-tag';
    tagH4.style.cssText = 'text-transform:uppercase;font-size:1rem;';
    tagH4.textContent = tag;
    tagHeader.appendChild(tagH4);
    tagSection.appendChild(tagHeader);

    for (const ev of events) {
      tagSection.appendChild(buildEventCard(ev));
    }

    wrapper.appendChild(tagSection);
  }

  ui.appendChild(wrapper);

  // Log drawer
  const logDrawer = document.createElement('div');
  logDrawer.className = 'socketspec-log';

  const logHeader = document.createElement('div');
  logHeader.className = 'log-header';
  const logTitle = document.createElement('strong');
  logTitle.textContent = 'Live Log';

  logFilterEl = document.createElement('input');
  logFilterEl.type = 'text';
  logFilterEl.placeholder = 'Filter...';
  logFilterEl.addEventListener('input', () => {
    const val = logFilterEl.value.toLowerCase();
    for (const el of (logOutputEl ? logOutputEl.children : [])) {
      el.style.display = val && !el.textContent.toLowerCase().includes(val) ? 'none' : '';
    }
  });

  const clearBtn = document.createElement('button');
  clearBtn.textContent = 'Clear';
  clearBtn.addEventListener('click', () => { if (logOutputEl) logOutputEl.innerHTML = ''; });

  const minBtn = document.createElement('button');
  minBtn.textContent = 'Minimize';
  minBtn.addEventListener('click', () => {
    logDrawer.classList.toggle('is-minimized');
    minBtn.textContent = logDrawer.classList.contains('is-minimized') ? 'Maximize' : 'Minimize';
  });

  logHeader.appendChild(logTitle);
  logHeader.appendChild(logFilterEl);
  logHeader.appendChild(clearBtn);
  logHeader.appendChild(minBtn);

  logOutputEl = document.createElement('pre');
  logOutputEl.id = 'log-output';

  logDrawer.appendChild(logHeader);
  logDrawer.appendChild(logOutputEl);
  ui.appendChild(logDrawer);

  root.appendChild(ui);
}

/* --- Schema load --- */
async function loadSchema() {
  try {
    const res = await fetch(`${DOCS_BASE}/schema`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    schema = await res.json();
    renderEvents();
    logMessage('SYS', `Schema loaded — ${schema.events.length} event(s)`);
  } catch (err) {
    console.error('Schema load failed:', err);
    const root = document.getElementById('socketspec-ui');
    root.innerHTML = `<p style="color:red;padding:20px">Failed to load schema: ${err.message}</p>`;
  }
}

/* --- Connection status update --- */
function setConnected(connected, id) {
  isConnected = connected;
  connId = id || null;
  if (!statusDotEl) return;
  statusDotEl.className = `status-dot${connected ? ' connected' : ''}`;
  statusTextEl.textContent = connected ? 'Connected' : 'Disconnected';
  statusConnIdEl.textContent = connected && id ? id : '';
  statusHintEl.textContent = connected ? 'Open another tab to test as a different user' : '';
  if (connectBtn) {
    connectBtn.textContent = connected ? 'Disconnect' : 'Connect';
    connectBtn.classList.toggle('connected', connected);
  }
}

/* --- Route incoming to try-it context --- */
function routeIncoming(data) {
  const ev = data?.event;
  if (!ev) return;

  // Route to sender's try-it block
  for (const [trigger, listenSet] of Object.entries(responseEventIndex)) {
    if (listenSet.has(ev)) {
      const ctx = tryItContexts[trigger];
      if (ctx && ctx.editorArea.style.display !== 'none') {
        ctx.responseBlock.style.display = 'block';
        const currentText = ctx.responseBlock.textContent;
        const cleanText = (currentText === 'Sent. Waiting for response...' || currentText.startsWith('Error:')) ? '' : currentText;
        ctx.responseBlock.textContent = (cleanText ? cleanText + '\n' : '') + JSON.stringify(data, null, 2);
      }
    }
  }

  // Route __error__ to all open try-it blocks
  if (ev === '__error__') {
    for (const ctx of Object.values(tryItContexts)) {
      if (ctx.editorArea.style.display !== 'none') {
        ctx.responseBlock.style.display = 'block';
        const currentText = ctx.responseBlock.textContent;
        const cleanText = (currentText === 'Sent. Waiting for response...' || currentText.startsWith('Error:')) ? '' : currentText;
        ctx.responseBlock.textContent = (cleanText ? cleanText + '\n' : '') + JSON.stringify(data, null, 2);
      }
    }
  }

  // Grab conn_id from first welcome/connect message
  if (!connId && data.payload?.conn_id) {
    setConnected(true, data.payload.conn_id);
  }
}

/* --- WebSocket URL builder --- */
function buildWsUrl() {
  let url = wsUrlInput ? wsUrlInput.value.trim() : `ws://${location.host}/ws`;
  const params = new URLSearchParams();
  if (authToken)  params.set('token',   authToken);
  if (authApiKey) params.set('api_key', authApiKey);
  const q = params.toString();
  if (q) url += (url.includes('?') ? '&' : '?') + q;
  return url;
}

/* --- Connect / Disconnect handler --- */
function handleConnect() {
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.close();
    return;
  }
  try {
    socket = new WebSocket(buildWsUrl());
  } catch (err) {
    logMessage('SYS', `Invalid URL: ${err.message}`);
    return;
  }

  socket.onopen = () => {
    setConnected(true, null);
    logMessage('SYS', `Connected to ${wsUrlInput ? wsUrlInput.value : ''}`);
  };

  socket.onclose = (ev) => {
    setConnected(false, null);
    logMessage('SYS', `Disconnected (code ${ev.code})`);
    socket = null;
  };

  socket.onmessage = (ev) => {
    try {
      const data = JSON.parse(ev.data);
      // Handle ping — respond with pong silently
      if (data.event === '__ping__') {
        socket.send(JSON.stringify({ event: '__pong__', payload: {} }));
        return;
      }
      logMessage('IN', data);
      routeIncoming(data);
    } catch {
      logMessage('IN', ev.data);
    }
  };

  socket.onerror = () => logMessage('SYS', 'WebSocket error');
}

/* --- Auth modal --- */
document.getElementById('auth-save').addEventListener('click', () => {
  authToken  = document.getElementById('auth-token').value.trim();
  authApiKey = document.getElementById('auth-api-key').value.trim();
  logMessage('SYS', 'Credentials saved');
});

/* --- Boot --- */
loadSchema();
