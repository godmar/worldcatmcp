# WorldCat MCP Server

An [MCP](https://modelcontextprotocol.io) server that gives AI agents **read-only**
access to OCLC's [WorldCat Search API v2](https://developer.api.oclc.org/wcv2).
It's built with Python, FastAPI and the official MCP Python SDK (`mcp` 2.x).

- **Endpoint:** `https://<MCP_URL>/mcp` (Streamable HTTP)
- **Authentication:** none for MCP clients. The server itself authenticates to
  WorldCat with the OCLC WSKey from `.env`.
- **Stateless:** the server speaks the stateless MCP protocol revision
  **2026-07-28**: every request is self-contained, with no `initialize`
  handshake and no `Mcp-Session-Id`. Older clients that perform the
  `initialize` handshake (2025-xx protocol revisions) get the SDK's legacy
  *stateless* Streamable HTTP mode. Either way the server keeps no
  per-client state. Any number of clients can use it at once, and any replica
  can serve any request, so it scales horizontally without sticky sessions.

More documentation:

| Document | Contents |
|---|---|
| [development.md](development.md) | Local setup, tests, and building, testing and running the container locally |
| [deployment.md](deployment.md) | Configuration via `.env`, the Kubernetes/kustomize setup, and deploying to endeavour |
| [architecture.md](architecture.md) | How the code is organized, plus token handling, health checks and design decisions |

## Tools

All tools are annotated `readOnlyHint: true`. They return WorldCat's JSON
unchanged. Parameters are snake_case and are mapped to WorldCat's camelCase
query parameters. Most tools also take `extra_params`, a dict of raw WorldCat
parameters for options the tool doesn't expose. Errors from WorldCat come back
as MCP tool errors (`isError: true`) that include the HTTP status and
WorldCat's message.

| Tool | WorldCat endpoint | Purpose |
|---|---|---|
| `search_bibs` | `GET /brief-bibs` or `/bibs` (`detail="full"`) | Search bibliographic records with WorldCat query syntax plus filters (format, language, date, holding library, audience, ...), facets, sorting and paging |
| `get_bib` | `GET /bibs/{ocn}` or `/brief-bibs/{ocn}` | Get one record by OCLC number (full by default) |
| `get_other_editions` | `GET /brief-bibs/{ocn}/other-editions` | List other editions and formats of a work |
| `get_holdings` | `GET /bibs-holdings` | See which libraries hold an item (by OCLC number, ISBN or ISSN), filtered by country, state, symbol or proximity |
| `get_holdings_summary` | `GET /bibs-summary-holdings` | Get holding counts for an item |
| `get_detailed_holdings` | `GET /bibs-detailed-holdings` | Get the local holdings detail (call numbers, locations) of specific institutions |
| `get_retained_holdings` | `GET /bibs-retained-holdings` | Find libraries with Shared Print retention commitments for an item |
| `search_my_holdings` | `GET /my-holdings` | Search the local holdings records of the institution that owns the API key |
| `get_my_holding` | `GET /my-holdings/{controlNumber}` | Get one local holdings record |
| `search_retained_holdings` | `GET /retained-holdings` | Search shared-print local holdings records |

### Query syntax cheat sheet (`search_bibs.q`)

| Example | Meaning |
|---|---|
| `kw:climate change` | keyword |
| `ti:"the hobbit" AND au:tolkien` | title and author |
| `bn:9780439136358` | ISBN |
| `in:0099-1333` | ISSN |
| `no:41266045` | OCLC number |
| `su:machine learning` | subject |
| `(au:gazihan OR au:womacka) AND kw:java` | boolean combination |

See OCLC's
[index list](https://help.oclc.org/Librarian_Toolbox/Searching_WorldCat_Indexes/Bibliographic_records/Bibliographic_record_indexes/Bibliographic_record_index_lists)
for all indexes.

## Connecting a client

Claude Code:

```bash
claude mcp add --transport http worldcat https://vtlibai-wc.endeavour.cs.vt.edu/mcp
```

Generic MCP client configuration:

```json
{ "mcpServers": { "worldcat": { "type": "http", "url": "https://vtlibai-wc.endeavour.cs.vt.edu/mcp" } } }
```

Python (`mcp` SDK):

```python
from mcp import Client

async with Client("https://vtlibai-wc.endeavour.cs.vt.edu/mcp") as c:
    res = await c.call_tool("search_bibs", {"q": "ti:moby dick", "limit": 3})
```
