from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True, slots=True)
class Settings:
    app_auth_token: str
    database_path: Path
    enable_watcher: bool
    poll_interval_seconds: int
    poll_jitter_seconds: int
    burst_mode: bool
    burst_interval_seconds: int
    burst_until: str | None
    cineplex_base_url: str
    cineplex_ticketing_base_url: str
    cineplex_subscription_key: str
    cineplex_user_agent: str
    cineplex_referer: str
    enable_cineplex_account: bool
    enable_checkout: bool
    allow_unattended_buy: bool
    ntfy_base_url: str
    ntfy_topic: str
    ntfy_token: str
    discord_webhook_url: str
    tmdb_api_key: str
    tmdb_region: str
    llm_base_url: str
    llm_api_key: str
    llm_model: str
    home_latitude: float
    home_longitude: float

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            app_auth_token=os.getenv("APP_AUTH_TOKEN", "local-development-token"),
            database_path=Path(os.getenv("DATABASE_PATH", "./state/radar.db")),
            enable_watcher=_bool("ENABLE_WATCHER", True),
            poll_interval_seconds=max(300, _int("POLL_INTERVAL_SECONDS", 300)),
            poll_jitter_seconds=max(0, _int("POLL_JITTER_SECONDS", 45)),
            burst_mode=_bool("BURST_MODE", False),
            burst_interval_seconds=max(30, _int("BURST_INTERVAL_SECONDS", 45)),
            burst_until=os.getenv("BURST_UNTIL") or None,
            cineplex_base_url=os.getenv(
                "CINEPLEX_BASE_URL",
                "https://apis.cineplex.com/prod/cpx/theatrical/api",
            ).rstrip("/"),
            cineplex_ticketing_base_url=os.getenv(
                "CINEPLEX_TICKETING_BASE_URL",
                "https://apis.cineplex.com/prod/ticketing/api",
            ).rstrip("/"),
            cineplex_subscription_key=os.getenv("CINEPLEX_SUBSCRIPTION_KEY", ""),
            cineplex_user_agent=os.getenv(
                "CINEPLEX_USER_AGENT",
                "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 "
                "Chrome/126.0 Mobile Safari/537.36 Radar/0.1",
            ),
            cineplex_referer=os.getenv("CINEPLEX_REFERER", "https://www.cineplex.com/"),
            enable_cineplex_account=_bool("ENABLE_CINEPLEX_ACCOUNT", False),
            enable_checkout=_bool("ENABLE_CHECKOUT", False),
            allow_unattended_buy=_bool("ALLOW_UNATTENDED_BUY", False),
            ntfy_base_url=os.getenv("NTFY_BASE_URL", "http://ntfy:80").rstrip("/"),
            ntfy_topic=os.getenv("NTFY_TOPIC", ""),
            ntfy_token=os.getenv("NTFY_TOKEN", ""),
            discord_webhook_url=os.getenv("DISCORD_WEBHOOK_URL", ""),
            tmdb_api_key=os.getenv("TMDB_API_KEY", ""),
            tmdb_region=os.getenv("TMDB_REGION", "CA"),
            llm_base_url=os.getenv("LLM_BASE_URL", "https://nano-gpt.com/api/v1").rstrip("/"),
            llm_api_key=os.getenv("LLM_API_KEY", ""),
            llm_model=os.getenv("LLM_MODEL", ""),
            home_latitude=_float("HOME_LATITUDE", 43.6532),
            home_longitude=_float("HOME_LONGITUDE", -79.3832),
        )

    def validate_safety(self) -> None:
        if self.allow_unattended_buy and not (
            self.enable_cineplex_account and self.enable_checkout
        ):
            raise RuntimeError(
                "ALLOW_UNATTENDED_BUY requires both ENABLE_CINEPLEX_ACCOUNT and "
                "ENABLE_CHECKOUT; no code path enables these flags implicitly."
            )
