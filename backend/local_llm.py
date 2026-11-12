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

    # 1. Dynamically query Groq for supported active models for this API key
    active_models: list[str] = []
    try:
        r = requests.get("https://api.groq.com/openai/v1/models", headers=headers, timeout=10)
        if r.status_code == 200:
            active_models = [m.get("id") for m in r.json().get("data", []) if m.get("id")]
    except Exception:
        pass

    preferred_candidates = [
        os.getenv("GROQ_MODEL", "").strip(),
        "llama-3.1-8b-instant",
        "llama-3.3-70b-versatile",
        "llama3-8b-8192",
        "llama3-70b-8192",
        "mixtral-8x7b-32768",
        "gemma2-9b-it",
    ]

    candidates: list[str] = []
    # If active models retrieved, pick preferred ones that are actively supported
    for p in preferred_candidates:
        if p and p in active_models and p not in candidates:
            candidates.append(p)
    # Add any other active llama models
    for a in active_models:
        if "llama" in a.lower() and a not in candidates:
            candidates.append(a)
    # Fallback to defaults if model list couldn't be retrieved
    for p in preferred_candidates:
        if p and p not in candidates:
            candidates.append(p)

    errors = []
    for model in candidates:
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        try:
            res = requests.post(url, json=payload, headers=headers, timeout=60)
            if res.status_code == 200:
                data = res.json()
                choices = data.get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content", "").strip()
            err_data = res.json() if "application/json" in res.headers.get("content-type", "") else {}
            msg = err_data.get("error", {}).get("message", res.text)
            errors.append(f"{model} ({res.status_code}): {msg}")
        except Exception as e:
            errors.append(f"{model}: {e}")
            continue

    raise LocalLLMError(f"Groq Cloud fallback failed. Attempts: {'; '.join(errors[:3])}")


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
        # In cloud environments with Groq enabled, report the active model so the UI activates
        return [model_name(), f"{model_name()} (Groq Cloud)"]
    return []
