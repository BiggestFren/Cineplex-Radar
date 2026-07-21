from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Protocol

import httpx
from pydantic import ValidationError

from .config import Settings
from .models import RadarCreate


SYSTEM_PROMPT = """Extract one movie watch request for a Toronto user. Return JSON only.
Never invent Cineplex IDs. The only required user details are the movie identity and
party size. Words such as people, tickets, and seats all describe party_size. Theatre,
format, date, and time preferences are optional and must never trigger clarification.
Use empty arrays or the defaults below when an optional preference is not supplied.

Exact response schema:
{"status":"complete|clarify","question":string|null,"radar":object|null}

For a complete request, radar must be:
{"movie_query":string,"movie_id":null,"preferred_theatre_ids":[],
"preferred_theatre_names":string[],"format_preference":string[],
"preferred_dates":string[],"time_start":"HH:MM"|null,
"time_end":"HH:MM"|null,"first_day_bonus":boolean,"party_size":integer,
"armed_mode":"notify_only|assisted_buy"}

Use armed_mode="notify_only" unless the user explicitly requests assisted buying.
Use first_day_bonus=true unless the user says otherwise. Only clarify when the movie
identity or party size is genuinely absent or ambiguous. Do not ask again for a value
already stated by the user.
"""

REPAIR_PROMPT = """Re-check the user's original request and correct the previous JSON.
Do not ask for information the user already supplied. In particular, convert people,
tickets, or seats to an integer party_size and preserve the stated movie title. Return
the exact JSON schema from the system instruction, using defaults for optional fields.
"""

_LIST_FIELDS = {
    "preferred_theatre_ids",
    "preferred_theatre_names",
    "format_preference",
    "preferred_dates",
}

_NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
}


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


def _normalise_time(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    cleaned = value.strip().upper().replace(".", "")
    for pattern in ("%H:%M", "%I:%M %p", "%I %p"):
        try:
            return datetime.strptime(cleaned, pattern).strftime("%H:%M")
        except ValueError:
            continue
    return value


def _normalise_party_size(value: Any) -> Any:
    if isinstance(value, str):
        cleaned = value.strip().casefold()
        if cleaned in _NUMBER_WORDS:
            return _NUMBER_WORDS[cleaned]
        match = re.search(r"\b([1-8])\b", cleaned)
        if match:
            return int(match.group(1))
    return value


def _normalise_radar_payload(payload: Any) -> Any:
    if not isinstance(payload, dict):
        return payload

    # OpenAI-compatible models commonly emit null for unspecified optional fields.
    # Dropping those values lets RadarCreate apply its safe defaults.
    normalised = {
        key: value
        for key, value in payload.items()
        if value is not None or key == "movie_id"
    }
    for field in _LIST_FIELDS:
        value = normalised.get(field)
        if isinstance(value, str):
            normalised[field] = [value] if value.strip() else []

    normalised["party_size"] = _normalise_party_size(normalised.get("party_size"))
    for field in ("time_start", "time_end"):
        if field in normalised:
            normalised[field] = _normalise_time(normalised[field])

    mode = normalised.get("armed_mode")
    if isinstance(mode, str):
        safe_mode = mode.strip().casefold().replace("-", "_").replace(" ", "_")
        if safe_mode in {"notify", "notification", "notify_me", "notify_only"}:
            normalised["armed_mode"] = "notify_only"
        elif safe_mode in {"assist", "assisted", "assisted_buy", "assisted_buying"}:
            normalised["armed_mode"] = "assisted_buy"

    return normalised


def _validate_result(result: dict[str, Any]) -> RadarCreate | None:
    if result.get("status") == "clarify" or not result.get("radar"):
        return None
    try:
        return RadarCreate.model_validate(_normalise_radar_payload(result["radar"]))
    except ValidationError:
        return None


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

    draft = _validate_result(result)
    if draft is not None:
        return draft, None

    # Some smaller OpenAI-compatible models ignore values that are plainly present
    # in a full request. Give the model one constrained correction attempt before
    # showing a clarification to the user.
    try:
        repaired = await client.complete_json(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "instruction": REPAIR_PROMPT,
                            "original_request": text,
                            "previous_response": result,
                        }
                    ),
                },
            ]
        )
    except (ValueError, json.JSONDecodeError, KeyError, TypeError):
        repaired = {}

    draft = _validate_result(repaired)
    if draft is not None:
        return draft, None

    question = repaired.get("question") or result.get("question")
    return None, str(question or "Which movie should I watch, and how many people need seats?")


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
