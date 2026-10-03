"""Turn phrases like "tonight" or "by Monday" into real datetimes.

Small local models are unreliable at date arithmetic, so the model only copies the
deadline *phrase* out of the message. This module does the maths, deterministically.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta

WEEKDAYS = {
    "monday": 0, "mon": 0, "tuesday": 1, "tues": 1, "tue": 1, "wednesday": 2, "wed": 2,
    "thursday": 3, "thurs": 3, "thu": 3, "friday": 4, "fri": 4, "saturday": 5, "sunday": 6,
    # Hindi / Hinglish
    "somvar": 0, "somwar": 0, "mangalvar": 1, "mangalwar": 1, "budhvar": 2, "budhwar": 2,
    "guruvar": 3, "guruwar": 3, "veervar": 3, "shukravar": 4, "shukrawar": 4,
    "shanivar": 5, "shaniwar": 5, "ravivar": 6, "raviwar": 6,
}
NUMBER_WORDS = {"half an": 0.5, "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4,
                "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
# (pattern, (hour, minute)) - first match wins
PARTS_OF_DAY = [
    (r"\bafter dinner\b", (21, 0)),
    (r"\bdinner\b", (20, 0)),
    (r"\b(tonight|tonite|night|raat)\b", (21, 0)),
    (r"\b(evening|shaam)\b", (18, 0)),
    (r"\b(afternoon|dopahar|dopahar mein)\b", (15, 0)),
    (r"\b(morning|subah|subha)\b", (9, 0)),
    (r"\b(noon|lunch)\b", (13, 0)),
    (r"\b(eod|end of (the )?day)\b", (18, 0)),
]
DEFAULT_TIME = (18, 0)


def resolve_deadline(text: str | None, now: datetime | None = None) -> datetime | None:
    """Best-effort conversion of a deadline phrase to a datetime. None if unclear."""
    if not text or not text.strip():
        return None
    t = text.lower().strip()
    now = (now or datetime.now()).replace(second=0, microsecond=0)

    # 1. "in 2 hours", "in half an hour"
    m = re.search(r"\bin\s+(half an|\d+(?:\.\d+)?|an?|one|two|three|four|five|six|seven|eight|nine|ten)"
                  r"\s*(minute|min|hour|hr|day|week)s?\b", t)
    if m:
        raw, unit = m.groups()
        n = float(raw) if re.fullmatch(r"\d+(?:\.\d+)?", raw) else NUMBER_WORDS[raw]
        unit = {"min": "minute", "hr": "hour"}.get(unit, unit)
        return now + {"minute": timedelta(minutes=n), "hour": timedelta(hours=n),
                      "day": timedelta(days=n), "week": timedelta(weeks=n)}[unit]

    # 2. Which day?
    today = now.replace(hour=0, minute=0)
    day = None
    if "day after tomorrow" in t or re.search(r"\b(parso|parson)\b", t):
        day = today + timedelta(days=2)
    # "kal" means both yesterday and tomorrow in Hindi; in a *promise* it's tomorrow.
    elif re.search(r"\b(tomorrow|tmrw|tmr|kal)\b", t):
        day = today + timedelta(days=1)
    elif re.search(r"\b(next week|agle hafte|agle week)\b", t):
        day = today + timedelta(days=7 - today.weekday())  # next Monday
    elif re.search(r"\bweekend\b", t):
        day = today + timedelta(days=(5 - today.weekday()) % 7)  # Saturday
    else:
        wd = re.search(r"\b(" + "|".join(WEEKDAYS) + r")\b", t)
        if wd:
            delta = (WEEKDAYS[wd.group(1)] - today.weekday()) % 7
            if delta == 0 and "today" not in t:
                delta = 7
            day = today + timedelta(days=delta)
        elif re.search(r"\b(today|aaj|tonight|tonite|eod|end of (the )?day|this (morning|afternoon|evening)|"
                       r"after dinner|later)\b", t):
            day = today

    # 3. Which time?
    hm = None
    m = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)", t)
    if m:
        h, mi, ap = int(m.group(1)), int(m.group(2) or 0), m.group(3)[0]
        if ap == "p" and h < 12:
            h += 12
        if ap == "a" and h == 12:
            h = 0
        hm = (h, mi)
    else:
        m = (re.search(r"\bat\s+(\d{1,2})(?::(\d{2}))?\b", t)
             or re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*baje\b", t)       # Hinglish: "5 baje"
             or re.search(r"\b(\d{1,2}):(\d{2})\b", t))
        if m:
            h, mi = int(m.group(1)), int(m.group(2) or 0)
            if 1 <= h <= 6 and ("at" in m.group(0) or "baje" in m.group(0)):
                h += 12  # "at 5" / "5 baje" almost always means 5pm
            if 6 < h < 12 and re.search(r"\b(evening|shaam|night|raat|tonight|afternoon|dopahar)\b", t):
                h += 12  # "shaam 7 baje", "tonight at 9" -> pm
            hm = (h, mi)
    explicit_time = hm is not None
    if hm is None:
        for pattern, value in PARTS_OF_DAY:
            if re.search(pattern, t):
                hm = value
                break

    if day is None and hm is None:
        return None
    if hm is None:
        hm = DEFAULT_TIME
    if not (0 <= hm[0] < 24 and 0 <= hm[1] < 60):
        return None
    if day is None:  # only a time, e.g. "at 5pm": today, or tomorrow if already past
        day = today
        if day.replace(hour=hm[0], minute=hm[1]) <= now:
            day += timedelta(days=1)

    result = day.replace(hour=hm[0], minute=hm[1])
    # "tonight" said at 10:30pm shouldn't be overdue the moment it's saved
    if not explicit_time and day == today and result < now and now.hour < 23:
        result = today.replace(hour=23, minute=59)
    return result
