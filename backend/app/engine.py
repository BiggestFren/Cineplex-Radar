from __future__ import annotations

import math
from datetime import datetime, time
from typing import Any, Iterable


FORMAT_SCORES = {
    "imax with laser": 100.0,
    "imax laser": 100.0,
    "digital imax": 90.0,
    "imax": 90.0,
    "ultraavx": 70.0,
    "laser projection": 12.0,
    "regular": 35.0,
    "standard": 35.0,
}


def _format_score(labels: Iterable[str]) -> float:
    joined = " ".join(str(label).lower() for label in labels)
    if "imax" in joined and "laser" in joined:
        return FORMAT_SCORES["imax with laser"]
    if "imax" in joined:
        return FORMAT_SCORES["imax"]
    if "ultraavx" in joined:
        return FORMAT_SCORES["ultraavx"] + (8.0 if "laser" in joined else 0.0)
    return FORMAT_SCORES["standard"]


def haversine_km(a_lat: float, a_lon: float, b_lat: float, b_lon: float) -> float:
    radius = 6371.0
    phi1, phi2 = math.radians(a_lat), math.radians(b_lat)
    dphi = math.radians(b_lat - a_lat)
    dlambda = math.radians(b_lon - a_lon)
    value = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _time_fit(show: time, start: str | None, end: str | None) -> float:
    if not start or not end:
        return 0.0
    start_t = time.fromisoformat(start)
    end_t = time.fromisoformat(end)
    minutes = show.hour * 60 + show.minute
    start_m = start_t.hour * 60 + start_t.minute
    end_m = end_t.hour * 60 + end_t.minute
    if start_m <= minutes <= end_m:
        centre = (start_m + end_m) / 2
        return 25.0 - abs(minutes - centre) / max((end_m - start_m) / 2, 1) * 5
    distance = min(abs(minutes - start_m), abs(minutes - end_m))
    return max(-25.0, -distance / 12)


def rank_showtimes(showtimes: list[dict[str, Any]], prefs: dict[str, Any]) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    home_lat = float(prefs.get("home_latitude", 43.6532))
    home_lon = float(prefs.get("home_longitude", -79.3832))
    preferred_dates = {str(value)[:10] for value in prefs.get("preferred_dates", [])}
    release_date = str(prefs.get("release_date") or "")[:10]
    for item in showtimes:
        dt = _parse_datetime(item.get("showStartDateTime"))
        if dt is None or item.get("isSoldOut") or not item.get("isShowtimeEnabledOnline", True):
            continue
        score = _format_score(item.get("experienceTypes", []))
        lat, lon = item.get("latitude"), item.get("longitude")
        if isinstance(lat, (float, int)) and isinstance(lon, (float, int)):
            distance = haversine_km(home_lat, home_lon, float(lat), float(lon))
            score += max(-40.0, 25.0 - distance * 2.5)
        show_date = dt.date().isoformat()
        if preferred_dates:
            score += 28.0 if show_date in preferred_dates else -12.0
        if prefs.get("first_day_bonus", True) and release_date and show_date == release_date:
            score += 35.0
        score += _time_fit(dt.time(), prefs.get("time_start"), prefs.get("time_end"))
        if int(item.get("seatsRemaining") or 0) < int(prefs.get("party_size", 1)):
            continue
        ranked.append({**item, "score": round(score, 3)})
    return sorted(ranked, key=lambda value: (-value["score"], value.get("showStartDateTime", "")))


def normalize_seat_map(layout: dict[str, Any], availability: dict[str, Any]) -> list[dict[str, Any]]:
    states = availability.get("seatAvailabilities", {})
    states = states if isinstance(states, dict) else {}
    seats: list[dict[str, Any]] = []
    areas = (
        ("standardSeats", "standard"),
        ("dboxSeats", "dbox"),
        ("balconySeats", "balcony"),
    )
    for key, category in areas:
        area = layout.get(key)
        if not isinstance(area, dict):
            continue
        rows = area.get("rows") if isinstance(area.get("rows"), list) else []
        for row in rows:
            if not isinstance(row, dict):
                continue
            row_number = int(row.get("number", 0)) + int(float(area.get("top", 0)))
            raw_seats = row.get("seats") if isinstance(row.get("seats"), list) else []
            for seat in raw_seats:
                if not isinstance(seat, dict):
                    continue
                seat_id = str(seat.get("id", ""))
                seat_type = str(seat.get("type", "Standard"))
                state = str(states.get(seat_id, "Unknown"))
                seats.append(
                    {
                        "id": seat_id,
                        "label": str(seat.get("label", seat_id)),
                        "row": row_number,
                        "column": float(area.get("left", 0))
                        + float(seat.get("column", 0)) * float(area.get("columnWidth", 1)),
                        "type": seat_type,
                        "category": category,
                        "available": state.lower() == "available",
                        "state": state,
                    }
                )
    return seats


def rank_seats(
    seat_map: list[dict[str, Any]] | dict[str, Any],
    party_size: int,
    prefs: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    if party_size < 1:
        return []
    prefs = prefs or {}
    seats = seat_map if isinstance(seat_map, list) else seat_map.get("seats", [])
    selectable = [
        seat for seat in seats
        if isinstance(seat, dict)
        and seat.get("available", False)
        and "wheelchair" not in str(seat.get("type", "")).lower()
        and "companion" not in str(seat.get("type", "")).lower()
    ]
    if not selectable:
        return []
    max_row = max(float(seat.get("row", 0)) for seat in selectable) or 1.0
    min_col = min(float(seat.get("column", 0)) for seat in selectable)
    max_col = max(float(seat.get("column", 0)) for seat in selectable)
    ideal_row = max_row * float(prefs.get("ideal_back_fraction", 0.60))
    ideal_col = (min_col + max_col) / 2
    by_row: dict[float, list[dict[str, Any]]] = {}
    for seat in selectable:
        by_row.setdefault(float(seat.get("row", 0)), []).append(seat)
    blocks: list[dict[str, Any]] = []
    for row, row_seats in by_row.items():
        ordered = sorted(row_seats, key=lambda value: float(value.get("column", 0)))
        for index in range(0, len(ordered) - party_size + 1):
            block = ordered[index : index + party_size]
            columns = [float(seat.get("column", 0)) for seat in block]
            gaps = [columns[i + 1] - columns[i] for i in range(len(columns) - 1)]
            if any(gap > 1.51 or gap <= 0 for gap in gaps):
                continue
            centre = sum(columns) / len(columns)
            score = -math.hypot((centre - ideal_col) * 1.25, (row - ideal_row) * 1.7)
            if row < max_row * 0.25:
                score -= 35.0
            edge_distance = min(min(columns) - min_col, max_col - max(columns))
            if edge_distance < 2:
                score -= (2 - edge_distance) * 12
            blocks.append({"score": score, "seats": block})
    if not blocks:
        return []
    best = max(blocks, key=lambda value: value["score"])
    return [{**seat, "block_score": round(best["score"], 3)} for seat in best["seats"]]

