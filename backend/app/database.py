from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .models import Booking, Event, RadarCreate, RadarItem, RadarUpdate, Suggestion


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(self.path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA foreign_keys=ON")
        self._migrate()

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def ping(self) -> bool:
        with self._lock:
            return self._connection.execute("SELECT 1").fetchone()[0] == 1

    def _migrate(self) -> None:
        with self._lock, self._connection:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS radar (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    movie_query TEXT NOT NULL,
                    movie_id INTEGER,
                    preferred_theatre_ids TEXT NOT NULL DEFAULT '[]',
                    preferred_theatre_names TEXT NOT NULL DEFAULT '[]',
                    format_preference TEXT NOT NULL DEFAULT '[]',
                    preferred_dates TEXT NOT NULL DEFAULT '[]',
                    time_start TEXT,
                    time_end TEXT,
                    first_day_bonus INTEGER NOT NULL DEFAULT 1,
                    party_size INTEGER NOT NULL DEFAULT 1,
                    armed_mode TEXT NOT NULL DEFAULT 'notify_only',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    message TEXT NOT NULL,
                    payload TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS suggestions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tmdb_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    release_date TEXT,
                    pitch TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    payload TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS bookings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    radar_id INTEGER,
                    state TEXT NOT NULL,
                    showtime TEXT NOT NULL DEFAULT '{}',
                    seats TEXT NOT NULL DEFAULT '[]',
                    deep_link TEXT,
                    hold_expires_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(radar_id) REFERENCES radar(id) ON DELETE SET NULL
                );
                CREATE TABLE IF NOT EXISTS observations (
                    fingerprint TEXT PRIMARY KEY,
                    observed_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS push_endpoints (
                    endpoint TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS preferences (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )

    def get_enabled_theatre_names(self, default_names: Iterable[str]) -> list[str]:
        with self._lock:
            row = self._connection.execute(
                "SELECT value FROM preferences WHERE key='enabled_theatre_names'"
            ).fetchone()
        if row is None:
            return list(default_names)
        try:
            value = json.loads(row["value"])
        except (TypeError, json.JSONDecodeError):
            return list(default_names)
        return [str(name) for name in value] if isinstance(value, list) else list(default_names)

    def set_enabled_theatre_names(self, names: Iterable[str]) -> list[str]:
        value = list(dict.fromkeys(str(name) for name in names))
        now = _now()
        with self._lock, self._connection:
            self._connection.execute(
                """INSERT INTO preferences(key,value,updated_at) VALUES('enabled_theatre_names',?,?)
                   ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at""",
                (json.dumps(value), now),
            )
        return value

    def register_push_endpoint(self, endpoint: str) -> None:
        now = _now()
        with self._lock, self._connection:
            self._connection.execute(
                """INSERT INTO push_endpoints(endpoint,created_at,updated_at) VALUES(?,?,?)
                   ON CONFLICT(endpoint) DO UPDATE SET updated_at=excluded.updated_at""",
                (endpoint, now, now),
            )

    def list_push_endpoints(self) -> list[str]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT endpoint FROM push_endpoints ORDER BY updated_at DESC"
            ).fetchall()
        return [str(row["endpoint"]) for row in rows]

    @staticmethod
    def _radar(row: sqlite3.Row) -> RadarItem:
        data = dict(row)
        for key in (
            "preferred_theatre_ids",
            "preferred_theatre_names",
            "format_preference",
            "preferred_dates",
        ):
            data[key] = json.loads(data[key])
        data["first_day_bonus"] = bool(data["first_day_bonus"])
        return RadarItem.model_validate(data)

    def list_radar(self) -> list[RadarItem]:
        with self._lock:
            rows = self._connection.execute("SELECT * FROM radar ORDER BY id").fetchall()
        return [self._radar(row) for row in rows]

    def get_radar(self, radar_id: int) -> RadarItem | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM radar WHERE id = ?", (radar_id,)
            ).fetchone()
        return self._radar(row) if row else None

    def create_radar(self, item: RadarCreate) -> RadarItem:
        data = item.model_dump(mode="json")
        now = _now()
        with self._lock, self._connection:
            cursor = self._connection.execute(
                """
                INSERT INTO radar (
                    movie_query, movie_id, preferred_theatre_ids,
                    preferred_theatre_names, format_preference, preferred_dates,
                    time_start, time_end, first_day_bonus, party_size, armed_mode,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data["movie_query"], data["movie_id"],
                    json.dumps(data["preferred_theatre_ids"]),
                    json.dumps(data["preferred_theatre_names"]),
                    json.dumps(data["format_preference"]),
                    json.dumps(data["preferred_dates"]), data["time_start"],
                    data["time_end"], int(data["first_day_bonus"]),
                    data["party_size"], data["armed_mode"], now, now,
                ),
            )
        return self.get_radar(cursor.lastrowid)  # type: ignore[return-value]

    def update_radar(self, radar_id: int, update: RadarUpdate) -> RadarItem | None:
        current = self.get_radar(radar_id)
        if current is None:
            return None
        merged = current.model_dump(exclude={"id", "created_at", "updated_at"})
        merged.update(update.model_dump(exclude_unset=True))
        validated = RadarCreate.model_validate(merged).model_dump(mode="json")
        with self._lock, self._connection:
            self._connection.execute(
                """
                UPDATE radar SET movie_query=?, movie_id=?, preferred_theatre_ids=?,
                    preferred_theatre_names=?, format_preference=?, preferred_dates=?,
                    time_start=?, time_end=?, first_day_bonus=?, party_size=?,
                    armed_mode=?, updated_at=? WHERE id=?
                """,
                (
                    validated["movie_query"], validated["movie_id"],
                    json.dumps(validated["preferred_theatre_ids"]),
                    json.dumps(validated["preferred_theatre_names"]),
                    json.dumps(validated["format_preference"]),
                    json.dumps(validated["preferred_dates"]), validated["time_start"],
                    validated["time_end"], int(validated["first_day_bonus"]),
                    validated["party_size"], validated["armed_mode"], _now(), radar_id,
                ),
            )
        return self.get_radar(radar_id)

    def delete_radar(self, radar_id: int) -> bool:
        with self._lock, self._connection:
            cursor = self._connection.execute("DELETE FROM radar WHERE id=?", (radar_id,))
        return cursor.rowcount > 0

    def add_event(
        self, event_type: str, title: str, message: str, payload: dict[str, Any] | None = None
    ) -> Event:
        now = _now()
        with self._lock, self._connection:
            cursor = self._connection.execute(
                "INSERT INTO events(type,title,message,payload,created_at) VALUES(?,?,?,?,?)",
                (event_type, title, message, json.dumps(payload or {}), now),
            )
        return Event(
            id=cursor.lastrowid, type=event_type, title=title, message=message,
            payload=payload or {}, created_at=now,
        )

    def list_events(self, since: datetime | None = None) -> list[Event]:
        query = "SELECT * FROM events"
        args: tuple[Any, ...] = ()
        if since:
            query += " WHERE created_at > ?"
            args = (since.isoformat(),)
        query += " ORDER BY created_at DESC, id DESC LIMIT 500"
        with self._lock:
            rows = self._connection.execute(query, args).fetchall()
        return [Event.model_validate({**dict(row), "payload": json.loads(row["payload"])}) for row in rows]

    def observe_once(self, fingerprint: str) -> bool:
        with self._lock, self._connection:
            cursor = self._connection.execute(
                "INSERT OR IGNORE INTO observations(fingerprint,observed_at) VALUES(?,?)",
                (fingerprint, _now()),
            )
        return cursor.rowcount == 1

    def add_suggestion(
        self, tmdb_id: int, title: str, release_date: str | None, pitch: str,
        payload: dict[str, Any] | None = None,
    ) -> Suggestion:
        now = _now()
        with self._lock, self._connection:
            cursor = self._connection.execute(
                """INSERT INTO suggestions(tmdb_id,title,release_date,pitch,status,payload,created_at,updated_at)
                   VALUES(?,?,?,?,?,?,?,?)""",
                (tmdb_id, title, release_date, pitch, "pending", json.dumps(payload or {}), now, now),
            )
        return self.get_suggestion(cursor.lastrowid)  # type: ignore[return-value]

    def get_suggestion(self, suggestion_id: int) -> Suggestion | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM suggestions WHERE id=?", (suggestion_id,)
            ).fetchone()
        if not row:
            return None
        return Suggestion.model_validate({**dict(row), "payload": json.loads(row["payload"])})

    def list_suggestions(self, status: str | None = None) -> list[Suggestion]:
        query = "SELECT * FROM suggestions"
        args: tuple[Any, ...] = ()
        if status:
            query += " WHERE status=?"
            args = (status,)
        query += " ORDER BY created_at DESC"
        with self._lock:
            rows = self._connection.execute(query, args).fetchall()
        return [Suggestion.model_validate({**dict(r), "payload": json.loads(r["payload"])}) for r in rows]

    def set_suggestion_status(self, suggestion_id: int, status: str) -> Suggestion | None:
        with self._lock, self._connection:
            self._connection.execute(
                "UPDATE suggestions SET status=?,updated_at=? WHERE id=?",
                (status, _now(), suggestion_id),
            )
        return self.get_suggestion(suggestion_id)

    def add_booking(
        self, radar_id: int | None, state: str, showtime: dict[str, Any],
        seats: Iterable[str] = (), deep_link: str | None = None,
        hold_expires_at: datetime | None = None,
    ) -> Booking:
        now = _now()
        with self._lock, self._connection:
            cursor = self._connection.execute(
                """INSERT INTO bookings(radar_id,state,showtime,seats,deep_link,hold_expires_at,created_at,updated_at)
                   VALUES(?,?,?,?,?,?,?,?)""",
                (radar_id, state, json.dumps(showtime), json.dumps(list(seats)), deep_link,
                 hold_expires_at.isoformat() if hold_expires_at else None, now, now),
            )
        return self.get_booking(cursor.lastrowid)  # type: ignore[return-value]

    def get_booking(self, booking_id: int) -> Booking | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM bookings WHERE id=?", (booking_id,)
            ).fetchone()
        if not row:
            return None
        return Booking.model_validate(
            {**dict(row), "showtime": json.loads(row["showtime"]), "seats": json.loads(row["seats"])}
        )

    def set_booking_state(self, booking_id: int, state: str) -> Booking | None:
        with self._lock, self._connection:
            self._connection.execute(
                "UPDATE bookings SET state=?,updated_at=? WHERE id=?",
                (state, _now(), booking_id),
            )
        return self.get_booking(booking_id)
