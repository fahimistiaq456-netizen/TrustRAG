"""Minimal Ollama client: private, local inference with no API key."""
from __future__ import annotations
import os
from typing import Any
import requests

from .config import get_settings


class LocalLLMError(RuntimeError):
    """Raised when Ollama is unavailable or returns an invalid response."""


def model_name() -> str:
    # Prefer the centralized HALLUFIX_OLLAMA_MODEL setting; fall back to the
    # legacy unprefixed OLLAMA_MODEL var so existing .env files keep working.
    return get_settings().ollama_model or os.getenv("OLLAMA_MODEL", "llama3.2:3b")


def _host() -> str:
    return (get_settings().ollama_host or os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")).rstrip("/")


def chat(messages: list[dict[str, str]], temperature: float = 0.2, json_mode: bool = False) -> str:
    host = _host()
    payload: dict[str, Any] = {"model": model_name(), "messages": messages, "stream": False, "options": {"temperature": temperature}}
    if json_mode:
        payload["format"] = "json"
    try:
        response = requests.post(f"{host}/api/chat", json=payload, timeout=180)
        response.raise_for_status()
        content = response.json().get("message", {}).get("content")
    except (requests.RequestException, ValueError) as exc:
        raise LocalLLMError(f"Ollama is unavailable. Install/start Ollama, then run `ollama pull {model_name()}`. Details: {exc}") from exc
    if not isinstance(content, str) or not content.strip():
        raise LocalLLMError("Ollama returned an empty response.")
    return content.strip()


def available_models() -> list[str]:
    host = _host()
    try:
        return [str(item["name"]) for item in requests.get(f"{host}/api/tags", timeout=3).json().get("models", [])]
    except (requests.RequestException, ValueError, KeyError):
        return []
