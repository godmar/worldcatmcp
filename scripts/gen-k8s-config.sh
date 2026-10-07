#!/usr/bin/env bash
# Derive the kustomize generator inputs under k8s/generated/ from .env.
# .env is the single source of truth; the generated files are git-ignored.
#
# usage: scripts/gen-k8s-config.sh [path/to/.env]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${1:-$ROOT/.env}"
OUT="$ROOT/k8s/generated"

[[ -f "$ENV_FILE" ]] || { echo "error: $ENV_FILE not found (copy .env.sample)" >&2; exit 1; }

# Parse KEY=VALUE lines (no shell evaluation of the file).
declare -A ENV
while IFS= read -r line || [[ -n "$line" ]]; do
  line="${line%$'\r'}"
  [[ "$line" =~ ^[[:space:]]*(#|$) ]] && continue
  [[ "$line" =~ ^[[:space:]]*(export[[:space:]]+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)$ ]] || {
    echo "warning: ignoring malformed line: $line" >&2; continue; }
  key="${BASH_REMATCH[2]}"; val="${BASH_REMATCH[3]}"
  # Strip one level of matching surrounding quotes.
  if [[ "$val" =~ ^\"(.*)\"$ || "$val" =~ ^\'(.*)\'$ ]]; then val="${BASH_REMATCH[1]}"; fi
  ENV[$key]="$val"
done < "$ENV_FILE"

require() {
  for k in "$@"; do
    [[ -n "${ENV[$k]:-}" ]] || { echo "error: $k is not set in $ENV_FILE" >&2; exit 1; }
  done
}
require WC_API_CLIENT_KEY WC_API_SECRET API_BASE_URL MCP_URL \
        REGISTRY_SERVER REGISTRY_USERNAME REGISTRY_PASSWORD MCP_IMAGE

# Keys that go into the Secret / deploy-only ConfigMap; everything else is
# treated as non-sensitive runtime configuration.
SECRET_KEYS=" WC_API_CLIENT_KEY WC_API_SECRET "
DEPLOY_KEYS=" MCP_URL MCP_IMAGE "
REGISTRY_KEYS=" REGISTRY_SERVER REGISTRY_USERNAME REGISTRY_PASSWORD "

mkdir -p "$OUT"
umask 077
: > "$OUT/config.env"; : > "$OUT/secret.env"; : > "$OUT/deploy.env"

for key in $(printf '%s\n' "${!ENV[@]}" | sort); do
  if   [[ "$SECRET_KEYS"   == *" $key "* ]]; then echo "$key=${ENV[$key]}" >> "$OUT/secret.env"
  elif [[ "$DEPLOY_KEYS"   == *" $key "* ]]; then echo "$key=${ENV[$key]}" >> "$OUT/deploy.env"
  elif [[ "$REGISTRY_KEYS" == *" $key "* ]]; then :
  else echo "$key=${ENV[$key]}" >> "$OUT/config.env"
  fi
done
# The server also wants to know its public hostname.
echo "MCP_URL=${ENV[MCP_URL]}" >> "$OUT/config.env"

auth=$(printf '%s:%s' "${ENV[REGISTRY_USERNAME]}" "${ENV[REGISTRY_PASSWORD]}" | base64 | tr -d '\n')
cat > "$OUT/dockerconfig.json" <<EOF
{"auths":{"${ENV[REGISTRY_SERVER]}":{"username":"${ENV[REGISTRY_USERNAME]}","password":"${ENV[REGISTRY_PASSWORD]}","auth":"$auth"}}}
EOF

echo "wrote $OUT/{config.env,secret.env,deploy.env,dockerconfig.json}"
