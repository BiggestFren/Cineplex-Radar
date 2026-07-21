from __future__ import annotations

from dataclasses import replace

import pytest

from app.config import Settings


@pytest.fixture
def settings(tmp_path):
    return replace(
        Settings.from_env(),
        app_auth_token="test-token",
        database_path=tmp_path / "radar.db",
        enable_watcher=False,
        cineplex_subscription_key="fixture-key",
        ntfy_topic="",
        discord_webhook_url="",
        tmdb_api_key="",
        llm_api_key="",
        llm_model="",
    )

