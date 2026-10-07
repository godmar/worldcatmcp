# Architecture

```
MCP client ──HTTPS──> nginx Ingress ──> Service ──> Pod(s): uvicorn + FastAPI
                                                      ├── /healthz, /readyz, /   (FastAPI routes)
                                                      └── /mcp   (MCP SDK Streamable HTTP app, stateless)
                                                              └── tools ──> WorldCatClient ──HTTPS──> WorldCat Search API v2
                                                                                 └── OAuth2 client credentials (oauth.oclc.org)
```

## Code layout

| Path | Role |
|---|---|
| `app/config.py` | `Settings`: reads the environment variables listed in `.env.sample` |
| `app/worldcat.py` | `WorldCatClient`: an async `httpx` client that handles OAuth token caching, parameter encoding and error mapping |
| `app/server.py` | `MCPServer` instance, server instructions for agents, and the 10 tool definitions |
| `app/main.py` | FastAPI app: health routes, plus the MCP app mounted at `/mcp`; its lifespan runs the MCP session manager |
| `tests/` | offline unit tests |
| `scripts/` | config generation, build/push, deploy, live smoke test |

## Statelessness and concurrency

The MCP app is created with `stateless_http=True` and `json_response=True`.

- **2026-07-28 clients** send the `MCP-Protocol-Version: 2026-07-28` header with
  each request. The SDK routes these requests to its single-exchange handler: one
  JSON-RPC request in, one response out, with no session.
- **Older clients** perform the `initialize` handshake. The SDK gives each of
  their HTTP requests a fresh, throwaway transport, and never issues an
  `Mcp-Session-Id`.

All request handling is async. Concurrent tool calls from any number of
clients share one `httpx.AsyncClient` connection pool and one cached OAuth
token. Nothing else is shared between requests.

## WorldCat authentication

`WorldCatClient` obtains a token with the OAuth2 client-credentials grant
(`POST https://oauth.oclc.org/token`, HTTP Basic auth with the WSKey,
`scope=wcapi`):

- The token is cached in memory and refreshed 60 s before it expires (OCLC
  tokens last about 20 minutes).
- An `asyncio.Lock` with a double-check makes concurrent requests trigger a
  single refresh.
- If WorldCat answers `401` (for example because the token was revoked), the
  request is retried once with a newly fetched token.

## Parameter encoding

WorldCat array parameters use `explode: false`, so the client joins list values
with commas (`itemType=book,video`). The exception is `creator`, which is
pipe-delimited. Booleans become `true` or `false`. The client drops `None`
values and empty lists, so WorldCat's defaults apply.

## Errors

WorldCat returns errors as problem-JSON bodies. The client raises
`WorldCatError` with the HTTP status and the problem's `detail` (or `title`).
Tools turn it into an MCP `ToolError`, which the client receives as a result
with `isError: true`, so the agent can see the problem and adjust its call.
Missing-identifier mistakes are caught before any request is sent.

## Health checks

| Check | Endpoint | Semantics |
|---|---|---|
| Liveness (k8s `livenessProbe`, Docker `HEALTHCHECK`) | `/healthz` | The process is serving HTTP |
| Readiness (k8s `readinessProbe`) | `/readyz` | Credentials are configured |

Neither check calls OCLC. An upstream outage shows up as tool errors; it
doesn't cause restart loops.

## Security notes

- MCP clients don't authenticate, as required. The server can only read from
  WorldCat, and every tool is read-only.
- The SDK's DNS-rebinding Host check is disabled. That check protects servers
  bound to localhost and would reject requests for the public hostname.
- The container runs as a non-root user with a read-only root filesystem, all
  Linux capabilities dropped, and the `RuntimeDefault` seccomp profile.
- `search_my_holdings` and `get_my_holding` expose the local holdings records
  of the institution that owns the WSKey to anyone who can reach the server.
  To remove them, delete those two tools from `app/server.py`.
