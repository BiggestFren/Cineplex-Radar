from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timezone
from typing import Any

from .cineplex import CineplexClient, CineplexDisabled, CineplexError, flatten_showtimes
from .config import Settings
from .database import Database
from .engine import normalize_seat_map, rank_seats, rank_showtimes
from .executor import BookingExecutor
from .llm import SupportsCompletion, tie_break_commentary
from .models import RadarItem
from .notifications import Notifier

logger = logging.getLogger(__name__)


def _matches_movie(item: RadarItem, movie: dict[str, Any]) -> bool:
    if item.movie_id is not None:
        return int(movie.get("id", -1)) == item.movie_id
    query = item.movie_query.casefold().strip()
    return query in str(movie.get("name", "")).casefold() or query == str(movie.get("filmUrl", "")).casefold()


def _matches_theatre(item: RadarItem, showtime: dict[str, Any]) -> bool:
    if not item.preferred_theatre_ids and not item.preferred_theatre_names:
        return True
    if int(showtime.get("theatreId", -1)) in item.preferred_theatre_ids:
        return True
    name = str(showtime.get("theatre", "")).casefold()
    return any(fragment.casefold() in name for fragment in item.preferred_theatre_names)


def _has_imax(showtime: dict[str, Any]) -> bool:
    return "imax" in " ".join(showtime.get("experienceTypes", [])).casefold()


class Watcher:
    def __init__(
        self,
        settings: Settings,
        database: Database,
        cineplex: CineplexClient,
        notifier: Notifier,
        executor: BookingExecutor | None = None,
        llm: SupportsCompletion | None = None,
    ):
        self.settings = settings
        self.database = database
        self.cineplex = cineplex
        self.notifier = notifier
        self.executor = executor or BookingExecutor(settings)
        self.llm = llm

    async def _alert(
        self, event_type: str, title: str, message: str, payload: dict[str, Any]
    ) -> None:
        event = self.database.add_event(event_type, title, message, payload)
        await self.notifier.send(
            title, message, priority="urgent" if event_type in {"drop", "booking"} else "high",
            action=f"radar://events/{event.id}", tags=["ticket"], payload=payload,
        )

    async def poll_once(self) -> int:
        radar_items = self.database.list_radar()
        if not radar_items:
            return 0
        catalog = await self.cineplex.movie_catalog()
        detections = 0
        for radar in radar_items:
            movies = [movie for movie in catalog if _matches_movie(radar, movie)]
            for movie in movies:
                film_id = int(movie["id"])
                catalog_key = f"catalog:{radar.id}:{film_id}"
                if self.database.observe_once(catalog_key):
                    detections += 1
                    await self._alert(
                        "catalog", f"{movie.get('name')} appeared",
                        "The movie is now present in Cineplex's catalog.",
                        {"radar_id": radar.id, "movie": movie},
                    )
                dates = await self.cineplex.bookable_dates(film_id)
                all_showtimes: list[dict[str, Any]] = []
                for date_value in dates[:3]:
                    payload = await self.cineplex.showtimes(film_id, date_value)
                    all_showtimes.extend(flatten_showtimes(payload))
                relevant = [show for show in all_showtimes if _matches_theatre(radar, show)]
                new_relevant: list[dict[str, Any]] = []
                for showtime in relevant:
                    day = str(showtime.get("date") or showtime.get("showStartDateTime", ""))[:10]
                    key = f"drop:{radar.id}:{film_id}:{showtime.get('theatreId')}:{day}"
                    if self.database.observe_once(key):
                        detections += 1
                        new_relevant.append(showtime)
                        await self._alert(
                            "drop", f"Tickets live: {movie.get('name')}",
                            f"{showtime.get('theatre')} has showtimes on {day}.",
                            {"radar_id": radar.id, "movie": movie, "showtime": showtime},
                        )
                    if _has_imax(showtime):
                        imax_key = f"imax:{radar.id}:{film_id}:{showtime.get('theatreId')}:{day}"
                        if self.database.observe_once(imax_key):
                            detections += 1
                            await self._alert(
                                "format", f"IMAX detected: {movie.get('name')}",
                                f"IMAX is listed at {showtime.get('theatre')} on {day}.",
                                {"radar_id": radar.id, "movie": movie, "showtime": showtime},
                            )
                if new_relevant and radar.armed_mode != "notify_only":
                    prefs = radar.model_dump(mode="json")
                    prefs.update(
                        home_latitude=self.settings.home_latitude,
                        home_longitude=self.settings.home_longitude,
                        release_date=movie.get("releaseDate"),
                    )
                    ranked = rank_showtimes(relevant, prefs)
                    if ranked:
                        chosen = ranked[0]
                        commentary = None
                        if self.llm is not None and len(ranked) > 1:
                            try:
                                commentary = await tie_break_commentary(self.llm, ranked[0], ranked[1])
                            except Exception:
                                logger.warning("LLM tie-break unavailable; keeping deterministic winner")
                        seats: list[dict[str, Any]] = []
                        theatre_id = chosen.get("theatreId")
                        showtime_id = chosen.get("vistaSessionId")
                        if theatre_id and showtime_id:
                            try:
                                layout, availability = await asyncio.gather(
                                    self.cineplex.seat_layout(int(theatre_id), int(showtime_id)),
                                    self.cineplex.seat_availability(int(theatre_id), int(showtime_id)),
                                )
                                seats = rank_seats(
                                    normalize_seat_map(layout, availability), radar.party_size, prefs
                                )
                            except CineplexError:
                                logger.warning("Seat preview unavailable; sending showtime-only plan")
                        labels = [str(seat.get("label")) for seat in seats if seat.get("label")]
                        result = self.executor.prepare_deep_link(chosen)
                        booking = self.database.add_booking(
                            radar.id, result.state, chosen, seats=labels, deep_link=result.deep_link
                        )
                        seat_text = f" Suggested seats: {', '.join(labels)}." if labels else ""
                        reason_text = f" {commentary}" if commentary else ""
                        await self._alert(
                            "booking", f"Plan ready: {movie.get('name')}",
                            f"Best match: {chosen.get('theatre')} at {chosen.get('showStartDateTime')}."
                            f"{seat_text}{reason_text} Tap to continue.",
                            {"booking_id": booking.id, "deep_link": result.deep_link,
                             "showtime": chosen, "seats": labels, "commentary": commentary},
                        )
        return detections

    def _interval(self) -> float:
        if self.settings.burst_mode and self.settings.burst_until:
            try:
                until = datetime.fromisoformat(self.settings.burst_until.replace("Z", "+00:00"))
                if until > datetime.now(timezone.utc):
                    return float(self.settings.burst_interval_seconds)
            except ValueError:
                logger.warning("Ignoring invalid BURST_UNTIL; expected ISO-8601")
        return float(self.settings.poll_interval_seconds)

    async def run_forever(self) -> None:
        while True:
            try:
                await self.poll_once()
            except CineplexDisabled as exc:
                logger.warning("Watcher disabled until configured: %s", exc)
            except CineplexError as exc:
                logger.warning("Cineplex poll failed safely: %s", exc)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Unexpected watcher poll failure")
            interval = self._interval()
            jitter = random.uniform(0, min(self.settings.poll_jitter_seconds, interval * 0.25))
            await asyncio.sleep(interval + jitter)
