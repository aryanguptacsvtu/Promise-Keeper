from datetime import datetime

from promise_keeper import whatsapp

ANDROID = """12/03/2026, 21:05 - Messages and calls are end-to-end encrypted.
12/03/2026, 21:06 - Rahul: Can you send the report?
12/03/2026, 21:07 - Me: Sure, I'll send it tonight
and I'll also call you tomorrow
12/03/2026, 21:08 - Me: <Media omitted>
13/03/2026, 08:00 - Me: lol nice
13/03/2026, 08:01 - Me: Kal subah main tumhe call karunga
"""

IOS = """[12/03/26, 9:05:03 PM] Rahul: hello
[12/03/26, 9:06:10 PM] Me: I will call you at 5
"""


def test_parse_android_multiline_and_skips():
    msgs = whatsapp.parse_chat(ANDROID)
    assert [m["sender"] for m in msgs] == ["Rahul", "Me", "Me", "Me"]
    assert msgs[1]["text"] == "Sure, I'll send it tonight\nand I'll also call you tomorrow"
    assert msgs[0]["when"] == datetime(2026, 3, 12, 21, 6)


def test_parse_ios_ampm_and_two_digit_year():
    msgs = whatsapp.parse_chat(IOS)
    assert msgs[1]["when"] == datetime(2026, 3, 12, 21, 6)


def test_dayfirst_heuristics():
    assert whatsapp.parse_chat("03/12/2026, 10:00 - A: hi")[0]["when"] == datetime(2026, 12, 3, 10, 0)
    assert whatsapp.parse_chat("03/12/2026, 10:00 - A: hi", dayfirst=False)[0]["when"] == datetime(2026, 3, 12, 10, 0)
    assert whatsapp.parse_chat("12/25/2026, 10:00 - A: hi")[0]["when"] == datetime(2026, 12, 25, 10, 0)


def test_senders_and_candidates():
    msgs = whatsapp.parse_chat(ANDROID)
    assert whatsapp.senders(msgs)[0] == "Me"
    cands = whatsapp.my_promise_candidates(msgs, "Me")
    assert [c["text"].split("\n")[0] for c in cands] == ["Sure, I'll send it tonight", "Kal subah main tumhe call karunga"]
    assert all(c["partner"] == "Rahul" for c in cands)


def test_candidates_since_filter():
    msgs = whatsapp.parse_chat(ANDROID)
    cands = whatsapp.my_promise_candidates(msgs, "Me", since=datetime(2026, 3, 13))
    assert len(cands) == 1
