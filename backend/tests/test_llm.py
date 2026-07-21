from __future__ import annotations

import json
from pathlib import Path

from app.llm import parse_radar_request

GOLDENS = json.loads((Path(__file__).parent / "fixtures" / "llm_golden.json").read_text())


class RecordedLLM:
    def __init__(self, response):
        self.responses = response if isinstance(response, list) else [response]
        self.calls = 0

    async def complete_json(self, messages):
        assert messages[-1]["content"]
        response = self.responses[min(self.calls, len(self.responses) - 1)]
        self.calls += 1
        return response


async def test_golden_natural_language_parsing():
    for case in GOLDENS:
        item, question = await parse_radar_request(RecordedLLM(case["response"]), case["input"])
        if case["response"]["status"] == "complete":
            assert question is None
            assert item is not None
            assert item.model_dump(mode="json") == case["expected"]
        else:
            assert item is None
            assert question == case["response"]["question"]


async def test_invalid_json_shape_asks_follow_up():
    item, question = await parse_radar_request(RecordedLLM({"status": "complete", "radar": {}}), "watch something")
    assert item is None
    assert question


async def test_complete_request_accepts_common_openai_compatible_output():
    client = RecordedLLM(
        {
            "status": "complete",
            "question": None,
            "radar": {
                "movie_query": "Dune: Messiah",
                "movie_id": None,
                "preferred_theatre_ids": None,
                "preferred_theatre_names": "Scotiabank Theatre Toronto",
                "format_preference": None,
                "preferred_dates": None,
                "time_start": "6 PM",
                "time_end": "11:00 PM",
                "first_day_bonus": None,
                "party_size": "2 people",
                "armed_mode": "notify me",
            },
        }
    )

    item, question = await parse_radar_request(
        client,
        "Watch Dune Messiah at Scotiabank Theatre Toronto for two people from 6 PM to 11 PM. Notify me only.",
    )

    assert question is None
    assert item is not None
    assert item.movie_query == "Dune: Messiah"
    assert item.preferred_theatre_names == ["Scotiabank Theatre Toronto"]
    assert item.party_size == 2
    assert item.time_start == "18:00"
    assert item.time_end == "23:00"
    assert item.armed_mode == "notify_only"
    assert client.calls == 1


async def test_false_clarification_gets_one_constrained_retry():
    client = RecordedLLM(
        [
            {
                "status": "clarify",
                "question": "What movie and how many people?",
                "radar": None,
            },
            {
                "status": "complete",
                "question": None,
                "radar": {
                    "movie_query": "Dune: Messiah",
                    "preferred_theatre_names": ["Scotiabank Theatre Toronto"],
                    "party_size": 2,
                },
            },
        ]
    )

    item, question = await parse_radar_request(
        client,
        "Dune Messiah at Scotiabank Theatre Toronto for two people",
    )

    assert question is None
    assert item is not None
    assert item.movie_query == "Dune: Messiah"
    assert item.party_size == 2
    assert client.calls == 2
