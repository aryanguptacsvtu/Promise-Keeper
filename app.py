"""Promise Keeper: run with  streamlit run app.py"""
from datetime import datetime, timedelta

import streamlit as st

from promise_keeper import config, db, llm, report, whatsapp
from promise_keeper.extractor import extract_promises

MAX_SCAN = 60  # most recent candidate lines the importer sends to the model

st.set_page_config(page_title="Promise Keeper", page_icon="📝", layout="centered")
db.init_db()

st.markdown(
    """
    <style>
    :root {
        --pk-ink: #243244;
        --pk-muted: #6b778c;
        --pk-accent: #4f46e5;
        --pk-accent-soft: #eef2ff;
        --pk-border: #e5e7eb;
        --pk-surface: #ffffff;
    }

    .stApp {
        background: linear-gradient(180deg, #f8faff 0%, #ffffff 34%);
        color: var(--pk-ink);
    }

    [data-testid="stHeader"] {
        background: transparent;
    }

    [data-testid="stSidebar"] {
        border-right: 1px solid var(--pk-border);
        background: #fbfcff;
    }

    [data-testid="stSidebar"] h2 {
        color: var(--pk-ink);
        letter-spacing: -0.02em;
    }

    h1 {
        color: var(--pk-ink);
        letter-spacing: -0.04em;
        margin-bottom: 0.2rem;
    }

    [data-testid="stMetric"] {
        padding: 0.85rem 1rem;
        border: 1px solid var(--pk-border);
        border-radius: 14px;
        background: var(--pk-surface);
        box-shadow: 0 5px 18px rgba(36, 50, 68, 0.05);
    }

    [data-testid="stMetricLabel"] {
        color: var(--pk-muted);
    }

    [data-baseweb="tab-list"] {
        gap: 0.35rem;
        border-bottom: 1px solid var(--pk-border);
    }

    [data-baseweb="tab"] {
        height: 3rem;
        padding: 0 0.85rem;
        color: var(--pk-muted);
    }

    [aria-selected="true"] {
        color: var(--pk-accent) !important;
        font-weight: 700;
    }

    .stButton > button,
    .stFormSubmitButton > button {
        border-radius: 9px;
        border-color: var(--pk-border);
        transition: border-color 120ms ease, box-shadow 120ms ease, transform 120ms ease;
    }

    .stButton > button:hover,
    .stFormSubmitButton > button:hover {
        border-color: var(--pk-accent);
        box-shadow: 0 4px 12px rgba(79, 70, 229, 0.14);
        transform: translateY(-1px);
    }

    .stButton button[kind="primary"],
    .stFormSubmitButton button[kind="primary"] {
        background: var(--pk-accent);
        border-color: var(--pk-accent);
    }

    [data-testid="stTextInput"] input,
    [data-testid="stTextArea"] textarea,
    [data-testid="stDateInput"] input,
    [data-testid="stTimeInput"] input {
        border-radius: 9px;
        border-color: var(--pk-border);
    }

    [data-testid="stExpander"] {
        border-color: var(--pk-border);
        border-radius: 12px;
        background: rgba(255, 255, 255, 0.72);
    }

    [data-testid="stCaptionContainer"] {
        color: var(--pk-muted);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

for key, default in (("candidates", None), ("source", ""), ("batch", 0), ("editing", None),
                     ("nudge_for", None), ("nudge_text", ""), ("import_cands", None), ("import_batch", 0)):
    st.session_state.setdefault(key, default)


@st.cache_data(ttl=15, show_spinner=False)
def cached_check(model_name: str):
    return llm.check(model_name)


# ---------- sidebar ----------
with st.sidebar:
    st.header("📝 Promise Keeper")
    model = st.text_input("Local model (Ollama)", config.MODEL)
    st.caption("Try `qwen2.5:3b`, `llama3.2:3b` or `gemma3:4b`. Swap freely, nothing else changes.")
    ok, msg = cached_check(model)
    (st.success if ok else st.error)(msg)
    if st.button("Re-check", help="Run the Ollama health check again"):
        cached_check.clear()
        st.rerun()
    st.caption("Everything runs on this machine. Your messages and promises are stored in "
               f"`{config.DB_PATH.name}` and never sent anywhere.")

st.title("Promise Keeper")
if flash := st.session_state.pop("flash", None):
    st.success(flash)

tab_add, tab_list, tab_forget, tab_import = st.tabs(
    ["➕ Add", "📋 My promises", "🤔 What am I forgetting?", "📥 Import WhatsApp"])


# ---------- shared widgets ----------
def due_inputs(key: str, default: datetime | None = None) -> datetime | None:
    """Checkbox + date picker + time picker. Returns None when 'Has deadline' is unticked."""
    c1, c2, c3 = st.columns([1, 1.4, 1])
    has = c1.checkbox("Has deadline", value=default is not None, key=f"{key}_has")
    base = default or datetime.now().replace(hour=18, minute=0, second=0, microsecond=0)
    d = c2.date_input("Due date", value=base.date(), key=f"{key}_d")
    t = c3.time_input("Due time", value=base.time(), key=f"{key}_t")
    return datetime.combine(d, t) if has else None


def candidate_form(name: str, cands: list[dict], batch: int, default_keep: bool, submit_label: str):
    """Review/edit extracted promises. Returns [(what, who, due, deadline_text, source), ...] of the
    ticked rows when submitted, else None."""
    rows = []
    with st.form(f"{name}_form"):
        for i, c in enumerate(cands):
            k = f"{name}_{batch}_{i}"
            st.markdown(f"**Promise {i + 1}**")
            if c.get("when"):
                st.caption(f"{c['when']:%d %b %Y, %H:%M} · “{c['source']}”")
            keep = st.checkbox("Save this one" if default_keep else "Still open, import it",
                               default_keep, key=f"{k}_keep")
            what = st.text_input("Promise", c["commitment"], key=f"{k}_what")
            who = st.text_input("Owed to", c["person"] or "", key=f"{k}_who")
            due = due_inputs(f"{k}_due", c["deadline"])
            if c["deadline_text"] and not c.get("when"):
                st.caption(f"You wrote: “{c['deadline_text']}”")
            rows.append((keep, what, who, due, c["deadline_text"], c.get("source")))
        submitted = st.form_submit_button(submit_label, type="primary")
    if not submitted:
        return None
    return [(w, p, d, dt, src) for k, w, p, d, dt, src in rows if k and w.strip()]


# ---------- add ----------
with tab_add:
    partner = st.text_input("Who is this conversation with? (optional)", placeholder="e.g. Rahul")
    message = st.text_area("Paste something you said or wrote (a chat message, a voice-note transcript)",
                           height=120, placeholder="Sure, I'll send you the project report tonight.\n"
                                                   "Kal subah main tumhe call karunga.")
    if st.button("Find promises", type="primary"):
        if not message.strip():
            st.warning("Paste a message first.")
        else:
            with st.spinner("Thinking, locally..."):
                try:
                    found = extract_promises(message, chat_partner=partner or None, model=model)
                    st.session_state.update(candidates=found, source=message,
                                            batch=st.session_state.batch + 1)
                except Exception as exc:
                    st.session_state.candidates = None
                    st.error(f"Couldn't extract promises: {exc}")

    cands = st.session_state.candidates
    if cands is not None and not cands:
        st.info("I didn't find any promises in that message. (Nothing saved.)")
    if cands:
        st.subheader("Is this right?")
        st.caption("Check and fix anything the model got wrong, then save.")
        chosen = candidate_form("add", cands, st.session_state.batch, True, "💾 Save selected")
        if chosen is not None:
            for w, p, d, dt, src in chosen:
                db.add_promise(w, p, d, dt, st.session_state.source)
            st.session_state.candidates = None
            st.session_state.flash = f"Saved {len(chosen)} promise(s). ✅"
            st.rerun()

    with st.expander("Or add one by hand"):
        with st.form("manual", clear_on_submit=True):
            m_what = st.text_input("Promise")
            m_who = st.text_input("Owed to")
            m_due = due_inputs("manual")
            if st.form_submit_button("Add") and m_what.strip():
                db.add_promise(m_what, m_who, m_due)
                st.session_state.flash = "Added. ✅"
                st.rerun()


# ---------- list ----------
def render_item(p: dict, now: datetime) -> None:
    pid = p["id"]
    if st.session_state.editing == pid:
        with st.form(f"edit_{pid}"):
            what = st.text_input("Promise", p["commitment"])
            who = st.text_input("Owed to", p["person"] or "")
            due = due_inputs(f"edit_{pid}", p["deadline"])
            c1, c2 = st.columns(2)
            save = c1.form_submit_button("Save", type="primary")
            cancel = c2.form_submit_button("Cancel")
        if save and what.strip():
            db.update_promise(pid, what, who, due)
            st.session_state.editing = None
            st.rerun()
        if cancel:
            st.session_state.editing = None
            st.rerun()
        return

    left, a, b, e, c = st.columns([5, 1, 1, 1, 1])
    who = f" → {p['person']}" if p["person"] else ""
    left.markdown(f"**{p['commitment']}**{who}")
    left.caption(report.describe_due(p["deadline"], now))
    if a.button("✅", key=f"done_{pid}", help="Mark done"):
        db.mark_done(pid); st.rerun()
    if b.button("😴", key=f"snz_{pid}", help="Snooze one day"):
        db.snooze(pid, 1); st.rerun()
    if e.button("✏️", key=f"edit_btn_{pid}", help="Edit"):
        st.session_state.editing = pid; st.rerun()
    if c.button("🗑️", key=f"del_{pid}", help="Delete"):
        db.delete(pid); st.rerun()

    if p["deadline"] and p["deadline"] < now:
        if left.button("💬 Draft a nudge", key=f"nudge_{pid}"):
            st.session_state.nudge_for, st.session_state.nudge_text = pid, ""
            st.rerun()
    if st.session_state.nudge_for == pid:
        with left:
            new_time = st.text_input("New time you can commit to (optional)", key=f"nt_{pid}",
                                     placeholder="e.g. tomorrow 10am")
            if st.button("Write it", key=f"nw_{pid}"):
                try:
                    with st.spinner("Writing, locally..."):
                        st.session_state.nudge_text = report.nudge(p, now, new_time, model=model)
                except Exception as exc:
                    st.warning(f"Model unavailable ({exc.__class__.__name__}).")
            if st.session_state.nudge_text:
                st.code(st.session_state.nudge_text, language=None, wrap_lines=True)
                st.caption("Drafted on this machine. Edit before you send.")


with tab_list:
    now = datetime.now()
    all_items = db.list_promises()
    overdue, upcoming, no_deadline = report.split_open(all_items, now)
    stats = report.weekly_stats(all_items, now)

    m1, m2, m3 = st.columns(3)
    m1.metric("Open", len(overdue) + len(upcoming) + len(no_deadline))
    m2.metric("Overdue", len(overdue))
    m3.metric("Kept this week", f"{stats['kept']}/{stats['total']}")
    st.caption(report.describe_stats(stats))

    view = st.radio("Group by", ["Status", "Person"], horizontal=True)
    if not (overdue or upcoming or no_deadline):
        st.info("No open promises. Add one in the first tab.")
    elif view == "Status":
        for title, group in (("⚠️ Overdue", overdue), ("📅 Coming up", upcoming), ("🕳️ No deadline", no_deadline)):
            if group:
                st.subheader(title)
                for p in group:
                    render_item(p, now)
    else:
        for person, group in report.group_by_person(overdue + upcoming + no_deadline).items():
            st.subheader(f"👤 {person} ({len(group)})")
            for p in group:
                render_item(p, now)

    done = [p for p in all_items if p["status"] == "done"]
    if done:
        with st.expander(f"Done ({len(done)})"):
            for p in done:
                left, right = st.columns([8, 1])
                left.markdown(f"~~{p['commitment']}~~" + (f" → {p['person']}" if p["person"] else ""))
                if right.button("↩️", key=f"reopen_{p['id']}", help="Mark as not done"):
                    db.reopen(p["id"]); st.rerun()

# ---------- what am I forgetting ----------
with tab_forget:
    nice = st.checkbox("Let the local model phrase it kindly", value=False)
    if st.button("What am I forgetting?", type="primary"):
        text = report.forgetting_report(db.list_promises("pending"))
        if nice and "open promise" in text:
            try:
                with st.spinner("Thinking, locally..."):
                    st.info(report.friendly(text, model=model))
            except Exception as exc:
                st.warning(f"Model unavailable ({exc.__class__.__name__}); showing the plain list.")
        st.markdown(text)
        st.caption("This list comes straight from the database, not from the model's memory.")

# ---------- import whatsapp ----------
with tab_import:
    st.caption("In WhatsApp: open a chat → ⋮ → More → Export chat → Without media. "
               "The file is read on this machine only; only lines *you* wrote are checked.")
    upload = st.file_uploader("Chat export (.txt)", type=["txt"])
    dayfirst = st.checkbox("Dates are day/month (India, UK, most of the world)", value=True)
    if upload:
        msgs = whatsapp.parse_chat(upload.getvalue().decode("utf-8", errors="ignore"), dayfirst=dayfirst)
        if not msgs:
            st.error("I couldn't find any messages in that file. Is it a WhatsApp 'Export chat' .txt?")
        else:
            me = st.selectbox("Which one is you?", whatsapp.senders(msgs))
            lookback = st.slider("Look back (days from the last message)", 7, 365, 30)
            since = msgs[-1]["when"] - timedelta(days=lookback)
            lines = whatsapp.my_promise_candidates(msgs, me, since)[-MAX_SCAN:]
            st.write(f"{len(msgs)} messages · {sum(m['sender'] == me for m in msgs)} from you · "
                     f"**{len(lines)}** look like possible promises"
                     + (f" (checking the latest {MAX_SCAN})" if len(lines) == MAX_SCAN else ""))
            if lines and st.button("Scan with the local model", type="primary"):
                found, bar = [], st.progress(0.0)
                try:
                    for n, line in enumerate(lines, 1):
                        # resolve "tomorrow" relative to when it was SAID, not today
                        for r in extract_promises(line["text"], now=line["when"],
                                                  chat_partner=line["partner"], model=model):
                            found.append({**r, "source": line["text"], "when": line["when"]})
                        bar.progress(n / len(lines))
                    st.session_state.import_cands = found
                    st.session_state.import_batch += 1
                except Exception as exc:
                    st.session_state.import_cands = None
                    st.error(f"Scan stopped: {exc}")
                bar.empty()

    cands = st.session_state.import_cands
    if cands is not None and not cands:
        st.info("No promises found in that chat. (Nothing saved.)")
    if cands:
        st.subheader(f"Found {len(cands)}")
        st.caption("Tick only the ones you still haven't done. Old deadlines will show as overdue, "
                   "which is the point.")
        chosen = candidate_form("import", cands, st.session_state.import_batch, False, "💾 Import ticked")
        if chosen is not None:
            have = {(x["commitment"].lower(), (x["person"] or "").lower()) for x in db.list_promises()}
            saved = skipped = 0
            for w, p, d, dt, src in chosen:
                if (w.strip().lower(), p.strip().lower()) in have:
                    skipped += 1
                    continue
                db.add_promise(w, p, d, dt, src)
                saved += 1
            st.session_state.import_cands = None
            st.session_state.flash = f"Imported {saved}" + (f", skipped {skipped} duplicate(s)" if skipped else "") + ". ✅"
            st.rerun()
