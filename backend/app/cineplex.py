from __future__ import annotations

import asyncio
import logging
from datetime import date
from typing import Any

import httpx

from .config import Settings

logger = logging.getLogger(__name__)


class CineplexError(RuntimeError):
    pass


class CineplexDisabled(CineplexError):
    pass


class CineplexClient:
    """Small, defensive client for the live public web contracts captured in docs."""

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None):
        self.settings = settings
        self._owns_client = client is None
        self.client = client or httpx.AsyncClient(timeout=20.0, follow_redirects=False)

    async def close(self) -> None:
        if self._owns_client:
            await self.client.aclose()

    @property
    def headers(self) -> dict[str, str]:
        if not self.settings.cineplex_subscription_key:
            raise CineplexDisabled("CINEPLEX_SUBSCRIPTION_KEY is not configured")
        return {
            "Accept": "application/json",
            "Accept-Language": "en-CA,en;q=0.9",
            "Ocp-Apim-Subscription-Key": self.settings.cineplex_subscription_key,
            "Referer": self.settings.cineplex_referer,
            "User-Agent": self.settings.cineplex_user_agent,
        }

    async def _get(self, url: str, params: dict[str, Any] | None = None) -> Any:
        delay = 1.0
        for attempt in range(4):
            response = await self.client.get(url, params=params, headers=self.headers)
            if response.status_code not in {403, 429}:
                try:
                    response.raise_for_status()
                    return response.json()
                except (httpx.HTTPError, ValueError) as exc:
                    raise CineplexError(f"Cineplex request failed safely: {response.status_code}") from exc
            if attempt == 3:
                raise CineplexError(
                    f"Cineplex returned {response.status_code}; backing off without retry storm"
                )
            retry_after = response.headers.get("Retry-After")
            wait = float(retry_after) if retry_after and retry_after.isdigit() else delay
            await asyncio.sleep(min(wait, 30.0))
            delay *= 2
        raise AssertionError("unreachable")

    async def movie_catalog(self, take: int = 999) -> list[dict[str, Any]]:
        data = await self._get(
            f"{self.settings.cineplex_base_url}/v1/movies",
            {
                "language": "en",
                "skip": 0,
                "take": max(1, min(take, 999)),
                "filterEvents": "false",
                "removeIrrelevantFilms": "false",
                "onePosterExcluded": "false",
            },
        )
        items = data.get("items", []) if isinstance(data, dict) else []
        if not isinstance(items, list):
            logger.warning("Cineplex catalog omitted items list; skipping payload")
            return []
        return [movie for movie in items if isinstance(movie, dict) and movie.get("id")]

    async def bookable_dates(self, film_id: int) -> list[str]:
        data = await self._get(
            f"{self.settings.cineplex_base_url}/v1/dates/bookable",
            {"language": "en", "filmId": film_id},
        )
        if not isinstance(data, list):
            logger.warning("Bookable-dates payload changed type; skipping film %s", film_id)
            return []
        return [value for value in data if isinstance(value, str)]

    async def showtimes(self, film_id: int, on_date: date | str) -> list[dict[str, Any]]:
        value = on_date.isoformat() if isinstance(on_date, date) else str(on_date)[:10]
        data = await self._get(
            f"{self.settings.cineplex_base_url}/v1/showtimes",
            {"language": "en", "filmId": film_id, "date": value},
        )
        if not isinstance(data, list):
            logger.warning("Showtimes payload changed type; skipping film %s date %s", film_id, value)
            return []
        return [item for item in data if isinstance(item, dict)]

    async def seat_layout(self, theatre_id: int, showtime_id: int) -> dict[str, Any]:
        data = await self._get(
            f"{self.settings.cineplex_ticketing_base_url}/v1/theatre/{theatre_id}/showtime/{showtime_id}/seat-layout"
        )
        return data if isinstance(data, dict) else {}

    async def seat_availability(
        self, theatre_id: int, showtime_id: int, preview: bool = True
    ) -> dict[str, Any]:
        data = await self._get(
            f"{self.settings.cineplex_ticketing_base_url}/v1/theatre/{theatre_id}/showtime/{showtime_id}/seat-availability",
            {"preview": str(preview).lower()},
        )
        return data if isinstance(data, dict) else {}


def flatten_showtimes(payload: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Tolerantly flatten Cineplex's theatre/date/movie/experience/session nesting."""
    flattened: list[dict[str, Any]] = []
    for theatre in payload:
        theatre_name = theatre.get("theatre")
        theatre_id = theatre.get("theatreId")
        if not theatre_name or not theatre_id:
            logger.warning("Skipping showtime theatre missing name/id")
            continue
        dates = theatre.get("dates") if isinstance(theatre.get("dates"), list) else []
        for date_group in dates:
            if not isinstance(date_group, dict):
                continue
            start_date = date_group.get("startDate")
            movies = date_group.get("movies") if isinstance(date_group.get("movies"), list) else []
            for movie in movies:
                if not isinstance(movie, dict):
                    continue
                experiences = (
                    movie.get("experiences") if isinstance(movie.get("experiences"), list) else []
                )
                for experience in experiences:
                    if not isinstance(experience, dict):
                        continue
                    labels = experience.get("experienceTypes")
                    labels = labels if isinstance(labels, list) else []
                    sessions = experience.get("sessions") if isinstance(experience.get("sessions"), list) else []
                    for session in sessions:
                        if not isinstance(session, dict) or not session.get("vistaSessionId"):
                            continue
                        flattened.append(
                            {
                                **session,
                                "movieId": movie.get("id"),
                                "movieName": movie.get("name"),
                                "filmUrl": movie.get("filmUrl"),
                                "theatreId": theatre_id,
                                "theatre": theatre_name,
                                "date": start_date,
                                "experienceTypes": [str(label) for label in labels],
                                "passesAllowed": movie.get("passesAllowed"),
                            }
                        )
    return flattened

