"""The "What am I forgetting?" answer.

The facts come from SQLite, never from the model's memory. The model is only allowed to
reword them (optional), so it can't invent or lose a promise.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from . import llm, prompts


def split_open(promises: list[dict], now: datetime | None = None):
    now = now or datetime.now()
    open_items = [p for p in promises if p["status"] == "pending"]
    overdue = [p for p in open_items if p["deadline"] and p["deadline"] < now]
    upcoming = [p for p in open_items if p["deadline"] and p["deadline"] >= now]
    no_deadline = [p for p in open_items if not p["deadline"]]
    return overdue, upcoming, no_deadline


def humanize(seconds: float) -> str:
    seconds = abs(int(seconds))
    if seconds < 3600:
        n, unit = max(seconds // 60, 1), "minute"
    elif seconds < 86400:
        n, unit = seconds // 3600, "hour"
    else:
        n, unit = seconds // 86400, "day"
    return f"{n} {unit}{'' if n == 1 else 's'}"


def describe_due(deadline: datetime | None, now: datetime) -> str:
    if not deadline:
        return "no deadline"
    gap = humanize((deadline - now).total_seconds())
    stamp = deadline.strftime("%a %d %b, %H:%M")
    return f"was due {stamp} ({gap} ago)" if deadline < now else f"due {stamp} (in {gap})"


def describe(p: dict, now: datetime) -> str:
    text = p["commitment"][0].upper() + p["commitment"][1:]
    who = f" (to {p['person']})" if p.get("person") else ""
    return f"{text}{who}: {describe_due(p['deadline'], now)}"


def forgetting_report(promises: list[dict], now: datetime | None = None) -> str:
    now = now or datetime.now()
    overdue, upcoming, no_deadline = split_open(promises, now)
    total = len(overdue) + len(upcoming) + len(no_deadline)
    if total == 0:
        return "You're all caught up. Nothing pending. 🎉"
    lines = [f"You have {total} open promise{'' if total == 1 else 's'}."]
    for title, group in (("⚠️ Overdue", overdue), ("📅 Coming up", upcoming), ("🕳️ No deadline", no_deadline)):
        if group:
            lines += ["", f"{title}:"] + [f"- {describe(p, now)}" for p in group]
    return "\n".join(lines)


def friendly(report_text: str, model: str | None = None, chat_fn=None) -> str:
    """Optional: let the local model reword the factual report in a kinder voice."""
    chat_fn = chat_fn or llm.chat
    return chat_fn(
        [{"role": "system", "content": prompts.FRIENDLY_SYSTEM},
         {"role": "user", "content": report_text}],
        model=model, temperature=0.4,
    ).strip()


def group_by_person(promises: list[dict]) -> dict[str, list[dict]]:
    """{'Rahul': [...], ..., 'Nobody in particular': [...]} - named people A-Z, unnamed last."""
    groups: dict[str, list[dict]] = {}
    for p in promises:
        groups.setdefault(p["person"] or "", []).append(p)
    ordered = {k: groups[k] for k in sorted((k for k in groups if k), key=str.lower)}
    if "" in groups:
        ordered["Nobody in particular"] = groups[""]
    return ordered


def weekly_stats(promises: list[dict], now: datetime | None = None, days: int = 7) -> dict:
    """How did the last `days` days go?

    The pool is every promise that was finished in the window, plus every still-open
    promise whose deadline passed in the window. `kept` = finished, `on_time` = finished
    by its deadline (or had none).
    """
    now = now or datetime.now()
    since = now - timedelta(days=days)
    kept = [p for p in promises if p["status"] == "done" and p["completed_at"] and p["completed_at"] >= since]
    missed = [p for p in promises if p["status"] == "pending" and p["deadline"] and since <= p["deadline"] < now]
    on_time = [p for p in kept if not p["deadline"] or p["completed_at"] <= p["deadline"]]
    overdue_now = [p for p in promises if p["status"] == "pending" and p["deadline"] and p["deadline"] < now]
    return {"kept": len(kept), "total": len(kept) + len(missed), "on_time": len(on_time),
            "overdue_now": len(overdue_now)}


def describe_stats(stats: dict) -> str:
    if stats["total"] == 0:
        return "No promises came due this week yet."
    return (f"This week you kept {stats['kept']} of {stats['total']} promises "
            f"({stats['on_time']} on time).")


def nudge(p: dict, now: datetime | None = None, new_time: str | None = None,
          model: str | None = None, chat_fn=None) -> str:
    """Draft a short, honest 'sorry, still on it' message for an overdue promise."""
    now = now or datetime.now()
    chat_fn = chat_fn or llm.chat
    facts = [f"Promise: {p['commitment']}", f"Owed to: {p['person'] or 'unknown'}",
             f"Original deadline: {describe_due(p['deadline'], now)}"]
    if new_time and new_time.strip():
        facts.append(f"New time I can commit to: {new_time.strip()}")
    return chat_fn(
        [{"role": "system", "content": prompts.NUDGE_SYSTEM},
         {"role": "user", "content": "\n".join(facts)}],
        model=model, temperature=0.5,
    ).strip()
