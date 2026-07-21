import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .cineplex import CineplexClient
from .config import Settings
from .database import Database
from .discovery import DiscoveryService, TMDBClient
from .executor import BookingExecutor
from .llm import LLMClient, parse_radar_request
from .models import (
    Booking,
    ChatRequest,
    ChatResponse,
    Event,
    Health,
    RadarCreate,
    RadarItem,
    RadarUpdate,
    PushRegistration,
    Suggestion,
    TheatrePreference,
    TheatrePreferencesUpdate,
)
from .notifications import Notifier
from .theatres import TORONTO_THEATRES, toronto_theatre_names
from .watcher import Watcher

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)
bearer = HTTPBearer(auto_error=False, scheme_name="RadarBearer")


def _components(settings: Settings) -> dict[str, Any]:
    settings.validate_safety()
    database = Database(settings.database_path)
    cineplex = CineplexClient(settings)
    notifier = Notifier(settings, endpoint_provider=database.list_push_endpoints)
    llm = LLMClient(settings)
    tmdb = TMDBClient(settings)
    executor = BookingExecutor(settings)
    watcher = Watcher(settings, database, cineplex, notifier, executor, llm)
    discovery = DiscoveryService(settings, database, notifier, llm, tmdb)
    return {
        "settings": settings,
        "database": database,
        "cineplex": cineplex,
        "notifier": notifier,
        "llm": llm,
        "tmdb": tmdb,
        "discovery": discovery,
        "executor": executor,
        "watcher": watcher,
    }


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if not hasattr(app.state, "settings"):
            for key, value in _components(settings).items():
                setattr(app.state, key, value)
        tasks: list[asyncio.Task[None]] = []
        if app.state.settings.enable_watcher:
            tasks.append(asyncio.create_task(app.state.watcher.run_forever(), name="cineplex-watcher"))
            tasks.append(asyncio.create_task(_discovery_loop(app), name="tmdb-discovery"))
        try:
            yield
        finally:
            for task in tasks:
                task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            await app.state.cineplex.close()
            await app.state.notifier.close()
            await app.state.llm.close()
            await app.state.tmdb.close()
            app.state.database.close()

    async def _discovery_loop(app: FastAPI) -> None:
        while True:
            try:
                await app.state.discovery.run_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Daily TMDB discovery failed safely")
            await asyncio.sleep(24 * 60 * 60)

    app = FastAPI(
        title="Radar API",
        version="0.2.0",
        description="Personal Cineplex pre-order watcher and human-approved booking assistant.",
        lifespan=lifespan,
    )
    for key, value in _components(settings).items():
        setattr(app.state, key, value)

    async def require_auth(
        request: Request,
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    ) -> None:
        expected = request.app.state.settings.app_auth_token
        if credentials is None or credentials.scheme.lower() != "bearer" or credentials.credentials != expected:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid bearer token")

    @app.get("/health", response_model=Health, tags=["system"])
    async def health(request: Request) -> Health:
        configured = request.app.state.settings
        return Health(
            database="ok" if request.app.state.database.ping() else "error",
            watcher_enabled=configured.enable_watcher,
            account_features_enabled=configured.enable_cineplex_account and configured.enable_checkout,
            unattended_buy_enabled=configured.allow_unattended_buy,
        )

    @app.get("/radar", response_model=list[RadarItem], tags=["radar"])
    async def list_radar(auth: Annotated[None, Depends(require_auth)], request: Request) -> list[RadarItem]:
        return request.app.state.database.list_radar()

    def theatre_preferences(request: Request) -> list[TheatrePreference]:
        enabled = {
            name.casefold()
            for name in request.app.state.database.get_enabled_theatre_names(
                toronto_theatre_names()
            )
        }
        return [
            TheatrePreference(**item, enabled=item["name"].casefold() in enabled)
            for item in TORONTO_THEATRES
        ]

    @app.get(
        "/settings/theatres",
        response_model=list[TheatrePreference],
        tags=["settings"],
    )
    async def list_theatre_preferences(
        auth: Annotated[None, Depends(require_auth)], request: Request
    ) -> list[TheatrePreference]:
        return theatre_preferences(request)

    @app.put(
        "/settings/theatres",
        response_model=list[TheatrePreference],
        tags=["settings"],
    )
    async def update_theatre_preferences(
        auth: Annotated[None, Depends(require_auth)],
        request: Request,
        update: TheatrePreferencesUpdate,
    ) -> list[TheatrePreference]:
        canonical = {item["name"].casefold(): item["name"] for item in TORONTO_THEATRES}
        unknown = [name for name in update.enabled_names if name.casefold() not in canonical]
        if unknown:
            raise HTTPException(status_code=422, detail=f"Unknown Toronto theatre: {unknown[0]}")
        requested = {name.casefold() for name in update.enabled_names}
        ordered = [item["name"] for item in TORONTO_THEATRES if item["name"].casefold() in requested]
        request.app.state.database.set_enabled_theatre_names(ordered)
        return theatre_preferences(request)

    @app.post("/radar", response_model=RadarItem, status_code=201, tags=["radar"])
    async def create_radar(auth: Annotated[None, Depends(require_auth)], request: Request, item: RadarCreate) -> RadarItem:
        if item.armed_mode == "unattended" and not request.app.state.settings.allow_unattended_buy:
            raise HTTPException(status_code=409, detail="Unattended buying is disabled")
        return request.app.state.database.create_radar(item)

    @app.patch("/radar/{radar_id}", response_model=RadarItem, tags=["radar"])
    async def update_radar(
        radar_id: int, auth: Annotated[None, Depends(require_auth)], request: Request, update: RadarUpdate
    ) -> RadarItem:
        if update.armed_mode == "unattended" and not request.app.state.settings.allow_unattended_buy:
            raise HTTPException(status_code=409, detail="Unattended buying is disabled")
        result = request.app.state.database.update_radar(radar_id, update)
        if result is None:
            raise HTTPException(status_code=404, detail="Radar item not found")
        return result

    @app.delete("/radar/{radar_id}", status_code=204, tags=["radar"])
    async def delete_radar(radar_id: int, auth: Annotated[None, Depends(require_auth)], request: Request) -> Response:
        if not request.app.state.database.delete_radar(radar_id):
            raise HTTPException(status_code=404, detail="Radar item not found")
        return Response(status_code=204)

    @app.get("/events", response_model=list[Event], tags=["feed"])
    async def list_events(
        auth: Annotated[None, Depends(require_auth)],
        request: Request,
        since: datetime | None = Query(default=None),
    ) -> list[Event]:
        return request.app.state.database.list_events(since)

    @app.get("/suggestions", response_model=list[Suggestion], tags=["feed"])
    async def list_suggestions(
        auth: Annotated[None, Depends(require_auth)], request: Request, suggestion_status: str | None = None
    ) -> list[Suggestion]:
        return request.app.state.database.list_suggestions(suggestion_status)

    @app.post("/suggestions/{suggestion_id}/accept", response_model=RadarItem, tags=["feed"])
    async def accept_suggestion(suggestion_id: int, auth: Annotated[None, Depends(require_auth)], request: Request) -> RadarItem:
        suggestion = request.app.state.database.get_suggestion(suggestion_id)
        if suggestion is None:
            raise HTTPException(status_code=404, detail="Suggestion not found")
        if suggestion.status != "pending":
            raise HTTPException(status_code=409, detail="Suggestion already handled")
        radar = request.app.state.database.create_radar(
            RadarCreate(movie_query=suggestion.title, preferred_dates=[suggestion.release_date] if suggestion.release_date else [])
        )
        request.app.state.database.set_suggestion_status(suggestion_id, "accepted")
        request.app.state.database.add_event(
            "suggestion_accepted", suggestion.title, "Added to radar.",
            {"suggestion_id": suggestion_id, "radar_id": radar.id},
        )
        return radar

    @app.post("/suggestions/{suggestion_id}/decline", response_model=Suggestion, tags=["feed"])
    async def decline_suggestion(suggestion_id: int, auth: Annotated[None, Depends(require_auth)], request: Request) -> Suggestion:
        suggestion = request.app.state.database.get_suggestion(suggestion_id)
        if suggestion is None:
            raise HTTPException(status_code=404, detail="Suggestion not found")
        if suggestion.status != "pending":
            raise HTTPException(status_code=409, detail="Suggestion already handled")
        return request.app.state.database.set_suggestion_status(suggestion_id, "declined")

    @app.post("/bookings/{booking_id}/approve", response_model=Booking, tags=["booking"])
    async def approve_booking(booking_id: int, auth: Annotated[None, Depends(require_auth)], request: Request) -> Booking:
        booking = request.app.state.database.get_booking(booking_id)
        if booking is None:
            raise HTTPException(status_code=404, detail="Booking not found")
        if not (request.app.state.settings.enable_cineplex_account and request.app.state.settings.enable_checkout):
            raise HTTPException(
                status_code=409,
                detail="In-app final confirmation is disabled; use the booking deep link",
            )
        raise HTTPException(
            status_code=501,
            detail="v2b remains safety-blocked pending redacted authenticated API samples",
        )

    @app.post("/bookings/{booking_id}/cancel", response_model=Booking, tags=["booking"])
    async def cancel_booking(booking_id: int, auth: Annotated[None, Depends(require_auth)], request: Request) -> Booking:
        booking = request.app.state.database.get_booking(booking_id)
        if booking is None:
            raise HTTPException(status_code=404, detail="Booking not found")
        if booking.state in {"completed", "cancelled"}:
            raise HTTPException(status_code=409, detail="Booking can no longer be cancelled")
        return request.app.state.database.set_booking_state(booking_id, "cancelled")

    @app.post("/chat", response_model=ChatResponse, tags=["chat"])
    async def chat(auth: Annotated[None, Depends(require_auth)], request: Request, body: ChatRequest) -> ChatResponse:
        try:
            draft, question = await parse_radar_request(request.app.state.llm, body.message)
        except Exception:
            logger.exception("LLM request failed without exposing credentials")
            raise HTTPException(status_code=503, detail="LLM provider unavailable")
        if draft is None:
            return ChatResponse(reply=question or "Please clarify your request.", needs_clarification=True)
        if draft.armed_mode == "unattended" and not request.app.state.settings.allow_unattended_buy:
            draft = draft.model_copy(update={"armed_mode": "assisted_buy"})
        radar = request.app.state.database.create_radar(draft)
        return ChatResponse(
            reply=f"Added {radar.movie_query} to your radar for {radar.party_size}.",
            radar_item=radar,
            draft=draft,
        )

    @app.post("/notifications/test", status_code=202, tags=["system"])
    async def test_notification(
        auth: Annotated[None, Depends(require_auth)], request: Request
    ) -> dict[str, bool]:
        sent = await request.app.state.notifier.send(
            "Radar test notification",
            "Your ntfy connection is working.",
            priority="high",
            action="radar://settings",
            tags=["white_check_mark"],
        )
        return {"sent": sent}

    @app.post("/push/register", status_code=204, tags=["system"])
    async def register_push(
        body: PushRegistration,
        auth: Annotated[None, Depends(require_auth)],
        request: Request,
    ) -> Response:
        request.app.state.database.register_push_endpoint(body.endpoint)
        return Response(status_code=204)

    @app.post("/internal/poll", status_code=202, tags=["system"], include_in_schema=False)
    async def trigger_poll(auth: Annotated[None, Depends(require_auth)], request: Request) -> dict[str, int]:
        return {"detections": await request.app.state.watcher.poll_once()}

    return app


app = create_app()
