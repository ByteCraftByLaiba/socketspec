/**
 * SocketSpec Docs UI - main.js
 * Renders socket events using Swagger UI HTML class names for pixel-perfect
 * visual parity. No emojis anywhere in this file.
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

/** Maps event name to { editor, responseBlock, tryItActive } */
const tryItContexts = {};
/** Maps trigger event name to Set of server-sent event names */
const responseEventIndex = {};

/* --- DOM refs (created dynamically) --- */
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

function buildSchemaTable(s) {
  if (!s || !s.properties) {
    const p = document.createElement('p');
    p.style.cssText = 'color:#999;font-style:italic;margin:4px 0';
    p.textContent = 'No payload';
    return p;
  }
  const required = new Set(s.required || []);
  const table = document.createElement('table');
  table.className = 'socketspec-table';

  const thead = table.createTHead();
  const hrow = thead.insertRow();
  for (const col of ['Name', 'Type', 'Required', 'Description']) {
    const th = document.createElement('th');
    th.textContent = col;
    hrow.appendChild(th);
  }

  const tbody = table.createTBody();
  for (const [name, def] of Object.entries(s.properties)) {
    const row = tbody.insertRow();

    const tdName = row.insertCell(); tdName.className = 'col-name'; tdName.textContent = name;
    const tdType = row.insertCell(); tdType.className = 'col-type';
    tdType.textContent = def.type ?? (def.$ref ? 'object' : 'any');

    const tdReq = row.insertCell();
    if (required.has(name)) {
      const star = document.createElement('span');
      star.className = 'required-star'; star.textContent = '*';
      tdReq.appendChild(star);
    }

    const tdDesc = row.insertCell(); tdDesc.className = 'col-desc';
    tdDesc.textContent = def.description ?? def.title ?? '';
  }
  return table;
}

/* --- Card building --- */
function makeOpblock(direction, eventName, descText, schemaObj, isSubcard) {
  // direction: 'emit' | 'listen' | 'broadcast'
  const block = document.createElement('div');
  block.className = `opblock opblock-${direction}`;
  if (!isSubcard) block.id = `card-${eventName}`;

  // Summary row
  const summary = document.createElement('div');
  summary.className = 'opblock-summary';

  const method = document.createElement('button');
  method.className = 'opblock-summary-method';
  method.type = 'button';
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

  // Toggle on summary click
  summary.addEventListener('click', () => block.classList.toggle('is-open'));

  block.appendChild(summary);

  // Body
  const body = document.createElement('div');
  body.className = 'opblock-body';

  if (schemaObj !== undefined) {
    // Schema section inside subcard
    const sec = document.createElement('div');
    sec.className = 'opblock-section';
    const secHead = document.createElement('div');
    secHead.className = 'opblock-section-header';
    const h4 = document.createElement('h4'); h4.textContent = 'Schema';
    secHead.appendChild(h4);
    sec.appendChild(secHead);
    const inner = document.createElement('div');
    inner.className = 'table-container';
    inner.appendChild(buildSchemaTable(schemaObj));
    sec.appendChild(inner);
    body.appendChild(sec);
  }

  block.appendChild(body);
  return { block, body };
}

function buildTryItSection(event) {
  const wrapper = document.createElement('div');
  wrapper.style.cssText = 'display:flex;flex-direction:column;gap:8px;';

  const tryItBtn = document.createElement('button');
  tryItBtn.className = 'try-out__btn';
  tryItBtn.type = 'button';
  tryItBtn.textContent = 'Try it out';

  const editorArea = document.createElement('div');
  editorArea.style.display = 'none';

  const editor = document.createElement('textarea');
  editor.className = 'payload-editor';
  editor.value = JSON.stringify(exampleFromSchema(event.payload), null, 2);

  const btnRow = document.createElement('div');
  btnRow.style.cssText = 'display:flex;gap:8px;align-items:center;';

  const execBtn = document.createElement('button');
  execBtn.className = 'btn-execute';
  execBtn.type = 'button';
  execBtn.textContent = 'Execute';

  const cancelBtn = document.createElement('button');
  cancelBtn.className = 'btn-cancel-try';
  cancelBtn.type = 'button';
  cancelBtn.textContent = 'Cancel';

  btnRow.appendChild(execBtn);
  btnRow.appendChild(cancelBtn);
  editorArea.appendChild(editor);
  editorArea.appendChild(btnRow);

  const responseBlock = document.createElement('pre');
  responseBlock.className = 'response-block';
  responseBlock.style.display = 'none';

  tryItBtn.addEventListener('click', () => {
    tryItBtn.style.display = 'none';
    editorArea.style.display = 'block';
  });

  cancelBtn.addEventListener('click', () => {
    tryItBtn.style.display = '';
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

  tryItContexts[event.name] = { editor, responseBlock, editorArea, tryItBtn };

  wrapper.appendChild(tryItBtn);
  wrapper.appendChild(editorArea);
  wrapper.appendChild(responseBlock);
  return wrapper;
}

function buildErrorTable() {
  const errors = [
    { code: 'VALIDATION_ERROR',  desc: 'Payload failed Pydantic validation or JSON parsing failed.' },
    { code: 'RATE_LIMIT_ERROR',  desc: 'Connection exceeded the allowed rate limit.' },
    { code: 'UNKNOWN_EVENT',     desc: 'The sent event name has no registered handler.' },
    { code: 'PAYLOAD_TOO_LARGE', desc: 'Incoming frame exceeded the maximum payload size.' },
  ];
  const table = document.createElement('table');
  table.className = 'socketspec-table';
  const thead = table.createTHead();
  const hrow = thead.insertRow();
  ['Code', 'When it occurs'].forEach(col => {
    const th = document.createElement('th'); th.textContent = col; hrow.appendChild(th);
  });
  const tbody = table.createTBody();
  for (const e of errors) {
    const row = tbody.insertRow();
    const c1 = row.insertCell(); c1.className = 'col-name'; c1.textContent = e.code;
    const c2 = row.insertCell(); c2.className = 'col-desc'; c2.textContent = e.desc;
  }
  return table;
}

function buildSection(label, child) {
  const sec = document.createElement('div');
  sec.className = 'opblock-section';

  const head = document.createElement('div');
  head.className = 'opblock-section-header';
  const h5 = document.createElement('h5'); h5.textContent = label;
  head.appendChild(h5);
  sec.appendChild(head);

  const inner = document.createElement('div');
  inner.className = 'table-container';
  inner.appendChild(child);
  sec.appendChild(inner);
  return sec;
}

function buildEventCard(event) {
  const { block, body } = makeOpblock('emit', event.name, event.description || '', undefined, false);

  // Try it out button row (top right of body header)
  const tryHeader = document.createElement('div');
  tryHeader.className = 'opblock-section-header';
  const tryLabel = document.createElement('h4');
  tryLabel.textContent = 'Parameters';
  tryHeader.appendChild(tryLabel);
  tryHeader.appendChild(buildTryItSection(event));
  body.appendChild(tryHeader);

  // Parameters table
  const paramInner = document.createElement('div');
  paramInner.className = 'table-container';
  paramInner.appendChild(buildSchemaTable(event.payload));
  body.appendChild(paramInner);

  // Server responds section
  if (event.emits && event.emits.length > 0) {
    const emitWrap = document.createElement('div');
    emitWrap.style.cssText = 'display:flex;flex-direction:column;gap:8px;margin-top:8px';
    for (const em of event.emits) {
      const { block: sub } = makeOpblock('listen', em.event, em.description || '', em.schema, true);
      emitWrap.appendChild(sub);
    }
    body.appendChild(buildSection('Server responds to sender', emitWrap));
    responseEventIndex[event.name] = responseEventIndex[event.name] || new Set();
    for (const em of event.emits) responseEventIndex[event.name].add(em.event);
  }

  // Room broadcast section
  if (event.broadcasts && event.broadcasts.length > 0) {
    const bcastWrap = document.createElement('div');
    bcastWrap.style.cssText = 'display:flex;flex-direction:column;gap:8px;margin-top:8px';
    for (const bc of event.broadcasts) {
      const label = `${bc.event} — Room: ${bc.room || '?'}`;
      const { block: sub } = makeOpblock('broadcast', label, bc.description || '', bc.schema, true);
      bcastWrap.appendChild(sub);
    }
    body.appendChild(buildSection('Broadcast to room', bcastWrap));
  }

  // Error responses section (always shown)
  body.appendChild(buildSection('Error responses', buildErrorTable()));

  return block;
}

/* --- Render all events --- */
function renderEvents() {
  const root = document.getElementById('socketspec-ui');
  root.innerHTML = '';

  // swagger-ui wrapper
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

  ctrlDiv.appendChild(wsUrlInput);
  ctrlDiv.appendChild(connectBtn);
  ctrlDiv.appendChild(authBtnEl);
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
  logHeader.appendChild(logTitle);
  logHeader.appendChild(logFilterEl);
  logHeader.appendChild(clearBtn);

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
        ctx.responseBlock.textContent = JSON.stringify(data, null, 2);
      }
    }
  }

  // Route __error__ to all open try-it blocks
  if (ev === '__error__') {
    for (const ctx of Object.values(tryItContexts)) {
      if (ctx.editorArea.style.display !== 'none') {
        ctx.responseBlock.style.display = 'block';
        ctx.responseBlock.textContent = JSON.stringify(data, null, 2);
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
