# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /srv

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app/ app/
RUN python -m compileall -q app

# Unprivileged user (matches runAsUser in k8s/deployment.yaml)
RUN groupadd --system --gid 10001 mcp && useradd --system --uid 10001 --gid mcp --no-create-home mcp
USER 10001:10001

EXPOSE 8000

# Liveness check for plain `docker run`; Kubernetes uses its own probes
# (/healthz for liveness, /readyz for readiness).
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2).status == 200 else 1)"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips", "*", "--no-server-header"]
