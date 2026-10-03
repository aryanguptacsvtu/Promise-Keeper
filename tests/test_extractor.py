import json
from datetime import datetime

import pytest

from promise_keeper.extractor import ExtractionError, extract_promises

NOW = datetime(2026, 10, 2, 15, 30)


def fake(payload):
    seen = {}

    def chat(messages, schema=None, model=None, **kw):
        seen["messages"], seen["schema"] = messages, schema
        return payload if isinstance(payload, str) else json.dumps(payload)

    chat.seen = seen
    return chat


def test_extracts_and_resolves_deadline():
    chat = fake({"promises": [{"commitment": "Send the report", "person": "Rahul",
                               "deadline_text": "tonight", "confidence": 0.9}]})
    out = extract_promises("I'll send you the report tonight", NOW, "Rahul", chat_fn=chat)
    assert out[0]["commitment"] == "Send the report"
    assert out[0]["person"] == "Rahul"
    assert out[0]["deadline"] == datetime(2026, 10, 2, 21, 0)


def test_prompt_contains_date_and_partner():
    chat = fake({"promises": []})
    extract_promises("hello", NOW, "Rahul", chat_fn=chat)
    user = chat.seen["messages"][-1]["content"]
    assert "Friday, 02 October 2026" in user and "Chat partner: Rahul" in user
    assert chat.seen["schema"] is not None


def test_no_promise_returns_empty():
    assert extract_promises("lol nice", NOW, chat_fn=fake({"promises": []})) == []


def test_low_confidence_and_blank_dropped():
    chat = fake({"promises": [
        {"commitment": "Maybe do X", "person": None, "deadline_text": None, "confidence": 0.2},
        {"commitment": "  ", "person": None, "deadline_text": None, "confidence": 0.9},
        {"commitment": "Do Y", "person": None, "deadline_text": None, "confidence": 0.8},
    ]})
    assert [p["commitment"] for p in extract_promises("x", NOW, chat_fn=chat)] == ["Do Y"]


def test_unparseable_deadline_kept_as_text_only():
    chat = fake({"promises": [{"commitment": "Do Z", "person": None,
                               "deadline_text": "whenever", "confidence": 0.9}]})
    out = extract_promises("x", NOW, chat_fn=chat)
    assert out[0]["deadline"] is None and out[0]["deadline_text"] == "whenever"


def test_bad_json_raises():
    with pytest.raises(ExtractionError):
        extract_promises("x", NOW, chat_fn=fake("not json at all"))


def test_empty_message_skips_model():
    def boom(*a, **k):
        raise AssertionError("model should not be called")
    assert extract_promises("   ", NOW, chat_fn=boom) == []
