"""Central configuration.

Everything is read from environment variables so secrets NEVER live in code.
Copy .env.example to .env and fill in your keys there - that is the ONLY
file you ever edit. This module is the only place that reads them.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # reads .env in the project root, if present

# --- API keys (set these in your .env file, never hardcode them) ---
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")  # optional, only for opening PRs

# --- Models ---
CHAT_MODEL: str = os.getenv("CHAT_MODEL", "gpt-4o-mini")
EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

# --- Infrastructure ---
REDIS_URL: str = os.getenv("REDIS_URL", "")  # empty -> built-in in-memory cache
DATA_DIR = Path(os.getenv("GITPILOT_DATA_DIR", "data")).resolve()
REPOS_DIR = DATA_DIR / "repos"      # cloned repositories live here
CHROMA_DIR = DATA_DIR / "chroma"    # the vector index lives here
DB_PATH = DATA_DIR / "gitpilot.db"  # SQLite metadata store

# --- Behaviour ---
MAX_AGENT_STEPS: int = int(os.getenv("MAX_AGENT_STEPS", "12"))
TEST_TIMEOUT_SECONDS: int = int(os.getenv("TEST_TIMEOUT_SECONDS", "120"))

for _dir in (DATA_DIR, REPOS_DIR, CHROMA_DIR):
    _dir.mkdir(parents=True, exist_ok=True)


def require_openai_key() -> str:
    """Fail fast with a helpful message if the key is missing."""
    if not OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. "
            "Copy .env.example to .env and paste your key there."
        )
    return OPENAI_API_KEY
