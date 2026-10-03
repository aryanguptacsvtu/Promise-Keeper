"""Message in -> list of structured promises out."""
from __future__ import annotations

import json
from datetime import datetime

from . import config, llm, prompts
from .dates import resolve_deadline

SCHEMA = {
    "type": "object",
    "properties": {
        "promises": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "commitment": {"type": "string"},
                    "person": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                    "deadline_text": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                    "confidence": {"type": "number"},
                },
                "required": ["commitment", "person", "deadline_text", "confidence"],
            },
        }
    },
    "required": ["promises"],
}


class ExtractionError(RuntimeError):
    pass


def extract_promises(message: str, now: datetime | None = None, chat_partner: str | None = None,
                     model: str | None = None, chat_fn=None,
                     min_confidence: float | None = None) -> list[dict]:
    """Return [{commitment, person, deadline_text, deadline (datetime|None), confidence}, ...]."""
    if not message or not message.strip():
        return []
    now = now or datetime.now()
    chat_fn = chat_fn or llm.chat
    min_confidence = config.MIN_CONFIDENCE if min_confidence is None else min_confidence

    raw = chat_fn(
        [{"role": "system", "content": prompts.EXTRACT_SYSTEM},
         {"role": "user", "content": prompts.extract_user_prompt(message, now, chat_partner)}],
        schema=SCHEMA, model=model,
    )
    try:
        items = json.loads(raw)["promises"]
    except (ValueError, KeyError, TypeError) as exc:
        raise ExtractionError(f"Model did not return valid JSON: {raw[:200]!r}") from exc

    results = []
    for item in items:
        if not isinstance(item, dict):
            continue
        commitment = (item.get("commitment") or "").strip()
        confidence = float(item.get("confidence") or 0)
        if not commitment or confidence < min_confidence:
            continue
        deadline_text = (item.get("deadline_text") or "").strip() or None
        results.append({
            "commitment": commitment,
            "person": (item.get("person") or "").strip() or None,
            "deadline_text": deadline_text,
            "deadline": resolve_deadline(deadline_text, now),
            "confidence": confidence,
        })
    return results
