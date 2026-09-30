"""Shared Gemini client."""

from functools import lru_cache

from google import genai

from app.core.config import get_settings


class LLMNotConfiguredError(RuntimeError):
    """Raised when AI features are used without GEMINI_API_KEY."""


@lru_cache
def get_gemini_client() -> genai.Client:
    api_key = get_settings().gemini_api_key
    if not api_key:
        raise LLMNotConfiguredError("Set GEMINI_API_KEY in .env to use AI features.")
    return genai.Client(api_key=api_key)
