# Development: building, testing and running locally

## Prerequisites

- Python 3.12
- Docker (or another OCI builder) for container work
- A `.env` file. Copy `.env.sample` and fill in the OCLC WSKey (`WC_API_CLIENT_KEY`,
  `WC_API_SECRET`). The deployment variables aren't needed to run locally.

## Python virtualenv

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
```

`requirements.txt` holds the pinned runtime dependencies that go into the
image. `requirements-dev.txt` adds the test tools.

## Running the server directly

```bash
set -a; . ./.env; set +a
.venv/bin/uvicorn app.main:app --reload --port 8000
```

| URL | Purpose |
|---|---|
| `http://localhost:8000/mcp` | MCP endpoint (Streamable HTTP, stateless) |
| `http://localhost:8000/healthz` | Liveness: always `200 {"status":"ok"}` while the process serves requests |
| `http://localhost:8000/readyz` | Readiness: `200` if WorldCat credentials are configured, `503` otherwise |
| `http://localhost:8000/` | Small JSON info document |

## Tests

### Unit tests (offline)

```bash
.venv/bin/pytest
```

The unit tests mock WorldCat with [respx](https://lundberg.github.io/respx/)
and call the MCP server in-process, so they need neither network access nor
credentials. They cover:

- parameter encoding
- OAuth token caching and refresh after a 401
- error mapping
- the tool list and its annotations
- mapping from tool arguments to WorldCat parameters
- the health endpoints

### End-to-end smoke test (live WorldCat)

With a server running (locally, in a container, or deployed), run:

```bash
.venv/bin/python scripts/smoke_test.py http://localhost:8000/mcp
.venv/bin/python scripts/smoke_test.py https://vtlibai-wc.endeavour.cs.vt.edu/mcp
```

The smoke test starts four concurrent clients:

- two speak the stateless **2026-07-28** protocol
- one uses the **legacy** `initialize` handshake
- one uses **auto** negotiation

Each client lists the tools, runs a search, and fetches a holdings summary. The
test prints one line per client and then `OK`.

Interactive testing also works with the MCP Inspector:
`npx @modelcontextprotocol/inspector`. Choose transport "Streamable HTTP" and
URL `http://localhost:8000/mcp`.

## Container

### Build

```bash
docker build -t worldcat-mcp:dev .
```

The image is based on `python:3.12-slim`. It runs as the unprivileged UID
10001, listens on port 8000, and has a Docker `HEALTHCHECK` that polls
`/healthz`.

### Run

```bash
docker run --rm --name worldcat-mcp --read-only --env-file .env -p 8000:8000 worldcat-mcp:dev
```

`--read-only` matches the `readOnlyRootFilesystem` setting used in
Kubernetes. Docker's `--env-file` passes values literally, so don't quote them
in `.env`.

### Test the running container

```bash
curl -s localhost:8000/healthz                              # {"status":"ok"}
docker inspect --format '{{.State.Health.Status}}' worldcat-mcp   # healthy (after ~30s)
.venv/bin/python scripts/smoke_test.py http://localhost:8000/mcp
```

### Push

```bash
scripts/build-push.sh     # docker build + push to $MCP_IMAGE from .env
```

This needs a `docker login` to the registry with **write** access. The deploy
token in `.env` is read-only and is used only by Kubernetes to pull the image.
