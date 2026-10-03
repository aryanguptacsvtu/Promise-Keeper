"""Settings. Override any of them with environment variables."""
import os
from pathlib import Path

# Any model you've pulled with `ollama pull`. Try qwen2.5:3b, llama3.2:3b, gemma2:2b ...
MODEL = os.getenv("PK_MODEL", "gemma3:4b")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
DB_PATH = Path(os.getenv("PK_DB", Path(__file__).resolve().parent.parent / "data" / "promises.db"))

# Extractions the model is less sure about than this are dropped.
MIN_CONFIDENCE = float(os.getenv("PK_MIN_CONFIDENCE", "0.5"))
