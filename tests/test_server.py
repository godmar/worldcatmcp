"""Offline tests: WorldCat is mocked with respx, MCP is exercised in-process."""

from __future__ import annotations

import json
import os

os.environ.setdefault("WC_API_CLIENT_KEY", "test-key")
os.environ.setdefault("WC_API_SECRET", "test-secret")
os.environ.setdefault("API_BASE_URL", "https://wc.test")

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from mcp import Client

from app import server
from app.config import Settings
from app.main import app
from app.worldcat import WorldCatClient, WorldCatError, _encode_params

BASE = "https://wc.test/worldcat/search/v2"
TOKEN_URL = "https://oauth.oclc.org/token"


@pytest.fixture
def wc():
    with respx.mock(assert_all_called=False) as mock:
        mock.post(TOKEN_URL).respond(json={"access_token": "tok-1", "expires_in": 1199})
        yield mock


@pytest.fixture(autouse=True)
def fresh_client(monkeypatch):
    """Give every test its own WorldCat client (no token cached across tests)."""
    monkeypatch.setattr(server, "client", WorldCatClient(Settings()))


def test_encode_params():
    assert _encode_params({
        "q": "ti:x", "limit": 5, "flag": True, "off": False, "none": None, "empty": [],
        "itemType": ["book", "video"], "creator": ["austen", "bronte"],
    }) == {
        "q": "ti:x", "limit": "5", "flag": "true", "off": "false",
        "itemType": "book,video", "creator": "austen|bronte",
    }


async def test_token_cached_and_sent(wc):
    route = wc.get(f"{BASE}/brief-bibs").respond(json={"numberOfRecords": 0})
    c = WorldCatClient(Settings())
    await c.get("/brief-bibs", {"q": "a"})
    await c.get("/brief-bibs", {"q": "b"})
    assert wc.calls.call_count == 3  # one token request, two searches
    assert route.calls[0].request.headers["Authorization"] == "Bearer tok-1"
    token_req = wc.calls[0].request
    assert b"grant_type=client_credentials" in token_req.content
    assert token_req.headers["Authorization"].startswith("Basic ")


async def test_token_refreshed_on_401(wc):
    wc.post(TOKEN_URL).mock(side_effect=[
        httpx.Response(200, json={"access_token": "old", "expires_in": 1199}),
        httpx.Response(200, json={"access_token": "new", "expires_in": 1199}),
    ])
    route = wc.get(f"{BASE}/bibs/1").mock(side_effect=[
        httpx.Response(401, json={"message": "expired"}),
        httpx.Response(200, json={"oclcNumber": "1"}),
    ])
    c = WorldCatClient(Settings())
    assert await c.get("/bibs/1") == {"oclcNumber": "1"}
    assert route.calls[1].request.headers["Authorization"] == "Bearer new"


async def test_error_is_raised(wc):
    wc.get(f"{BASE}/bibs/2").respond(404, json={"type": "NOT_FOUND", "title": "Not found",
                                                "detail": "no such record"})
    with pytest.raises(WorldCatError) as ei:
        await WorldCatClient(Settings()).get("/bibs/2")
    assert ei.value.status == 404 and ei.value.message == "no such record"


async def test_list_tools():
    async with Client(server.mcp) as c:
        tools = {t.name: t for t in (await c.list_tools()).tools}
    assert set(tools) == {
        "search_bibs", "get_bib", "get_other_editions", "get_holdings", "get_holdings_summary",
        "get_detailed_holdings", "get_retained_holdings", "search_my_holdings", "get_my_holding",
        "search_retained_holdings",
    }
    assert all(t.annotations and t.annotations.read_only_hint for t in tools.values())
    assert "q" in tools["search_bibs"].input_schema["required"]


async def test_search_bibs_maps_parameters(wc):
    route = wc.get(f"{BASE}/brief-bibs").respond(json={"numberOfRecords": 1, "briefRecords": [
        {"oclcNumber": "41266045", "title": "Simon's Cat"}]})
    async with Client(server.mcp) as c:
        res = await c.call_tool("search_bibs", {
            "q": "ti:Simon's Cat", "item_type": ["book", "video"], "held_by_symbol": ["VPI"],
            "show_holding_indicators": True, "limit": 5,
        })
    assert not res.is_error
    params = dict(route.calls[0].request.url.params)
    assert params == {"q": "ti:Simon's Cat", "itemType": "book,video", "heldBySymbol": "VPI",
                      "showHoldingsIndicators": "true", "offset": "0", "limit": "5"}
    data = res.structured_content or json.loads(res.content[0].text)
    assert data["briefRecords"][0]["oclcNumber"] == "41266045"


async def test_search_bibs_full_uses_bibs_endpoint(wc):
    route = wc.get(f"{BASE}/bibs").respond(json={"numberOfRecords": 0})
    async with Client(server.mcp) as c:
        res = await c.call_tool("search_bibs", {"q": "kw:x", "detail": "full"})
    assert not res.is_error and route.called


async def test_holdings_requires_identifier(wc):
    async with Client(server.mcp) as c:
        res = await c.call_tool("get_holdings", {})
    assert res.is_error
    assert "oclc_number" in res.content[0].text


async def test_api_error_becomes_tool_error(wc):
    wc.get(f"{BASE}/bibs/123").respond(404, json={"detail": "not found here"})
    async with Client(server.mcp) as c:
        res = await c.call_tool("get_bib", {"oclc_number": 123})
    assert res.is_error
    assert "404" in res.content[0].text and "not found here" in res.content[0].text


def test_health_endpoints():
    with TestClient(app) as http:
        assert http.get("/healthz").json() == {"status": "ok"}
        assert http.get("/readyz").status_code == 200
        assert http.get("/").json()["mcp_endpoint"] == "/mcp"
