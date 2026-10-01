import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")


def api_key() -> str:
    key = (os.getenv("GEMINI_API_KEY") or "").strip()
    if not key or key == "paste-your-key-here":
        raise RuntimeError("GEMINI_API_KEY is missing. Add it to .env")
    return key