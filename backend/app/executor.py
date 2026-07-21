from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

from .config import Settings


def build_deep_link(showtime: dict[str, Any], film_slug: str | None = None) -> str:
    if showtime.get("ticketingRedesignUrl"):
        return str(showtime["ticketingRedesignUrl"])
    if showtime.get("ticketingUrl"):
        return str(showtime["ticketingUrl"])
    params = {
        "VistaSessionId": showtime.get("vistaSessionId"),
        "VISTAHOCategoryCode": showtime.get("areaCode", "0000000001"),
        "LocationId": showtime.get("theatreId"),
        "IsSeriesShowtime": "False",
    }
    return "https://apis.cineplex.com/prod/ticketing/api/v1/routing/redirect-to-ticketing?" + urlencode(params)


@dataclass(slots=True)
class ExecutionResult:
    state: str
    message: str
    deep_link: str | None = None


class BookingExecutor:
    """Safety boundary for account and checkout automation.

    Deep links are fully available. Authenticated Playwright operations deliberately
    remain blocked until redacted login, hold, CineClub, and confirmation traffic
    samples exist and a real v2b trial is explicitly run by the owner.
    """

    def __init__(self, settings: Settings):
        self.settings = settings

    def prepare_deep_link(self, showtime: dict[str, Any]) -> ExecutionResult:
        return ExecutionResult(
            state="ready_for_user",
            message="Showtime selected. Complete seat selection and purchase in Cineplex.",
            deep_link=build_deep_link(showtime, showtime.get("filmUrl")),
        )

    async def prepare_playwright(self, showtime: dict[str, Any], seats: list[str]) -> ExecutionResult:
        if not self.settings.enable_cineplex_account:
            return ExecutionResult("blocked", "ENABLE_CINEPLEX_ACCOUNT is disabled")
        if not self.settings.enable_checkout:
            return ExecutionResult("blocked", "ENABLE_CHECKOUT is disabled")
        return ExecutionResult(
            "blocked",
            "Authenticated v2b is safety-blocked until redacted login, hold, CineClub, and confirmation samples are captured.",
        )

    async def unattended_buy(self, *_: Any, **__: Any) -> ExecutionResult:
        if not self.settings.allow_unattended_buy:
            return ExecutionResult("blocked", "ALLOW_UNATTENDED_BUY is disabled")
        return ExecutionResult(
            "blocked", "v3 is not implemented before a documented successful real v2b purchase"
        )

