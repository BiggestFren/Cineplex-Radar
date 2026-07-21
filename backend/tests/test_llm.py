from __future__ import annotations

import json
from pathlib import Path

from app.llm import parse_radar_request

GOLDENS = json.loads((Path(__file__).parent / "fixtures" / "llm_golden.json").read_text())


class RecordedLLM:
    def __init__(self, response):
        self.response = response

    async def complete_json(self, messages):
        assert messages[-1]["content"]
        return self.response


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

