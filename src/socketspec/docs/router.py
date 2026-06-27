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

"""HTTP routes serving the SocketSpec docs UI and schema JSON.

Owns docs HTTP endpoints. Does NOT own WebSocket transport or event routing.
"""

from __future__ import annotations

import logging
import sys
from importlib.resources import files
from typing import TYPE_CHECKING

from socketspec.docs.engine import DocsEngine

if TYPE_CHECKING:
    from fastapi import FastAPI

    from socketspec.app import SocketApp

logger = logging.getLogger(__name__)

BEARER_PREFIX = "bearer "
DOCS_UI_PACKAGE = "socketspec.docs.ui"


def mount_docs(app: FastAPI, socket_app: SocketApp) -> None:
    """Register docs UI and schema routes on a FastAPI application.

    FastAPI is imported lazily inside this function so that ``socketspec.docs``
    can be imported without FastAPI being installed — e.g. when mounting on a
    Starlette or Django adapter in a future phase.

    Args:
        app: The FastAPI application instance.
        socket_app: The mounted SocketSpec application.
    """
    # Lazy import — keeps this module framework-agnostic at import time.
    from fastapi import Request  # noqa: PLC0415
    from fastapi.responses import HTMLResponse, JSONResponse, Response  # noqa: PLC0415

    # Expose to module globals so FastAPI's runtime type annotation parsing
    # works with nested functions
    mod_globals = sys.modules[__name__].__dict__
    mod_globals["Request"] = Request
    mod_globals["Response"] = Response
    mod_globals["HTMLResponse"] = HTMLResponse
    mod_globals["JSONResponse"] = JSONResponse

    docs_url = socket_app._docs_url.rstrip("/")
    engine = DocsEngine(socket_app._registry)

    @app.get(docs_url, response_class=HTMLResponse, response_model=None)
    async def docs_index(request: Request) -> Response:
        _check_docs_access(request, socket_app._docs_access_token)
        html = (files(DOCS_UI_PACKAGE) / "index.html").read_text(encoding="utf-8")
        css = (files(DOCS_UI_PACKAGE) / "style.css").read_text(encoding="utf-8")
        js = (files(DOCS_UI_PACKAGE) / "main.js").read_text(encoding="utf-8")
        html = html.replace("{{DOCS_URL}}", docs_url)
        html = html.replace("{{INLINE_CSS}}", css)
        html = html.replace("{{INLINE_JS}}", js)
        return HTMLResponse(content=html)

    @app.get(f"{docs_url}/main.js", response_model=None)
    async def docs_main_js(request: Request) -> Response:
        _check_docs_access(request, socket_app._docs_access_token)
        content = (files(DOCS_UI_PACKAGE) / "main.js").read_text(encoding="utf-8")
        return Response(content=content, media_type="application/javascript")

    @app.get(f"{docs_url}/style.css", response_model=None)
    async def docs_style_css(request: Request) -> Response:
        _check_docs_access(request, socket_app._docs_access_token)
        content = (files(DOCS_UI_PACKAGE) / "style.css").read_text(encoding="utf-8")
        return Response(content=content, media_type="text/css")

    @app.get(f"{docs_url}/schema", response_model=None)
    async def docs_schema(request: Request) -> JSONResponse:
        _check_docs_access(request, socket_app._docs_access_token)
        return JSONResponse(content=engine.generate_schema())


def _check_docs_access(request: object, access_token: str | None) -> None:
    """Validate an optional bearer token or query-param token for docs access."""
    from fastapi import HTTPException, Request  # noqa: PLC0415

    if not isinstance(request, Request):  # pragma: no cover
        return
    if access_token is None:
        return

    authorization = request.headers.get("authorization", "")
    if authorization.lower().startswith(BEARER_PREFIX):
        provided = authorization[len(BEARER_PREFIX) :].strip()
        if provided == access_token:
            return

    if request.query_params.get("token") == access_token:
        return

    raise HTTPException(status_code=401, detail="Docs access token required")
