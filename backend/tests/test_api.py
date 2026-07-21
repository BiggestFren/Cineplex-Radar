from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


class FakeLLM:
    async def complete_json(self, messages):
        return {
            "status": "complete",
            "question": None,
            "radar": {
                "movie_query": "Dune: Messiah",
                "movie_id": None,
                "preferred_theatre_ids": [],
                "preferred_theatre_names": ["Scotiabank Theatre Toronto"],
                "format_preference": ["IMAX"],
                "preferred_dates": [],
                "time_start": "18:00",
                "time_end": "23:00",
                "first_day_bonus": True,
                "party_size": 2,
                "armed_mode": "notify_only",
            },
        }

    async def close(self):
        return None


def test_api_contract_and_auth(settings):
    app = create_app(settings)
    original_llm = app.state.llm
    app.state.llm = FakeLLM()
    headers = {"Authorization": "Bearer test-token"}
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/radar").status_code == 401

        theatres = client.get("/settings/theatres", headers=headers)
        assert theatres.status_code == 200
        assert len(theatres.json()) == 12
        assert all(item["enabled"] for item in theatres.json())
        selected_name = "Scotiabank Theatre Toronto"
        updated_theatres = client.put(
            "/settings/theatres", headers=headers, json={"enabled_names": [selected_name]}
        )
        assert updated_theatres.status_code == 200
        assert [item["name"] for item in updated_theatres.json() if item["enabled"]] == [selected_name]
        invalid_theatre = client.put(
            "/settings/theatres", headers=headers, json={"enabled_names": ["Made Up Cinema"]}
        )
        assert invalid_theatre.status_code == 422

        create = client.post("/radar", headers=headers, json={"movie_query": "The Odyssey", "party_size": 2})
        assert create.status_code == 201
        radar_id = create.json()["id"]
        assert client.get("/radar", headers=headers).json()[0]["id"] == radar_id
        patch = client.patch(f"/radar/{radar_id}", headers=headers, json={"party_size": 4})
        assert patch.status_code == 200 and patch.json()["party_size"] == 4
        blocked = client.patch(f"/radar/{radar_id}", headers=headers, json={"armed_mode": "unattended"})
        assert blocked.status_code == 409

        database = app.state.database
        database.add_event("drop", "Tickets live", "Toronto showtimes appeared")
        assert client.get("/events", headers=headers).status_code == 200

        accepted_source = database.add_suggestion(1, "Movie A", "2026-08-14", "Worth watching")
        accepted = client.post(f"/suggestions/{accepted_source.id}/accept", headers=headers)
        assert accepted.status_code == 200
        declined_source = database.add_suggestion(2, "Movie B", None, "Maybe")
        declined = client.post(f"/suggestions/{declined_source.id}/decline", headers=headers)
        assert declined.status_code == 200 and declined.json()["status"] == "declined"
        assert client.get("/suggestions", headers=headers).status_code == 200

        booking = database.add_booking(radar_id, "ready_for_user", {"vistaSessionId": 1}, deep_link="https://example.invalid")
        approve = client.post(f"/bookings/{booking.id}/approve", headers=headers)
        assert approve.status_code == 409
        cancel = client.post(f"/bookings/{booking.id}/cancel", headers=headers)
        assert cancel.status_code == 200 and cancel.json()["state"] == "cancelled"

        chat = client.post("/chat", headers=headers, json={"message": "Watch Dune in IMAX Friday evening for two"})
        assert chat.status_code == 200
        assert chat.json()["radar_item"]["movie_query"] == "Dune: Messiah"
        test_push = client.post("/notifications/test", headers=headers)
        assert test_push.status_code == 202
        registered = client.post(
            "/push/register", headers=headers, json={"endpoint": "https://push.example.invalid/u/abc"}
        )
        assert registered.status_code == 204
        assert database.list_push_endpoints() == ["https://push.example.invalid/u/abc"]

        deleted = client.delete(f"/radar/{radar_id}", headers=headers)
        assert deleted.status_code == 204
        assert client.delete("/radar/999999", headers=headers).status_code == 404
    # create_app built this client before it was replaced in app.state.
    import asyncio
    asyncio.run(original_llm.close())
