"""Loads settings from the environment (and .env, if present)."""
import os

from dotenv import load_dotenv

load_dotenv(override=True)

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "")
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN", "")
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN", "")  # read by the replicate client itself
REPLICATE_MODEL = os.getenv("REPLICATE_MODEL", "")
TRIGGER_WORD = os.getenv("TRIGGER_WORD", "TOK")


def require(*names):
    """Exit with a clear message if any of the named settings is empty."""
    missing = [n for n in names if not globals().get(n)]
    if missing:
        raise SystemExit(f"Missing required settings in .env: {', '.join(missing)}")
