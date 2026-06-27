# Copyright (c) 2025 Laiba Shahab. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Debug log SSE router. Only mounted when SocketApp(debug=True)."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI

    from socketspec.app import SocketApp

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# HTML page (all inline — zero external dependencies)
# ---------------------------------------------------------------------------

_DEBUG_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>SocketSpec Debug</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: system-ui, sans-serif; background: #0f1117; color: #c9d1d9; }

    /* Topbar */
    .topbar {
      background: #1b1b1b; padding: 10px 20px;
      display: flex; align-items: center; gap: 12px;
      border-bottom: 2px solid #49cc90;
    }
    .topbar h1 { font-size: 1.1rem; font-weight: 700; color: #fff; }
    .topbar .badge {
      font-size: 0.7rem; padding: 2px 8px; border-radius: 12px;
      background: #49cc90; color: #000; font-weight: 700;
    }
    .topbar .badge.disconnected { background: #f93e3e; color: #fff; }
    #conn-count { margin-left: auto; font-size: 0.75rem; color: #888; }

    /* Toolbar */
    .toolbar {
      display: flex; gap: 8px; align-items: center;
      padding: 8px 16px; background: #161b22; border-bottom: 1px solid #30363d;
    }
    .toolbar input {
      flex: 1; background: #0d1117; border: 1px solid #30363d;
      color: #c9d1d9; padding: 5px 10px; border-radius: 4px; font-size: 0.8rem;
    }
    .toolbar button {
      background: transparent; border: 1px solid #444; color: #888;
      padding: 5px 12px; border-radius: 4px; cursor: pointer; font-size: 0.8rem;
    }
    .toolbar button:hover { background: #21262d; color: #fff; }

    /* Log list */
    #log-list { list-style: none; padding: 0; }
    .log-item {
      display: grid;
      grid-template-columns: 180px 100px 200px 1fr;
      gap: 8px; align-items: start;
      padding: 6px 16px; border-bottom: 1px solid #21262d;
      font-size: 0.8rem; font-family: monospace;
    }
    .log-item:hover { background: #161b22; }
    .log-item .ts { color: #555; }
    .log-item .badge {
      font-size: 0.65rem; font-weight: 700; padding: 2px 8px;
      border-radius: 3px; text-align: center; text-transform: uppercase;
    }
    .badge-connect    { background: #49cc90; color: #000; }
    .badge-disconnect { background: #f93e3e; color: #fff; }
    .badge-event      { background: #61affe; color: #fff; }
    .badge-emit       { background: #555; color: #ccc; }
    .log-item .conn-id { color: #888; }
    .log-item .detail  { color: #c9d1d9; word-break: break-all; }

    #scroll-wrapper { height: calc(100vh - 110px); overflow-y: auto; }
  </style>
</head>
<body>
  <div class="topbar">
    <h1>SocketSpec Debug</h1>
    <span class="badge disconnected" id="sse-badge">Connecting</span>
    <span id="conn-count">0 entries</span>
  </div>
  <div class="toolbar">
    <input id="filter" type="text" placeholder="Filter by conn_id or event..." />
    <button id="clear-btn">Clear</button>
    <button id="pause-btn">Pause</button>
  </div>
  <div id="scroll-wrapper">
    <ul id="log-list"></ul>
  </div>

  <script>
    const STREAM_URL = '{{DEBUG_URL}}/stream';
    const list = document.getElementById('log-list');
    const filterInput = document.getElementById('filter');
    const sseBadge = document.getElementById('sse-badge');
    const countEl = document.getElementById('conn-count');
    let count = 0;
    let paused = false;

    const badgeClass = {
      connect: 'badge-connect',
      disconnect: 'badge-disconnect',
      event: 'badge-event',
      emit: 'badge-emit',
    };

    function addEntry(entry) {
      count++;
      countEl.textContent = `${count} entries`;

      const li = document.createElement('li');
      li.className = 'log-item';
      li.dataset.raw = JSON.stringify(entry).toLowerCase();

      const filter = filterInput.value.toLowerCase();
      if (filter && !li.dataset.raw.includes(filter)) li.style.display = 'none';

      const ts = document.createElement('span');
      ts.className = 'ts';
      ts.textContent = entry.ts ? entry.ts.slice(0, 23).replace('T', ' ') : '';

      const badge = document.createElement('span');
      badge.className = `badge ${badgeClass[entry.type] || 'badge-emit'}`;
      badge.textContent = entry.type || '?';

      const connId = document.createElement('span');
      connId.className = 'conn-id';
      connId.textContent = (entry.conn_id || '').slice(0, 8);

      const detail = document.createElement('span');
      detail.className = 'detail';
      const parts = [];
      if (entry.event)        parts.push(`event=${entry.event}`);
      if (entry.user_id)      parts.push(`user=${entry.user_id}`);
      if (entry.reason)       parts.push(`reason=${entry.reason}`);
      if (entry.payload_size) parts.push(`size=${entry.payload_size}B`);
      detail.textContent = parts.join('  ');

      li.appendChild(ts);
      li.appendChild(badge);
      li.appendChild(connId);
      li.appendChild(detail);
      list.appendChild(li);

      const wrapper = document.getElementById('scroll-wrapper');
      if (!paused) wrapper.scrollTop = wrapper.scrollHeight;
    }

    // SSE
    let es = new EventSource(STREAM_URL);
    es.onopen = () => {
      sseBadge.textContent = 'Connected';
      sseBadge.className = 'badge';
    };
    es.onmessage = (e) => {
      if (paused) return;
      try { addEntry(JSON.parse(e.data)); } catch {}
    };
    es.onerror = () => {
      sseBadge.textContent = 'Reconnecting';
      sseBadge.className = 'badge disconnected';
    };

    // Filter
    filterInput.addEventListener('input', () => {
      const val = filterInput.value.toLowerCase();
      for (const li of list.children) {
        li.style.display = val && !li.dataset.raw.includes(val) ? 'none' : '';
      }
    });

    // Clear
    document.getElementById('clear-btn').addEventListener('click', () => {
      list.innerHTML = '';
      count = 0;
      countEl.textContent = '0 entries';
    });

    // Pause/Resume
    const pauseBtn = document.getElementById('pause-btn');
    pauseBtn.addEventListener('click', () => {
      paused = !paused;
      pauseBtn.textContent = paused ? 'Resume' : 'Pause';
    });
  </script>
</body>
</html>
"""


def _build_debug_html(debug_url: str) -> str:
    return _DEBUG_HTML.replace("{{DEBUG_URL}}", debug_url)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


def mount_debug(app: FastAPI, socket_app: SocketApp) -> None:
    """Register the debug log page and its SSE stream endpoint."""
    import sys  # noqa: PLC0415

    from fastapi import Request  # noqa: PLC0415
    from fastapi.responses import HTMLResponse, StreamingResponse  # noqa: PLC0415

    mod_globals = sys.modules[__name__].__dict__
    mod_globals["Request"] = Request
    mod_globals["HTMLResponse"] = HTMLResponse
    mod_globals["StreamingResponse"] = StreamingResponse

    debug_url = socket_app._debug_url.rstrip("/")
    queue = socket_app._debug_queue

    @app.get(debug_url, response_model=None)
    async def debug_index(request: Request) -> HTMLResponse:
        return HTMLResponse(content=_build_debug_html(debug_url))

    @app.get(f"{debug_url}/stream", response_model=None)
    async def debug_stream(request: Request) -> StreamingResponse:
        async def event_generator() -> AsyncIterator[str]:
            # Guarded: mount_debug only called when debug=True
            assert queue is not None
            while True:
                if await request.is_disconnected():
                    break
                try:
                    entry = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {json.dumps(entry)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    logger.info("Debug UI mounted at %s", debug_url)
