from __future__ import annotations

from app.database import Database
from app.models import RadarCreate
from app.watcher import Watcher


class FakeCineplex:
    async def movie_catalog(self):
        return [{"id": 99, "name": "Dune: Messiah", "filmUrl": "dune-messiah", "releaseDate": "2026-08-14"}]

    async def bookable_dates(self, film_id):
        assert film_id == 99
        return ["2026-08-14T00:00:00"]

    async def showtimes(self, film_id, date_value):
        return [
            {
                "theatre": "Scotiabank Theatre Toronto",
                "theatreId": 7402,
                "dates": [
                    {
                        "startDate": "2026-08-14T00:00:00",
                        "movies": [
                            {
                                "id": 99,
                                "name": "Dune: Messiah",
                                "filmUrl": "dune-messiah",
                                "experiences": [
                                    {
                                        "experienceTypes": ["IMAX", "Laser Projection"],
                                        "sessions": [
                                            {
                                                "vistaSessionId": 123,
                                                "areaCode": "0000000001",
                                                "showStartDateTime": "2026-08-14T19:00:00",
                                                "isSoldOut": False,
                                                "isShowtimeEnabledOnline": True,
                                                "seatsRemaining": 120,
                                                "ticketingUrl": "https://example.invalid/tickets",
                                            }
                                        ],
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        ]

    async def seat_layout(self, theatre_id, showtime_id):
        return {}

    async def seat_availability(self, theatre_id, showtime_id):
        return {}


class FakeNotifier:
    def __init__(self):
        self.sent = []

    async def send(self, title, message, **kwargs):
        self.sent.append((title, message, kwargs))
        return True


async def test_repeat_polls_are_deduplicated(settings):
    database = Database(settings.database_path)
    database.create_radar(
        RadarCreate(
            movie_query="Dune: Messiah",
            preferred_theatre_names=["Scotiabank Theatre Toronto"],
            armed_mode="assisted_buy",
            party_size=2,
        )
    )
    notifier = FakeNotifier()
    watcher = Watcher(settings, database, FakeCineplex(), notifier)
    first = await watcher.poll_once()
    second = await watcher.poll_once()
    assert first == 3  # catalog, theatre/date drop, IMAX-format alert
    assert second == 0
    assert len(database.list_events()) == 4  # plus one plan-ready event
    assert len(notifier.sent) == 4
    database.close()
