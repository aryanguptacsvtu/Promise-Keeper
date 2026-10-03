from datetime import datetime

import pytest

from promise_keeper.dates import resolve_deadline

NOW = datetime(2026, 10, 2, 15, 30)  # a Friday


@pytest.mark.parametrize("text,expected", [
    ("tonight", datetime(2026, 10, 2, 21, 0)),
    ("after dinner", datetime(2026, 10, 2, 21, 0)),
    ("tomorrow morning", datetime(2026, 10, 3, 9, 0)),
    ("by Monday", datetime(2026, 10, 5, 18, 0)),
    ("Friday", datetime(2026, 10, 9, 18, 0)),          # today is Friday -> next Friday
    ("today", datetime(2026, 10, 2, 18, 0)),
    ("in 2 hours", datetime(2026, 10, 2, 17, 30)),
    ("in half an hour", datetime(2026, 10, 2, 16, 0)),
    ("in an hour", datetime(2026, 10, 2, 16, 30)),
    ("in 3 days", datetime(2026, 10, 5, 15, 30)),
    ("at 5pm", datetime(2026, 10, 2, 17, 0)),
    ("at 3pm", datetime(2026, 10, 3, 15, 0)),          # already passed -> tomorrow
    ("tomorrow at 10:30 am", datetime(2026, 10, 3, 10, 30)),
    ("next week", datetime(2026, 10, 5, 18, 0)),
    ("this weekend", datetime(2026, 10, 3, 18, 0)),
    ("day after tomorrow", datetime(2026, 10, 4, 18, 0)),
])
def test_resolves(text, expected):
    assert resolve_deadline(text, NOW) == expected


@pytest.mark.parametrize("text", [None, "", "   ", "whenever", "soon-ish"])
def test_unclear_returns_none(text):
    assert resolve_deadline(text, NOW) is None


def test_tonight_late_is_not_instantly_overdue():
    late = datetime(2026, 10, 2, 22, 30)
    assert resolve_deadline("tonight", late) == datetime(2026, 10, 2, 23, 59)


@pytest.mark.parametrize("text,expected", [
    ("kal subah", datetime(2026, 10, 3, 9, 0)),
    ("aaj raat", datetime(2026, 10, 2, 21, 0)),
    ("parso shaam", datetime(2026, 10, 4, 18, 0)),
    ("somvar tak", datetime(2026, 10, 5, 18, 0)),
    ("agle hafte", datetime(2026, 10, 5, 18, 0)),
    ("kal 5 baje", datetime(2026, 10, 3, 17, 0)),
    ("aaj shaam 7 baje", datetime(2026, 10, 2, 19, 0)),
    ("by Wed", datetime(2026, 10, 7, 18, 0)),
])
def test_hinglish_and_short_weekdays(text, expected):
    assert resolve_deadline(text, NOW) == expected
