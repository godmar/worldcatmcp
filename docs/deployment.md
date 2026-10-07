# Deployment (Kubernetes, endeavour cluster)

## Configuration: `.env` is the single source of truth

Every site-specific or sensitive value lives in `.env`, which is git-ignored.
`.env.sample` documents each variable.

| Variable | Used for | Ends up in |
|---|---|---|
| `WC_API_CLIENT_KEY`, `WC_API_SECRET` | OCLC WSKey (client-credentials grant) | Secret `worldcat-mcp-secret` |
| `API_BASE_URL` | WorldCat Search API base URL | ConfigMap `worldcat-mcp-config` |
| `WC_TOKEN_URL`, `WC_API_SCOPE`, `LOG_LEVEL`, ... (optional) | runtime tuning | ConfigMap `worldcat-mcp-config` |
| `MCP_URL` | public hostname | Ingress `host` (through kustomize `replacements`) and the ConfigMap |
| `MCP_IMAGE` | image reference | Deployment container `image` (through kustomize `replacements`) |
| `REGISTRY_SERVER`, `REGISTRY_USERNAME`, `REGISTRY_PASSWORD` | read-only deploy token | `kubernetes.io/dockerconfigjson` Secret `worldcat-mcp-regcred` (imagePullSecret) |

`scripts/gen-k8s-config.sh` parses `.env` without evaluating it as shell code
and writes the generator inputs to `k8s/generated/`:

| File | Contents |
|---|---|
| `config.env` | non-secret runtime settings, for the `configMapGenerator` |
| `secret.env` | WSKey credentials, for the `secretGenerator` |
| `deploy.env` | `MCP_URL` and `MCP_IMAGE`, for a local-only ConfigMap used by `replacements` and never applied to the cluster |
| `dockerconfig.json` | registry pull credentials, for a `secretGenerator` |

`k8s/generated/` is git-ignored and written with mode 0600. Any `.env`
variable that isn't a secret, registry or deploy key goes into the ConfigMap
automatically, so you can add a new runtime setting without touching the
script.

## Manifests (`k8s/`)

```
k8s/
├── kustomization.yaml   namespace vtlib, generators, replacements, common labels
├── deployment.yaml      2 replicas, probes, non-root, read-only root fs
├── service.yaml         ClusterIP :80 -> :8000
├── ingress.yaml         ingressClassName nginx, host from MCP_URL
└── generated/           (git-ignored) produced from .env
```

- **Namespace:** `vtlib`, which already exists. The kustomization doesn't
  create it.
- **TLS:** the cluster terminates TLS for every `*.endeavour.cs.vt.edu` host, so
  the Ingress has no TLS section.
- **Probes:** the liveness probe polls `GET /healthz` and the readiness probe
  polls `GET /readyz`. Neither probe calls WorldCat, so an OCLC outage doesn't
  restart pods or take them out of the Service.
- **Config changes:** the generators append a content hash to the
  ConfigMap/Secret names. Changing `.env` and re-applying therefore rolls the
  Deployment automatically.
- **Scaling:** the server is stateless, so you can change `replicas` freely.
  Sticky sessions aren't needed.

To preview the rendered manifests:

```bash
scripts/gen-k8s-config.sh && KUBECONFIG=endeavour.yaml kubectl kustomize k8s/
```

## Deploying

Prerequisites:

- `kubectl` (it includes kustomize)
- the kubeconfig `endeavour.yaml` in the project root, or set `KUBECONFIG_FILE`
- a `docker login container.cs.vt.edu` with push rights

To build, push and deploy in one step, run:

```bash
scripts/deploy.sh --build
```

The script runs these steps:

1. `scripts/build-push.sh`: builds `$MCP_IMAGE` and pushes it.
2. `scripts/gen-k8s-config.sh`: regenerates `k8s/generated/` from `.env`.
3. `kubectl apply -k k8s/`.
4. `kubectl rollout restart deployment/worldcat-mcp`: forces a re-pull, because
   the tag (for example `:latest`) may not have changed. It then waits for the
   rollout to finish.

To deploy without rebuilding the image, run `scripts/deploy.sh` without
`--build`.

### Verify

```bash
export KUBECONFIG=$PWD/endeavour.yaml
kubectl -n vtlib get pods -l app=worldcat-mcp
kubectl -n vtlib logs -l app=worldcat-mcp --tail=50
curl -s https://vtlibai-wc.endeavour.cs.vt.edu/healthz
.venv/bin/python scripts/smoke_test.py https://vtlibai-wc.endeavour.cs.vt.edu/mcp
```

### Remove

```bash
KUBECONFIG=endeavour.yaml kubectl delete -k k8s/
```
