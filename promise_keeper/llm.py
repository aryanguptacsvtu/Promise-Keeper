"""Thin wrapper around a local Ollama server. Nothing here talks to the internet."""
from __future__ import annotations

from . import config


def chat(messages: list[dict], schema: dict | None = None, model: str | None = None,
         temperature: float = 0.0) -> str:
    """Send a chat to the local model and return the reply text.

    If `schema` is given, Ollama constrains the output to that JSON schema.
    """
    import ollama

    client = ollama.Client(host=config.OLLAMA_HOST)
    resp = client.chat(
        model=model or config.MODEL,
        messages=messages,
        format=schema,
        options={"temperature": temperature},
    )
    return resp["message"]["content"]


def check(model: str | None = None) -> tuple[bool, str]:
    """Is Ollama running and is the model pulled? Returns (ok, human message)."""
    model = model or config.MODEL
    try:
        import ollama

        listing = ollama.Client(host=config.OLLAMA_HOST).list()
        names = [getattr(m, "model", None) or m["name"] for m in listing["models"]]
    except Exception as exc:  # not installed, server down, ...
        return False, f"Can't reach Ollama at {config.OLLAMA_HOST} ({exc.__class__.__name__}). Is `ollama serve` running?"
    base = model.split(":")[0]
    if any(n == model or (":" not in model and n.split(":")[0] == base) for n in names):
        return True, f"Ollama is running, model `{model}` is ready."
    return False, f"Ollama is running but `{model}` isn't pulled. Run: ollama pull {model}"
