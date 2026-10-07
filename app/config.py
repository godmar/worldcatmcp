"""Runtime configuration, read from environment variables (see .env.sample)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


@dataclass(frozen=True)
class Settings:
    client_key: str = field(default_factory=lambda: _env("WC_API_CLIENT_KEY"))
    client_secret: str = field(default_factory=lambda: _env("WC_API_SECRET"))
    api_base_url: str = field(
        default_factory=lambda: _env(
            "API_BASE_URL", "https://americas.discovery.api.oclc.org"
        ).rstrip("/")
    )
    token_url: str = field(
        default_factory=lambda: _env("WC_TOKEN_URL", "https://oauth.oclc.org/token")
    )
    scope: str = field(default_factory=lambda: _env("WC_API_SCOPE", "wcapi"))
    http_timeout: float = field(default_factory=lambda: float(_env("WC_HTTP_TIMEOUT", "30")))
    log_level: str = field(default_factory=lambda: _env("LOG_LEVEL", "INFO").upper())


settings = Settings()
