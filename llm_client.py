"""Unified LLM client supporting Anthropic Messages and OpenAI Chat Completions.

Provider is auto-detected from AUTONOVEL_API_BASE_URL (URLs containing
"anthropic" use the native Anthropic protocol; everything else uses the
OpenAI Chat Completions protocol). Set AUTONOVEL_API_PROVIDER to override.

API key is read from the first non-empty of:
  AUTONOVEL_API_KEY > ANTHROPIC_API_KEY > OPENAI_API_KEY
"""
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

API_BASE_URL = os.environ.get("AUTONOVEL_API_BASE_URL", "https://api.anthropic.com")
API_KEY = (
    os.environ.get("AUTONOVEL_API_KEY")
    or os.environ.get("ANTHROPIC_API_KEY")
    or os.environ.get("OPENAI_API_KEY")
    or ""
)
ANTHROPIC_BETA = "context-1m-2025-08-07"


def _resolve_provider() -> str:
    explicit = os.environ.get("AUTONOVEL_API_PROVIDER", "").strip().lower()
    if explicit in ("anthropic", "openai"):
        return explicit
    return "anthropic" if "anthropic" in API_BASE_URL.lower() else "openai"


def call(
    prompt: str,
    *,
    model: str,
    max_tokens: int = 4000,
    temperature: float = 0.7,
    system: str | None = None,
    timeout: float = 300.0,
    extra_beta: bool = False,
) -> str:
    """Call the configured LLM provider and return the text response."""
    if _resolve_provider() == "anthropic":
        return _call_anthropic(
            prompt, model, max_tokens, temperature, system, timeout, extra_beta
        )
    return _call_openai(prompt, model, max_tokens, temperature, system, timeout)


def _call_anthropic(prompt, model, max_tokens, temperature, system, timeout, extra_beta):
    headers = {
        "x-api-key": API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    if extra_beta:
        headers["anthropic-beta"] = ANTHROPIC_BETA
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        payload["system"] = system
    resp = httpx.post(
        f"{API_BASE_URL}/v1/messages",
        headers=headers,
        json=payload,
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()["content"][0]["text"]


def _call_openai(prompt, model, max_tokens, temperature, system, timeout):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": messages,
    }
    resp = httpx.post(
        f"{API_BASE_URL}/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]
