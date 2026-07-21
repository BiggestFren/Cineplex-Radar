from __future__ import annotations

import logging
import json
from typing import Any, Callable
from urllib.parse import quote

import httpx

from .config import Settings

logger = logging.getLogger(__name__)


class Notifier:
    def __init__(
        self,
        settings: Settings,
        client: httpx.AsyncClient | None = None,
        endpoint_provider: Callable[[], list[str]] | None = None,
    ):
        self.settings = settings
        self._owns_client = client is None
        self.client = client or httpx.AsyncClient(timeout=15.0)
        self.endpoint_provider = endpoint_provider or (lambda: [])

    async def close(self) -> None:
        if self._owns_client:
            await self.client.aclose()

    async def send(
        self,
        title: str,
        message: str,
        *,
        priority: str = "high",
        action: str | None = None,
        tags: list[str] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> bool:
        sent = False
        direct_payload = json.dumps(
            {"title": title, "message": message, "action": action or "radar://events",
             "priority": priority, "payload": payload or {}}
        ).encode()
        for endpoint in self.endpoint_provider():
            try:
                response = await self.client.post(
                    endpoint, content=direct_payload, headers={"Content-Type": "application/json"}
                )
                response.raise_for_status()
                sent = True
            except httpx.HTTPError:
                logger.warning("A registered UnifiedPush endpoint rejected delivery")
        if self.settings.ntfy_topic:
            headers = {"Title": title, "Priority": priority}
            if action:
                headers["Click"] = action
            if tags:
                headers["Tags"] = ",".join(tags)
            if self.settings.ntfy_token:
                headers["Authorization"] = f"Bearer {self.settings.ntfy_token}"
            response = await self.client.post(
                f"{self.settings.ntfy_base_url}/{quote(self.settings.ntfy_topic, safe='')}",
                content=message.encode(),
                headers=headers,
            )
            response.raise_for_status()
            sent = True
        if self.settings.discord_webhook_url:
            response = await self.client.post(
                self.settings.discord_webhook_url,
                json={"content": f"**{title}**\n{message}"},
            )
            response.raise_for_status()
            sent = True
        if not sent:
            logger.info("Notification transport disabled: %s — %s", title, message)
        return sent
