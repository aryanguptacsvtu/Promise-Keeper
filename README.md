# 📝 Promise Keeper

A local-first assistant that remembers what you promised people. Paste a message
("I'll send you the report tonight" or "Kal subah main tumhe call karunga"), confirm what it found, and later ask
**"What am I forgetting?"**

**Open-source core:** an open-weight model running through [Ollama](https://ollama.com), stored in SQLite.
No API keys, no accounts, works with Wi-Fi off. Your messages and relationships never leave the machine.

## Run it

```bash
# 1. Install Ollama (https://ollama.com) and pull a small open-weight model
ollama pull qwen2.5:3b

# 2. Install and start the app
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

The sidebar shows whether Ollama and the model are reachable. Change the default model with
`PK_MODEL=llama3.2:3b streamlit run app.py` (or type another name in the sidebar).

## Features

- **Paste a message → promises.** English, Hindi and Hinglish ("kal subah", "aaj raat", "5 baje").
- **Import a WhatsApp chat export.** Only *your* lines are scanned, and "tomorrow" is resolved
  relative to when you *said* it, so old promises correctly show up as overdue.
- **You confirm everything.** Date/time pickers, edit any promise later, undo "done".
- **Group by status or by person** ("what do I owe Rahul?"), plus a weekly "you kept 7 of 9" summary.
- **Draft a nudge** for an overdue promise, written by the local model from the facts only.
- **"What am I forgetting?"** is a SQL query, never the model's memory.

## How it works

```
message ──► local LLM (JSON-schema output) ──► commitment, person, deadline *phrase*
                                                        │
                       dates.py resolves "tonight" / "by Monday" deterministically
                                                        │
                       you confirm / edit  ──►  SQLite  ──►  "What am I forgetting?"
```

Design choices worth mentioning in your write-up:

- **The model never does date maths.** Small models are bad at it, so it only copies the phrase
  ("by Monday"); `promise_keeper/dates.py` turns it into a datetime and is unit-tested.
- **The model never answers "what am I forgetting?" from memory.** The answer is a SQL query; the
  model may optionally reword it, but it can't add or drop items.
- **Human-in-the-loop:** nothing is saved until you confirm the extracted promise.
- **"No promise here" is a valid answer**, so ordinary chat doesn't create fake promises.

## Test and compare models

```bash
pytest                                                          # 54 tests, no model needed
python scripts/evaluate.py qwen2.5:3b llama3.2:3b gemma3:4b     # scores each model on tests/cases.json
```

`evaluate.py` prints a per-category breakdown (`core`, `hinglish`, `edge`) and a Markdown table
ready to paste into a post. Add your own friend's real messages to `tests/cases.json` (with their
permission, names removed).

### Results

Run the command above on your machine and paste the table here. Real numbers only:

| Model | Right # of promises | Deadlines | core | edge | hinglish | Avg s/msg |
|---|---|---|---|---|---|---|
| _run `scripts/evaluate.py`_ | | | | | | |


## Layout

```
app.py                  Streamlit UI
promise_keeper/
  llm.py                Ollama wrapper + health check
  whatsapp.py           chat-export parser + cheap promise pre-filter
  prompts.py            all prompt text
  extractor.py          message -> structured promises
  dates.py              deadline phrase -> datetime
  db.py                 SQLite storage
  report.py             "What am I forgetting?" logic
scripts/evaluate.py     model comparison
tests/                  pytest suite + labelled cases
```

## Ideas for next steps

Voice-note input with Whisper, desktop notifications for overdue items, fine-tuning a small model
on Hinglish promises, Telegram/Signal importers. See `CONTRIBUTING.md`.

## License

MIT, see `LICENSE`.
