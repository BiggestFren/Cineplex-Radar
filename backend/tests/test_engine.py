from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.engine import normalize_seat_map, rank_seats, rank_showtimes

FIXTURES = Path(__file__).parent / "fixtures"


def test_imax_with_laser_beats_digital_imax_and_ultraavx():
    showtimes = json.loads((FIXTURES / "showtimes_engine.json").read_text())
    ranked = rank_showtimes(
        showtimes,
        {
            "home_latitude": 43.65,
            "home_longitude": -79.38,
            "release_date": "2026-08-14",
            "preferred_dates": ["2026-08-14"],
            "time_start": "18:00",
            "time_end": "22:30",
            "party_size": 2,
        },
    )
    assert ranked[0]["id"] == "imax-laser"
    assert ranked[1]["id"] == "digital-imax"
    assert ranked[2]["id"] == "ultraavx"


@pytest.mark.parametrize("party_size", [1, 2, 3, 4])
def test_best_contiguous_seats_for_parties_one_to_four(party_size: int):
    fixture = json.loads((FIXTURES / "seat_map_engine.json").read_text())
    seats = rank_seats(fixture["seats"], party_size)
    assert len(seats) == party_size
    assert len({seat["row"] for seat in seats}) == 1
    assert all(seat["available"] for seat in seats)
    assert all("wheelchair" not in seat["type"].lower() for seat in seats)


def test_sold_out_centre_and_accessibility_seats_are_skipped():
    fixture = json.loads((FIXTURES / "seat_map_engine.json").read_text())
    selected = rank_seats(fixture["seats"], 4)
    labels = {seat["label"] for seat in selected}
    assert not labels.intersection({"G7", "G8", "G9", "G10", "H8", "H9"})


def test_normalizes_captured_cineplex_seat_contract():
    layout = json.loads((FIXTURES / "seat_layout_live_excerpt.json").read_text())
    availability = json.loads((FIXTURES / "seat_availability_live_excerpt.json").read_text())
    seats = normalize_seat_map(layout, availability)
    assert any(seat["label"] == "AA1" and seat["available"] for seat in seats)
    assert any(seat["type"] == "Wheelchair" for seat in seats)

