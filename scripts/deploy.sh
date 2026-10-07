#!/usr/bin/env bash
# Deploy to the cluster: regenerate config from .env, apply the kustomization,
# restart so the (re-pushed) image is pulled, and wait for the rollout.
#
# usage: scripts/deploy.sh [--build]   (--build also builds and pushes the image first)
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/env.sh"

if [[ "${1:-}" == "--build" ]]; then
  "$ROOT/scripts/build-push.sh"
fi

"$ROOT/scripts/gen-k8s-config.sh" "$ENV_FILE"
kubectl apply -k "$ROOT/k8s"
# The image tag (e.g. :latest) may not have changed; force new pods so that
# imagePullPolicy: Always fetches the current image.
kubectl -n "$NAMESPACE" rollout restart deployment/worldcat-mcp
kubectl -n "$NAMESPACE" rollout status deployment/worldcat-mcp --timeout=180s

echo
echo "MCP endpoint: https://$MCP_URL/mcp"
