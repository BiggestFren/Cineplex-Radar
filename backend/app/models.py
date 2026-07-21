from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ArmedMode(StrEnum):
    notify_only = "notify_only"
    assisted_buy = "assisted_buy"
    unattended = "unattended"


class RadarBase(BaseModel):
    movie_query: str = Field(min_length=1, max_length=200)
    movie_id: int | None = None
    preferred_theatre_ids: list[int] = Field(default_factory=list)
    preferred_theatre_names: list[str] = Field(default_factory=list)
    format_preference: list[str] = Field(
        default_factory=lambda: ["IMAX with Laser", "IMAX", "UltraAVX", "Regular"]
    )
    preferred_dates: list[str] = Field(default_factory=list)
    time_start: str | None = None
    time_end: str | None = None
    first_day_bonus: bool = True
    party_size: int = Field(default=1, ge=1, le=8)
    armed_mode: ArmedMode = ArmedMode.notify_only

    @field_validator("time_start", "time_end")
    @classmethod
    def validate_time(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            datetime.strptime(value, "%H:%M")
        except ValueError as exc:
            raise ValueError("time must use 24-hour HH:MM") from exc
        return value


class RadarCreate(RadarBase):
    pass


class RadarUpdate(BaseModel):
    movie_query: str | None = Field(default=None, min_length=1, max_length=200)
    movie_id: int | None = None
    preferred_theatre_ids: list[int] | None = None
    preferred_theatre_names: list[str] | None = None
    format_preference: list[str] | None = None
    preferred_dates: list[str] | None = None
    time_start: str | None = None
    time_end: str | None = None
    first_day_bonus: bool | None = None
    party_size: int | None = Field(default=None, ge=1, le=8)
    armed_mode: ArmedMode | None = None


class RadarItem(RadarBase):
    id: int
    created_at: datetime
    updated_at: datetime


class Event(BaseModel):
    id: int
    type: str
    title: str
    message: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class Suggestion(BaseModel):
    id: int
    tmdb_id: int
    title: str
    release_date: str | None = None
    pitch: str
    status: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class Booking(BaseModel):
    id: int
    radar_id: int | None = None
    state: str
    showtime: dict[str, Any] = Field(default_factory=dict)
    seats: list[str] = Field(default_factory=list)
    deep_link: str | None = None
    hold_expires_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class PushRegistration(BaseModel):
    endpoint: str = Field(min_length=12, max_length=2000, pattern=r"^https://")


class ChatResponse(BaseModel):
    reply: str
    needs_clarification: bool = False
    radar_item: RadarItem | None = None
    draft: RadarCreate | None = None


class TheatrePreference(BaseModel):
    name: str
    address: str
    city: str = "Toronto"
    province: str = "ON"
    slug: str
    enabled: bool = True


class TheatrePreferencesUpdate(BaseModel):
    enabled_names: list[str] = Field(default_factory=list)


class Health(BaseModel):
    status: str = "ok"
    database: str = "ok"
    watcher_enabled: bool
    account_features_enabled: bool
    unattended_buy_enabled: bool
    time: datetime = Field(default_factory=utc_now)
