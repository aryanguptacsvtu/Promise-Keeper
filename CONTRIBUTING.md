# Contributing

Thanks for helping! Good first contributions:

- **More languages for `promise_keeper/dates.py`**: add day, weekday and time-of-day words
  (Marathi, Tamil, Bengali, Spanish...) plus parametrized cases in `tests/test_dates.py`.
- **More labelled messages in `tests/cases.json`** (use `"category"`: `core`, `hinglish`, `edge`, or a new one).
  Only add messages you have permission to share, and remove names and numbers.
- **Chat-export parsers** for Telegram / Signal / iMessage next to `promise_keeper/whatsapp.py`.

```bash
pip install -r requirements.txt
pytest                      # no model needed
python scripts/evaluate.py qwen2.5:3b   # needs Ollama
```

Please keep the two rules that make the project trustworthy: the model never does date maths,
and the "What am I forgetting?" list always comes from the database, not from the model.
