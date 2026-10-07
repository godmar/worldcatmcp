"""FastAPI application: health endpoints plus the MCP Streamable HTTP endpoint at /mcp."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from mcp.server.transport_security import TransportSecuritySettings

from . import __version__
from .config import settings
from .server import client, mcp

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    async with mcp.session_manager.run():
        yield
    await client.aclose()


# Build the MCP ASGI app first: it creates the session manager used in lifespan.
mcp_app = mcp.streamable_http_app(
    streamable_http_path="/mcp",
    # Stateless: no per-session state on the server. Clients speaking MCP
    # 2026-07-28 send self-contained requests (no initialize, no session id);
    # older clients get the legacy stateless Streamable HTTP mode. Either way,
    # any replica can serve any request and concurrent clients don't interact.
    stateless_http=True,
    json_response=True,
    # Public, unauthenticated server behind an Ingress: the localhost-oriented
    # DNS-rebinding Host check would only reject legitimate traffic.
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)

app = FastAPI(
    title="WorldCat MCP Server",
    version=__version__,
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


@app.get("/healthz", include_in_schema=False)
async def healthz():
    """Liveness: the process is up and serving requests."""
    return {"status": "ok"}


@app.get("/readyz", include_in_schema=False)
async def readyz():
    """Readiness: the server is configured with WorldCat credentials."""
    if not client.configured:
        return JSONResponse({"status": "unconfigured"}, status_code=503)
    return {"status": "ready"}


@app.get("/", include_in_schema=False)
async def index():
    return {
        "name": "WorldCat MCP Server",
        "version": __version__,
        "mcp_endpoint": "/mcp",
        "transport": "streamable-http (stateless)",
    }


# Mounted last so the routes above take precedence; serves /mcp.
app.mount("/", mcp_app)
