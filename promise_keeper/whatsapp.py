"""Read a WhatsApp "Export chat" .txt file and pull out the lines *you* wrote.

Everything here is plain parsing; it never touches a model or the network.
A cheap regex pre-filter keeps the model from having to read thousands of "ok" and "lol" lines.
"""
from __future__ import annotations

import re
from collections import Counter
from datetime import datetime

# Android: 12/03/2026, 21:05 - Name: text      iOS: [12/03/26, 9:05:03 PM] Name: text
LINE = re.compile(
    r"^\[?(\d{1,2})[/.](\d{1,2})[/.](\d{2,4}),?\s+(\d{1,2}):(\d{2})(?::\d{2})?\s*([AaPp]\.?[Mm]\.?)?\]?"
    r"\s*(?:-\s*)?([^:]+?):\s(.*)$"
)
INVISIBLE = dict.fromkeys(map(ord, "\u200e\u200f\u202a\u202c\u202f\ufeff"), " ")
SKIP_TEXT = ("<media omitted>", "image omitted", "video omitted", "sticker omitted",
             "audio omitted", "this message was deleted", "you deleted this message")

# Words that suggest a commitment (English + Hinglish). Deliberately generous: the model decides.
PROMISE_HINT = re.compile(
    r"\b(i'?ll|i will|i'?m going to|i promise|let me|will send|will call|will do|"
    r"remind me|get back to you|karunga|karungi|kar dunga|kar dungi|bhejunga|bhejungi|"
    r"bhej dunga|bhej dungi|dunga|dungi|aaunga|aaungi|batata hoon|bataunga|dekhta hoon|"
    r"main .{1,40}(karunga|karungi|dunga|dungi|aaunga|aaungi))\b",
    re.IGNORECASE,
)


def _to_datetime(d: str, mo: str, y: str, h: str, mi: str, ampm: str | None, dayfirst: bool) -> datetime | None:
    a, b = int(d), int(mo)
    day, month = (a, b) if dayfirst else (b, a)
    if a > 12:            # unambiguous: first number must be the day
        day, month = a, b
    elif b > 12:          # unambiguous: second number must be the day
        day, month = b, a
    year = int(y)
    if year < 100:
        year += 2000
    hour = int(h)
    if ampm:
        ap = ampm[0].lower()
        if ap == "p" and hour < 12:
            hour += 12
        if ap == "a" and hour == 12:
            hour = 0
    try:
        return datetime(year, month, day, hour, int(mi))
    except ValueError:
        return None


def parse_chat(text: str, dayfirst: bool = True) -> list[dict]:
    """[{'when': datetime, 'sender': str, 'text': str}, ...]. Multi-line messages are joined."""
    messages: list[dict] = []
    for raw in text.translate(INVISIBLE).splitlines():
        m = LINE.match(raw.strip("\r"))
        when = _to_datetime(*m.group(1, 2, 3, 4, 5, 6), dayfirst) if m else None
        if m and when:
            messages.append({"when": when, "sender": m.group(7).strip(), "text": m.group(8).strip()})
        elif messages and raw.strip():          # continuation of the previous message
            messages[-1]["text"] += "\n" + raw.strip()
    return [msg for msg in messages if not msg["text"].lower().startswith(SKIP_TEXT)]


def senders(messages: list[dict]) -> list[str]:
    """Names in the chat, most talkative first."""
    return [name for name, _ in Counter(m["sender"] for m in messages).most_common()]


def my_promise_candidates(messages: list[dict], me: str, since: datetime | None = None) -> list[dict]:
    """Lines written by `me` that look like they might contain a promise, each tagged with the
    other person's name when it's a 1:1 chat."""
    others = [s for s in senders(messages) if s != me]
    partner = others[0] if len(others) == 1 else None
    return [
        {**m, "partner": partner}
        for m in messages
        if m["sender"] == me and (since is None or m["when"] >= since) and PROMISE_HINT.search(m["text"])
    ]
