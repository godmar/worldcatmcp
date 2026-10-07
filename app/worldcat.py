"""Async client for the OCLC WorldCat Search API v2.

Authentication uses the OAuth2 client-credentials grant against
https://oauth.oclc.org/token. The access token is shared by all MCP sessions,
cached in memory, and refreshed shortly before it expires.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx

from .config import Settings

log = logging.getLogger(__name__)

API_PREFIX = "/worldcat/search/v2"
# Refresh the token this many seconds before the server says it expires.
TOKEN_SKEW = 60


class WorldCatError(Exception):
    """An error returned by WorldCat (or while talking to it)."""

    def __init__(self, status: int, message: str, detail: Any = None):
        super().__init__(f"WorldCat API error {status}: {message}")
        self.status = status
        self.message = message
        self.detail = detail


def _encode_params(params: dict[str, Any]) -> dict[str, str]:
    """Drop unset values and encode lists/bools the way WorldCat expects.

    Array parameters use `explode: false` (comma-separated), except `creator`
    which is pipe-delimited.
    """
    out: dict[str, str] = {}
    for key, value in params.items():
        if value is None or value == [] or value == "":
            continue
        if isinstance(value, bool):
            out[key] = "true" if value else "false"
        elif isinstance(value, (list, tuple)):
            sep = "|" if key == "creator" else ","
            out[key] = sep.join(str(v) for v in value)
        else:
            out[key] = str(value)
    return out


class WorldCatClient:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings
        self._http = httpx.AsyncClient(
            timeout=settings.http_timeout,
            transport=transport,
            headers={"Accept": "application/json", "User-Agent": "worldcat-mcp/0.1"},
        )
        self._token: str | None = None
        self._token_expires: float = 0.0
        self._lock = asyncio.Lock()

    async def aclose(self) -> None:
        await self._http.aclose()

    @property
    def configured(self) -> bool:
        return bool(self.settings.client_key and self.settings.client_secret)

    async def _get_token(self, force: bool = False) -> str:
        if not force and self._token and time.time() < self._token_expires - TOKEN_SKEW:
            return self._token
        async with self._lock:
            # Another request may have refreshed the token while we waited.
            if not force and self._token and time.time() < self._token_expires - TOKEN_SKEW:
                return self._token
            if not self.configured:
                raise WorldCatError(500, "WC_API_CLIENT_KEY / WC_API_SECRET are not configured")
            resp = await self._http.post(
                self.settings.token_url,
                data={"grant_type": "client_credentials", "scope": self.settings.scope},
                auth=(self.settings.client_key, self.settings.client_secret),
            )
            if resp.status_code != 200:
                raise WorldCatError(resp.status_code, "token request failed", _body(resp))
            body = resp.json()
            self._token = body["access_token"]
            self._token_expires = time.time() + float(body.get("expires_in", 1199))
            log.info("obtained WorldCat access token (expires in %ss)", body.get("expires_in"))
            return self._token

    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """GET `API_PREFIX + path` and return the decoded JSON body."""
        url = f"{self.settings.api_base_url}{API_PREFIX}{path}"
        query = _encode_params(params or {})
        for attempt in (1, 2):
            token = await self._get_token(force=attempt == 2)
            resp = await self._http.get(
                url, params=query, headers={"Authorization": f"Bearer {token}"}
            )
            # A 401 most likely means the cached token was revoked; retry once.
            if resp.status_code == 401 and attempt == 1:
                continue
            break
        if resp.status_code >= 400:
            body = _body(resp)
            message = resp.reason_phrase
            if isinstance(body, dict):
                message = body.get("detail") or body.get("title") or body.get("message") or message
            raise WorldCatError(resp.status_code, str(message), body)
        if not resp.content:
            return {}
        return resp.json()


def _body(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except ValueError:
        return resp.text[:2000]
