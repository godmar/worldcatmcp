#!/usr/bin/env bash
# Build the container image and push it to $MCP_IMAGE (from .env).
# Requires a `docker login` to the registry with write access.
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/env.sh"

docker build -t "$MCP_IMAGE" "$ROOT"
docker push "$MCP_IMAGE"
