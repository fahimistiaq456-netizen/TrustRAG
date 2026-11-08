"""Minimal Ollama client with cloud fallback: private local inference with no API key."""
from __future__ import annotations
import os
from typing import Any
import requests

from .config import get_settings


class LocalLLMError(RuntimeError):
    """Raised when Ollama / Cloud LLM is unavailable or returns an invalid response."""


def model_name() -> str:
    # Prefer the centralized HALLUFIX_OLLAMA_MODEL setting; fall back to the
    # legacy unprefixed OLLAMA_MODEL var so existing .env files keep working.
    return get_settings().ollama_model or os.getenv("OLLAMA_MODEL", "llama3.2:3b")


def _host() -> str:
    return (get_settings().ollama_host or os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")).rstrip("/")


def _chat_groq(messages: list[dict[str, str]], api_key: str, temperature: float = 0.2, json_mode: bool = False) -> str:
    """Free cloud fallback when running in cloud environments (Render) where local Ollama is absent."""
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Content-Type": "application/json",
    }
    groq_model = os.getenv("GROQ_MODEL", "llama-3.2-3b-preview")
    payload: dict[str, Any] = {
        "model": groq_model,
        "messages": messages,
        "temperature": temperature,
        "stream": False,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    res = requests.post(url, json=payload, headers=headers, timeout=60)
    res.raise_for_status()
    data = res.json()
    choices = data.get("choices", [])
    if not choices:
        raise LocalLLMError("Groq returned an empty choice list.")
    content = choices[0].get("message", {}).get("content", "")
    return content.strip()


def chat(messages: list[dict[str, str]], temperature: float = 0.2, json_mode: bool = False) -> str:
    host = _host()
    payload: dict[str, Any] = {"model": model_name(), "messages": messages, "stream": False, "options": {"temperature": temperature}}
    if json_mode:
        payload["format"] = "json"

    # 1. First attempt: local Ollama (default on local machine)
    try:
        response = requests.post(f"{host}/api/chat", json=payload, timeout=60)
        response.raise_for_status()
        content = response.json().get("message", {}).get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
    except (requests.RequestException, ValueError) as exc:
        # 2. Second attempt: Cloud LLM fallback if GROQ_API_KEY is configured
        groq_key = os.getenv("GROQ_API_KEY", "").strip()
        if groq_key:
            try:
                return _chat_groq(messages, groq_key, temperature, json_mode)
            except Exception as groq_exc:
                raise LocalLLMError(f"Cloud fallback failed: {groq_exc}. Ollama error: {exc}") from groq_exc
        raise LocalLLMError(f"Ollama is unavailable at {host}. Install/start Ollama, or set GROQ_API_KEY in cloud. Details: {exc}") from exc

    if not isinstance(content, str) or not content.strip():
        raise LocalLLMError("Ollama returned an empty response.")
    return content.strip()


def available_models() -> list[str]:
    host = _host()
    try:
        models = [str(item["name"]) for item in requests.get(f"{host}/api/tags", timeout=3).json().get("models", [])]
        if models:
            return models
    except (requests.RequestException, ValueError, KeyError):
        pass
    if os.getenv("GROQ_API_KEY", "").strip():
        return ["llama-3.2-3b-preview (Cloud)"]
    return []
