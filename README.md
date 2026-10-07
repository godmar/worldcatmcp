# WorldCat MCP Server

A stateless MCP server (MCP 2026-07-28) that gives AI agents read-only access to the
OCLC WorldCat Search API v2. It's built with FastAPI and the MCP Python SDK.

```bash
cp .env.sample .env                 # fill in credentials
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest                    # offline unit tests
set -a; . ./.env; set +a; .venv/bin/uvicorn app.main:app --port 8000
scripts/deploy.sh --build           # build, push, deploy to k8s (namespace vtlib)
```

See [docs/](docs/README.md) for the tools, local development and container use, deployment, and architecture.
