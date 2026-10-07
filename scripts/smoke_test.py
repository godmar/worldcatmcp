#!/usr/bin/env python3
"""End-to-end smoke test against a running server (local or deployed).

Exercises both the stateless 2026-07-28 protocol and the legacy
initialize-handshake mode, plus several concurrent clients.

usage: python scripts/smoke_test.py [http://localhost:8000/mcp]
"""

from __future__ import annotations

import asyncio
import json
import sys

from mcp import Client


async def run_client(url: str, mode: str, query: str) -> str:
    async with Client(url, mode=mode) as c:
        tools = await c.list_tools()
        names = sorted(t.name for t in tools.tools)
        res = await c.call_tool("search_bibs", {"q": query, "limit": 3})
        if res.is_error:
            raise RuntimeError(f"search_bibs failed: {res.content}")
        data = res.structured_content or json.loads(res.content[0].text)
        recs = data.get("briefRecords", [])
        first = recs[0] if recs else {}
        line = (f"[{mode:9}] protocol={c.protocol_version} tools={len(names)} "
                f"q={query!r} hits={data.get('numberOfRecords')} "
                f"first={first.get('title')!r} ocn={first.get('oclcNumber')}")
        if first.get("oclcNumber"):
            res = await c.call_tool("get_holdings_summary", {"oclc_number": int(first["oclcNumber"])})
            if res.is_error:
                raise RuntimeError(f"get_holdings_summary failed: {res.content}")
            line += " holdings_summary=ok"
        return line


async def main(url: str) -> None:
    jobs = [
        run_client(url, "2026-07-28", "ti:moby dick AND au:melville"),
        run_client(url, "legacy", "su:machine learning"),
        run_client(url, "auto", "bn:9780439136358"),
        run_client(url, "2026-07-28", "kw:appalachian trail"),
    ]
    for line in await asyncio.gather(*jobs):
        print(line)
    print("OK")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000/mcp"))
