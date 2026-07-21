from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import httpx

from .config import Settings
from .database import Database
from .llm import SupportsCompletion, rank_suggestions
from .notifications import Notifier


class TMDBClient:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None):
        self.settings = settings
        self._owns_client = client is None
        self.client = client or httpx.AsyncClient(timeout=20.0)

    async def close(self) -> None:
        if self._owns_client:
            await self.client.aclose()

    async def upcoming(self) -> list[dict[str, Any]]:
        if not self.settings.tmdb_api_key:
            return []
        today = date.today()
        response = await self.client.get(
            "https://api.themoviedb.org/3/discover/movie",
            params={
                "api_key": self.settings.tmdb_api_key,
                "region": self.settings.tmdb_region,
                "with_release_type": "2|3",
                "release_date.gte": today.isoformat(),
                "release_date.lte": (today + timedelta(days=120)).isoformat(),
                "sort_by": "popularity.desc",
                "include_adult": "false",
            },
        )
        response.raise_for_status()
        results = response.json().get("results", [])
        return [item for item in results if isinstance(item, dict)]


class DiscoveryService:
    def __init__(
        self,
        settings: Settings,
        database: Database,
        notifier: Notifier,
        llm: SupportsCompletion,
        tmdb: TMDBClient | None = None,
    ):
        self.settings = settings
        self.database = database
        self.notifier = notifier
        self.llm = llm
        self.tmdb = tmdb or TMDBClient(settings)

    async def run_once(self) -> list[int]:
        upcoming = await self.tmdb.upcoming()
        if not upcoming:
            return []
        history = [item.model_dump(mode="json") for item in self.database.list_suggestions()]
        selected = await rank_suggestions(self.llm, upcoming[:30], history[-100:])
        by_id = {int(item["id"]): item for item in upcoming if item.get("id")}
        created: list[int] = []
        for choice in selected:
            tmdb_id = int(choice.get("tmdb_id", 0))
            source = by_id.get(tmdb_id)
            if not source:
                continue
            if not self.database.observe_once(f"suggestion:{tmdb_id}"):
                continue
            suggestion = self.database.add_suggestion(
                tmdb_id,
                str(source.get("title") or choice.get("title") or "Upcoming movie"),
                source.get("release_date"),
                str(choice.get("pitch") or "Pre-orders may open soon. Add it to Radar?"),
                payload=source,
            )
            self.database.add_event(
                "suggestion", suggestion.title, suggestion.pitch,
                {"suggestion_id": suggestion.id},
            )
            await self.notifier.send(
                f"Radar suggestion: {suggestion.title}", suggestion.pitch,
                action=f"radar://suggestions/{suggestion.id}", tags=["movie_camera"],
            )
            created.append(suggestion.id)
        return created
