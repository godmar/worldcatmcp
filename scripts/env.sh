# Sourced by the other scripts: load .env (the single source of truth).
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT/.env}"
[[ -f "$ENV_FILE" ]] || { echo "error: $ENV_FILE not found (copy .env.sample)" >&2; exit 1; }
set -a; # shellcheck disable=SC1090
. "$ENV_FILE"; set +a
export KUBECONFIG="${KUBECONFIG_FILE:-$ROOT/endeavour.yaml}"
NAMESPACE=vtlib
