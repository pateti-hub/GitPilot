"""One shared, lazily-created OpenAI client.

Lazy creation means the app can start (and /health works) even before a
key is configured - only real AI calls require the key.
"""
from __future__ import annotations

from openai import OpenAI

from . import config

_client: OpenAI | None = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=config.require_openai_key())
    return _client
