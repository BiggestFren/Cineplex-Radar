from __future__ import annotations

import json
from typing import Any, Protocol

import httpx
from pydantic import ValidationError

from .config import Settings
from .models import RadarCreate


SYSTEM_PROMPT = """You parse movie radar requests for one Toronto user.
Return JSON only. Never invent Cineplex IDs. Schema:
{"status":"complete|clarify","question":string|null,"radar":object|null}
radar fields: movie_query, movie_id(null), preferred_theatre_ids([]),
preferred_theatre_names, format_preference, preferred_dates, time_start,
time_end, first_day_bonus, party_size, armed_mode.
Use armed_mode=notify_only unless the user explicitly asks for assisted buying.
If movie identity, party size, or an essential preference is ambiguous, clarify.
"""


class SupportsCompletion(Protocol):
    async def complete_json(self, messages: list[dict[str, str]]) -> dict[str, Any]: ...


class LLMClient:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None):
        self.settings = settings
        self._owns_client = client is None
        self.client = client or httpx.AsyncClient(timeout=45.0)

    async def close(self) -> None:
        if self._owns_client:
            await self.client.aclose()

    async def complete_json(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        if not self.settings.llm_api_key or not self.settings.llm_model:
            raise RuntimeError("LLM_API_KEY and LLM_MODEL are required")
        response = await self.client.post(
            f"{self.settings.llm_base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.settings.llm_api_key}"},
            json={
                "model": self.settings.llm_model,
                "messages": messages,
                "temperature": 0,
                "response_format": {"type": "json_object"},
            },
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            raise ValueError("LLM response was not a JSON object")
        return parsed


async def parse_radar_request(client: SupportsCompletion, text: str) -> tuple[RadarCreate | None, str | None]:
    try:
        result = await client.complete_json(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ]
        )
    except (ValueError, json.JSONDecodeError, KeyError, TypeError):
        return None, "I couldn't safely parse that. Which movie, party size, and theatre or area should I watch?"
    if result.get("status") == "clarify" or not result.get("radar"):
        question = result.get("question")
        return None, str(question or "Could you clarify the movie and your key preferences?")
    try:
        return RadarCreate.model_validate(result["radar"]), None
    except ValidationError:
        return None, "I need a little more detail before creating this watch. What movie and party size?"


async def rank_suggestions(
    client: SupportsCompletion,
    upcoming: list[dict[str, Any]],
    history: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    prompt = {
        "task": "Choose zero to three worthwhile movies for this user this week and write a short pitch.",
        "rules": "Return {suggestions:[{tmdb_id,title,pitch}]}; use only supplied movies.",
        "upcoming": upcoming,
        "history": history,
    }
    result = await client.complete_json(
        [{"role": "system", "content": "You rank movie suggestions; return strict JSON only."},
         {"role": "user", "content": json.dumps(prompt)}]
    )
    suggestions = result.get("suggestions", [])
    return [item for item in suggestions[:3] if isinstance(item, dict)] if isinstance(suggestions, list) else []


async def tie_break_commentary(
    client: SupportsCompletion, first: dict[str, Any], second: dict[str, Any]
) -> str | None:
    top = float(first.get("score", 0))
    other = float(second.get("score", 0))
    if top <= 0 or abs(top - other) / top > 0.05:
        return None
    result = await client.complete_json(
        [
            {"role": "system", "content": "Pick between two nearly tied showtimes. JSON: {choice:1|2,reason:string}. One sentence."},
            {"role": "user", "content": json.dumps({"first": first, "second": second}, default=str)},
        ]
    )
    return str(result.get("reason")) if result.get("reason") else None

