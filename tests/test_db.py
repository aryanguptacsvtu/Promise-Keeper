from datetime import datetime, timedelta

import pytest

from promise_keeper import db, report

NOW = datetime(2026, 10, 2, 15, 30)


@pytest.fixture
def path(tmp_path):
    return tmp_path / "t.db"


def test_add_and_list(path):
    pid = db.add_promise("Send report", "Rahul", NOW + timedelta(hours=5), "tonight", "msg", path, NOW)
    rows = db.list_promises("pending", path)
    assert [r["id"] for r in rows] == [pid]
    assert rows[0]["person"] == "Rahul" and rows[0]["deadline"] == NOW + timedelta(hours=5)


def test_blank_person_becomes_none(path):
    db.add_promise("Do thing", "  ", None, None, None, path, NOW)
    assert db.list_promises(db_path=path)[0]["person"] is None


def test_done_and_delete(path):
    a = db.add_promise("A", db_path=path, now=NOW)
    b = db.add_promise("B", db_path=path, now=NOW)
    db.mark_done(a, path, NOW)
    assert [r["commitment"] for r in db.list_promises("pending", path)] == ["B"]
    assert [r["commitment"] for r in db.list_promises("done", path)] == ["A"]
    db.delete(b, path)
    assert db.list_promises("pending", path) == []


def test_ordering_deadline_first_none_last(path):
    db.add_promise("none", db_path=path, now=NOW)
    db.add_promise("late", deadline=NOW + timedelta(days=2), db_path=path, now=NOW)
    db.add_promise("soon", deadline=NOW + timedelta(hours=1), db_path=path, now=NOW)
    assert [r["commitment"] for r in db.list_promises(db_path=path)] == ["soon", "late", "none"]


def test_snooze_future_and_overdue(path):
    future = db.add_promise("f", deadline=NOW + timedelta(hours=2), db_path=path, now=NOW)
    past = db.add_promise("p", deadline=NOW - timedelta(days=3), db_path=path, now=NOW)
    db.snooze(future, 1, path, NOW)
    db.snooze(past, 1, path, NOW)
    got = {r["commitment"]: r["deadline"] for r in db.list_promises(db_path=path)}
    assert got["f"] == NOW + timedelta(hours=2, days=1)
    assert got["p"] == NOW + timedelta(days=1)


def test_report_groups_and_wording(path):
    db.add_promise("send project report", "Rahul", NOW - timedelta(hours=2), "tonight", db_path=path, now=NOW)
    db.add_promise("call mom", deadline=NOW + timedelta(days=1), db_path=path, now=NOW)
    db.add_promise("fix bike", db_path=path, now=NOW)
    text = report.forgetting_report(db.list_promises("pending", path), NOW)
    assert "3 open promises" in text
    assert "Send project report (to Rahul): was due" in text and "2 hours ago" in text
    assert text.index("Overdue") < text.index("Coming up") < text.index("No deadline")


def test_report_empty():
    assert "all caught up" in report.forgetting_report([], NOW)


def test_update_and_reopen(path):
    pid = db.add_promise("Old text", "Rahul", None, db_path=path, now=NOW)
    db.update_promise(pid, " New text ", "  ", NOW + timedelta(days=1), path)
    row = db.list_promises(db_path=path)[0]
    assert row["commitment"] == "New text" and row["person"] is None
    assert row["deadline"] == NOW + timedelta(days=1)
    db.mark_done(pid, path, NOW)
    db.reopen(pid, path)
    row = db.list_promises(db_path=path)[0]
    assert row["status"] == "pending" and row["completed_at"] is None


def test_group_by_person(path):
    db.add_promise("a", "Zoya", db_path=path, now=NOW)
    db.add_promise("b", None, db_path=path, now=NOW)
    db.add_promise("c", "amit", db_path=path, now=NOW)
    db.add_promise("d", "Zoya", db_path=path, now=NOW)
    groups = report.group_by_person(db.list_promises(db_path=path))
    assert list(groups) == ["amit", "Zoya", "Nobody in particular"]
    assert len(groups["Zoya"]) == 2


def test_weekly_stats(path):
    done_on_time = db.add_promise("a", deadline=NOW - timedelta(days=1), db_path=path, now=NOW - timedelta(days=3))
    done_late = db.add_promise("b", deadline=NOW - timedelta(days=2), db_path=path, now=NOW - timedelta(days=3))
    db.add_promise("missed", deadline=NOW - timedelta(days=2), db_path=path, now=NOW - timedelta(days=3))
    db.add_promise("ancient", deadline=NOW - timedelta(days=30), db_path=path, now=NOW - timedelta(days=31))
    db.add_promise("future", deadline=NOW + timedelta(days=2), db_path=path, now=NOW)
    db.mark_done(done_on_time, path, NOW - timedelta(days=2))
    db.mark_done(done_late, path, NOW - timedelta(hours=5))
    stats = report.weekly_stats(db.list_promises(db_path=path), NOW)
    assert stats == {"kept": 2, "total": 3, "on_time": 1, "overdue_now": 2}
    assert "kept 2 of 3" in report.describe_stats(stats)


def test_weekly_stats_empty():
    assert "No promises" in report.describe_stats(report.weekly_stats([], NOW))


def test_nudge_uses_only_given_facts():
    seen = {}

    def chat(messages, model=None, **kw):
        seen["user"] = messages[-1]["content"]
        return "  Hi Rahul, still on the report, sending it by 9pm.  "

    p = {"commitment": "Send report", "person": "Rahul", "deadline": NOW - timedelta(hours=3)}
    out = report.nudge(p, NOW, new_time="9pm", chat_fn=chat)
    assert out == "Hi Rahul, still on the report, sending it by 9pm."
    assert "Owed to: Rahul" in seen["user"] and "New time I can commit to: 9pm" in seen["user"]
